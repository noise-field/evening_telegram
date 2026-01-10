"""Daemon mode for running multiple subscriptions continuously."""

import asyncio
import signal
from typing import Optional

import structlog
from telethon import TelegramClient

from .config.models import Config, SubscriptionConfig
from .llm.client import LLMClient
from .llm.tracker import TokenTracker
from .models.data import Article, ArticleType, Newspaper, NewspaperSection
from .output import generate_html, send_email_report
from .processing import deduplicate_and_cluster, generate_article
from .scheduler import SubscriptionScheduler
from .state import StateManager
from .telegram import TelegramClientWrapper, fetch_messages, send_telegram_report
from datetime import datetime, timezone
import uuid
from pathlib import Path

logger = structlog.get_logger()


class EveningTelegramDaemon:
    """Daemon for running The Evening Telegram with multiple subscriptions."""

    def __init__(self, config: Config):
        """
        Initialize the daemon.

        Args:
            config: Application configuration
        """
        self.config = config
        self.schedulers: dict[str, SubscriptionScheduler] = {}
        self._stop_event = asyncio.Event()
        self._telegram_client_wrapper: Optional[TelegramClientWrapper] = None
        self._telegram_client: Optional[TelegramClient] = None
        self._state_manager: Optional[StateManager] = None

    async def initialize(self) -> None:
        """Initialize the daemon (state manager, etc.)."""
        logger.info("Initializing daemon")

        # Initialize state manager
        self._state_manager = StateManager(self.config.state.db_path)
        await self._state_manager.initialize()

        logger.info("Daemon initialized")

    async def run_subscription(
        self, subscription_id: str, subscription: SubscriptionConfig
    ) -> None:
        """
        Run a single subscription (generate and deliver a report).

        Args:
            subscription_id: Subscription ID
            subscription: Subscription configuration
        """
        logger.info(
            "Running subscription",
            subscription_id=subscription_id,
            subscription_name=subscription.name,
        )

        try:
            # Determine time window based on mode
            since_timestamp = None
            processed_ids: set[tuple[int, int]] = set()

            if self.config.state.mode == "since_last":
                last_run = await self._state_manager.get_last_successful_run(
                    subscription_id=subscription_id
                )
                if last_run:
                    since_timestamp = last_run[1]
                    logger.info(
                        "Running in incremental mode",
                        subscription=subscription.name,
                        since=since_timestamp,
                    )

                # Get processed message IDs for this subscription
                processed_ids = await self._state_manager.get_processed_message_ids(
                    subscription_id=subscription_id
                )
                logger.info(
                    "Found previously processed messages",
                    subscription=subscription.name,
                    count=len(processed_ids),
                )
            else:
                logger.info(
                    "Running in full mode",
                    subscription=subscription.name,
                )

            # Start new run
            period_start = since_timestamp or datetime.now().astimezone()
            period_end = datetime.now().astimezone()
            run_id = await self._state_manager.start_run(
                period_start, period_end, subscription_id=subscription_id
            )

            # Get processing config (use subscription-specific or defaults)
            from .config.models import ProcessingConfig

            processing_config = subscription.processing or ProcessingConfig()

            # Fetch messages
            logger.info(
                "Fetching messages",
                subscription=subscription.name,
                channel_count=len(subscription.channels),
            )

            # Ensure we have a telegram client
            if self._telegram_client is None:
                self._telegram_client_wrapper = TelegramClientWrapper(self.config.telegram)
                self._telegram_client = await self._telegram_client_wrapper.__aenter__()

            messages = await fetch_messages(
                client=self._telegram_client,
                channels=subscription.channels,
                schedule_config=subscription.schedule,
                processing_config=processing_config,
                since_timestamp=since_timestamp,
                processed_message_ids=processed_ids,
            )

            if not messages:
                logger.warning(
                    "No new messages to process", subscription=subscription.name
                )
                await self._state_manager.complete_run(run_id, 0)
                return

            logger.info(
                "Fetched messages", subscription=subscription.name, count=len(messages)
            )

            # Initialize LLM client
            token_tracker = TokenTracker()
            llm_client = LLMClient(self.config.llm, token_tracker)

            # Cluster messages
            logger.info("Clustering messages", subscription=subscription.name)
            clusters = await deduplicate_and_cluster(
                messages=messages,
                llm_client=llm_client,
                batch_size=processing_config.clustering_batch_size,
            )
            logger.info(
                "Created topic clusters",
                subscription=subscription.name,
                count=len(clusters),
            )

            # Filter clusters by minimum sources
            significant_clusters = [
                c
                for c in clusters
                if c.source_count >= processing_config.min_sources_for_article
            ]
            brief_clusters = [
                c
                for c in clusters
                if c.source_count < processing_config.min_sources_for_article
            ]

            logger.info(
                "Filtered clusters",
                subscription=subscription.name,
                significant=len(significant_clusters),
                brief=len(brief_clusters),
            )

            # Generate articles
            logger.info("Generating articles", subscription=subscription.name)
            articles: list[Article] = []

            for cluster in significant_clusters:
                article = await generate_article(
                    cluster=cluster,
                    language=subscription.output.language,
                    newspaper_name=subscription.output.newspaper_name,
                    llm_client=llm_client,
                )
                if article:
                    articles.append(article)

            # Generate briefs
            for cluster in brief_clusters:
                cluster.suggested_type = ArticleType.BRIEF
                cluster.suggested_section = "In Brief"
                article = await generate_article(
                    cluster=cluster,
                    language=subscription.output.language,
                    newspaper_name=subscription.output.newspaper_name,
                    llm_client=llm_client,
                )
                if article:
                    articles.append(article)

            logger.info(
                "Generated articles",
                subscription=subscription.name,
                count=len(articles),
            )

            # Organize into sections
            sections_dict: dict[str, list[Article]] = {}
            for article in articles:
                if article.section not in sections_dict:
                    sections_dict[article.section] = []
                sections_dict[article.section].append(article)

            # Create sections with order from config
            section_order = subscription.output.sections

            sections = []
            for idx, section_name in enumerate(section_order):
                if section_name in sections_dict:
                    sections.append(
                        NewspaperSection(
                            name=section_name,
                            articles=sections_dict[section_name],
                            order=idx,
                        )
                    )

            # Add any remaining sections not in the order list
            for section_name, section_articles in sections_dict.items():
                if section_name not in section_order:
                    sections.append(
                        NewspaperSection(
                            name=section_name,
                            articles=section_articles,
                            order=len(sections),
                        )
                    )

            # Create newspaper
            newspaper = Newspaper(
                edition_id=str(uuid.uuid4()),
                title=subscription.output.newspaper_name,
                tagline=subscription.output.tagline,
                edition_date=datetime.now(timezone.utc),
                period_start=period_start,
                period_end=period_end,
                language=subscription.output.language,
                sections=sections,
                total_messages_processed=len(messages),
                total_channels=len(set(m.channel_id for m in messages)),
                token_usage=token_tracker.to_dict(),
            )

            # Output
            html_content = ""
            html_path_str = ""

            # Generate HTML
            if subscription.output.save_html:
                logger.info("Generating HTML", subscription=subscription.name)
                channel_info = [
                    {"username": ch, "title": ch} for ch in subscription.channels
                ]
                html_path_str = generate_html(
                    newspaper, subscription.output.html_path, channel_info
                )
                logger.info(
                    "Saved HTML", subscription=subscription.name, path=html_path_str
                )

                # Read HTML content for email
                with open(html_path_str, "r", encoding="utf-8") as f:
                    html_content = f.read()

            # Send via Telegram
            if (
                subscription.output.send_telegram
                and subscription.output.telegram
                and subscription.output.telegram.bot_token
                and subscription.output.telegram.chat_id
            ):
                logger.info("Sending to Telegram", subscription=subscription.name)
                await send_telegram_report(
                    newspaper=newspaper,
                    bot_token=subscription.output.telegram.bot_token,
                    chat_id=subscription.output.telegram.chat_id,
                    html_path=html_path_str if html_path_str else None,
                )
                logger.info("Sent to Telegram", subscription=subscription.name)

            # Send via email
            if subscription.output.send_email:
                # Build email config
                email_config = None

                if subscription.output.email and self.config.email:
                    # Merge subscription email config with global config
                    from .config.models import EmailConfig

                    email_config = EmailConfig(
                        smtp_host=self.config.email.smtp_host,
                        smtp_port=self.config.email.smtp_port,
                        smtp_user=self.config.email.smtp_user,
                        smtp_password=self.config.email.smtp_password,
                        use_tls=self.config.email.use_tls,
                        to=subscription.output.email.to,
                        from_address=subscription.output.email.from_address
                        or self.config.email.from_address,
                        from_name=subscription.output.email.from_name
                        or self.config.email.from_name,
                    )
                elif self.config.email:
                    email_config = self.config.email

                if email_config:
                    logger.info("Sending email", subscription=subscription.name)
                    if not html_content:
                        # Generate HTML for email if not already generated
                        channel_info = [
                            {"username": ch, "title": ch}
                            for ch in subscription.channels
                        ]
                        from jinja2 import Environment, FileSystemLoader, select_autoescape

                        template_dir = Path(__file__).parent / "templates"
                        env = Environment(
                            loader=FileSystemLoader(template_dir),
                            autoescape=select_autoescape(["html", "xml"]),
                        )
                        template = env.get_template("newspaper.html")
                        html_content = template.render(
                            newspaper=newspaper,
                            language=newspaper.language,
                            channels=channel_info,
                        )

                    await send_email_report(newspaper, html_content, email_config)
                    logger.info("Sent email", subscription=subscription.name)

            # Mark messages as processed
            message_ids = [(m.channel_id, m.message_id) for m in messages]
            await self._state_manager.mark_messages_processed(
                run_id, message_ids, subscription_id=subscription_id
            )

            # Complete run
            await self._state_manager.complete_run(run_id, len(messages))

            logger.info(
                "Subscription run completed successfully",
                subscription=subscription.name,
                articles=newspaper.total_articles,
                messages=newspaper.total_messages_processed,
                llm_tokens=token_tracker.total_tokens,
            )

        except Exception as e:
            logger.error(
                "Error running subscription",
                subscription=subscription.name,
                error=str(e),
                exc_info=True,
            )
            raise

    async def start(self) -> None:
        """Start the daemon and all subscription schedulers."""
        await self.initialize()

        logger.info(
            "Starting daemon with subscriptions",
            subscription_count=len(self.config.subscriptions),
        )

        # Create schedulers for each subscription
        for sub_id, sub_config in self.config.subscriptions.items():
            # Create a callback that captures the subscription
            async def make_callback(sid: str, sconfig: SubscriptionConfig):
                async def callback():
                    await self.run_subscription(sid, sconfig)

                return callback

            callback = await make_callback(sub_id, sub_config)

            scheduler = SubscriptionScheduler(
                subscription_id=sub_id,
                subscription_name=sub_config.name,
                schedule=sub_config.schedule,
                callback=callback,
            )

            self.schedulers[sub_id] = scheduler
            scheduler.start()

            logger.info(
                "Started scheduler",
                subscription_id=sub_id,
                subscription_name=sub_config.name,
            )

        logger.info("All schedulers started, daemon running")

        # Wait for stop signal
        await self._stop_event.wait()

        logger.info("Stopping daemon")

        # Stop all schedulers
        for sub_id, scheduler in self.schedulers.items():
            logger.info("Stopping scheduler", subscription_id=sub_id)
            await scheduler.stop()

        # Clean up telegram client
        if self._telegram_client_wrapper:
            await self._telegram_client_wrapper.__aexit__(None, None, None)

        logger.info("Daemon stopped")

    def stop(self) -> None:
        """Signal the daemon to stop."""
        self._stop_event.set()

    def setup_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Set up signal handlers for graceful shutdown.

        Args:
            loop: The asyncio event loop to attach signal handlers to
        """
        def signal_handler():
            logger.info("Received shutdown signal, stopping daemon")
            self.stop()

        # Use asyncio's signal handlers which work properly with the event loop
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
