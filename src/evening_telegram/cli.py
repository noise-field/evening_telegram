"""CLI interface for The Evening Telegram."""

import asyncio
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import click
import structlog

from .config import load_config
from .llm.client import LLMClient
from .llm.tracker import TokenTracker
from .models.data import Article, ArticleType, Newspaper, NewspaperSection
from .output import generate_html, send_email_report
from .processing import deduplicate_and_cluster, generate_article
from .state import StateManager
from .telegram import TelegramClientWrapper, fetch_messages, send_telegram_report

logger = structlog.get_logger()


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--lookback", help="Override time lookback period (e.g., '24 hours', '7 days')")
@click.option("--from", "from_time", help="Start time for explicit time range")
@click.option("--to", "to_time", help="End time for explicit time range")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Override HTML output path")
@click.option("--channels", help="Comma-separated list of channels (overrides config)")
@click.option("--no-telegram", is_flag=True, help="Skip Telegram delivery")
@click.option("--no-email", is_flag=True, help="Skip email delivery")
@click.option("--telegram-only", is_flag=True, help="Only send via Telegram (skip HTML save)")
@click.option("--dry-run", is_flag=True, help="Process but don't save or send")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv)")
def main(
    config: Optional[Path],
    lookback: Optional[str],
    from_time: Optional[str],
    to_time: Optional[str],
    output: Optional[Path],
    channels: Optional[str],
    no_telegram: bool,
    no_email: bool,
    telegram_only: bool,
    dry_run: bool,
    verbose: int,
) -> None:
    """The Evening Telegram - Generate a newspaper-style digest from Telegram channels."""
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # Prepare CLI overrides
    overrides: dict[str, Any] = {}

    if lookback:
        overrides["period.lookback"] = lookback
    if from_time:
        overrides["period.from"] = from_time
    if to_time:
        overrides["period.to"] = to_time
    if output:
        overrides["output.html_path"] = str(output)
    if channels:
        overrides["channels"] = [ch.strip() for ch in channels.split(",")]
    if no_telegram:
        overrides["output.send_telegram"] = False
    if no_email:
        overrides["output.send_email"] = False
    if telegram_only:
        overrides["output.save_html"] = False
        overrides["output.send_telegram"] = True
        overrides["output.send_email"] = False

    # Run the main async function
    try:
        asyncio.run(run_evening_telegram(config, overrides, dry_run, verbose))
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=verbose >= 2)
        sys.exit(1)


async def run_evening_telegram(
    config_path: Optional[Path],
    overrides: dict[str, Any],
    dry_run: bool,
    verbose: int,
) -> None:
    """
    Main orchestration function for The Evening Telegram.

    Args:
        config_path: Path to configuration file
        overrides: CLI overrides
        dry_run: Whether to skip output
        verbose: Verbosity level from CLI
    """
    # Load configuration
    logger.info("Loading configuration")
    cfg = load_config(config_path, overrides)

    # Set application logging level based on CLI flags or config
    log_level = logging.WARNING
    if verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG
    elif cfg.logging:
        # Use config file setting if no -v flags provided
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        log_level = level_map.get(cfg.logging.level.upper(), logging.INFO)

    # Update structlog filtering level
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    # Initialize state manager
    state_manager = StateManager(cfg.state.db_path)
    await state_manager.initialize()

    # Determine time window and processed messages based on mode
    since_timestamp = None
    processed_ids: set[tuple[int, int]] = set()

    if cfg.state.mode == "since_last":
        last_run = await state_manager.get_last_successful_run()
        if last_run:
            since_timestamp = last_run[1]
            logger.info("Running in incremental mode", since=since_timestamp)

        # In since_last mode, skip already processed messages
        processed_ids = await state_manager.get_processed_message_ids()
        logger.info("Found previously processed messages", count=len(processed_ids))
    else:
        # In full mode, reprocess all messages in the time window
        logger.info("Running in full mode - will process all messages in lookback period")

    # Start new run
    # Use timezone-aware datetimes to match Telegram timestamps
    period_start = since_timestamp or datetime.now(timezone.utc)
    period_end = datetime.now(timezone.utc)
    run_id = await state_manager.start_run(period_start, period_end)

    try:
        # Fetch messages
        logger.info("Fetching messages", channel_count=len(cfg.channels))

        async with TelegramClientWrapper(cfg.telegram) as client:
            messages = await fetch_messages(
                client=client,
                channels=cfg.channels,
                period_config=cfg.period,
                processing_config=cfg.processing,
                since_timestamp=since_timestamp,
                processed_message_ids=processed_ids,
            )

        if not messages:
            logger.warning("No new messages to process")
            await state_manager.complete_run(run_id, 0)
            return

        logger.info("Fetched messages", count=len(messages))

        # Initialize LLM client
        token_tracker = TokenTracker()
        llm_client = LLMClient(cfg.llm, token_tracker)

        # Cluster messages
        logger.info("Clustering messages")
        clusters = await deduplicate_and_cluster(
            messages=messages,
            llm_client=llm_client,
            batch_size=cfg.processing.clustering_batch_size,
        )
        logger.info("Created topic clusters", count=len(clusters))

        # Filter clusters by minimum sources
        significant_clusters = [
            c for c in clusters if c.source_count >= cfg.processing.min_sources_for_article
        ]
        brief_clusters = [
            c for c in clusters if c.source_count < cfg.processing.min_sources_for_article
        ]

        logger.info(
            "Filtered clusters",
            significant=len(significant_clusters),
            brief=len(brief_clusters),
        )

        # Generate articles
        logger.info("Generating articles")
        articles: list[Article] = []

        for cluster in significant_clusters:
            article = await generate_article(
                cluster=cluster,
                language=cfg.output.language,
                newspaper_name=cfg.output.newspaper_name,
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
                language=cfg.output.language,
                newspaper_name=cfg.output.newspaper_name,
                llm_client=llm_client,
            )
            if article:
                articles.append(article)

        logger.info("Generated articles", count=len(articles))

        # Organize into sections
        sections_dict: dict[str, list[Article]] = {}
        for article in articles:
            if article.section not in sections_dict:
                sections_dict[article.section] = []
            sections_dict[article.section].append(article)

        # Create sections with order
        section_order = [
            "Breaking News",
            "Politics",
            "World",
            "Business",
            "Technology",
            "Science",
            "Culture",
            "Sports",
            "Opinion",
            "In Brief",
        ]

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
            title=cfg.output.newspaper_name,
            tagline=cfg.output.tagline,
            edition_date=datetime.now(timezone.utc),
            period_start=period_start,
            period_end=period_end,
            language=cfg.output.language,
            sections=sections,
            total_messages_processed=len(messages),
            total_channels=len(set(m.channel_id for m in messages)),
            token_usage=token_tracker.to_dict(),
        )

        # Output
        if dry_run:
            logger.warning("Dry run mode - skipping output")
        else:
            html_content = ""
            html_path_str = ""

            # Generate HTML
            if cfg.output.save_html:
                logger.info("Generating HTML")
                channel_info = [
                    {"username": ch, "title": ch} for ch in cfg.channels
                ]
                html_path_str = generate_html(newspaper, cfg.output.html_path, channel_info)
                logger.info("Saved HTML", path=html_path_str)

                # Read HTML content for email
                with open(html_path_str, "r", encoding="utf-8") as f:
                    html_content = f.read()

            # Send via Telegram
            if cfg.output.send_telegram and cfg.telegram.bot_token and cfg.telegram.report_chat_id:
                logger.info("Sending to Telegram")
                await send_telegram_report(
                    newspaper=newspaper,
                    bot_token=cfg.telegram.bot_token,
                    chat_id=cfg.telegram.report_chat_id,
                    html_path=html_path_str if html_path_str else None,
                )
                logger.info("Sent to Telegram")

            # Send via email
            if cfg.output.send_email and cfg.email:
                logger.info("Sending email")
                if not html_content:
                    # Generate HTML for email if not already generated
                    channel_info = [{"username": ch, "title": ch} for ch in cfg.channels]
                    from jinja2 import Environment, FileSystemLoader, select_autoescape

                    template_dir = Path(__file__).parent / "templates"
                    env = Environment(
                        loader=FileSystemLoader(template_dir),
                        autoescape=select_autoescape(["html", "xml"]),
                    )
                    template = env.get_template("newspaper.html")
                    html_content = template.render(
                        newspaper=newspaper, language=newspaper.language, channels=channel_info
                    )

                await send_email_report(newspaper, html_content, cfg.email)
                logger.info("Sent email")

        # Mark messages as processed
        message_ids = [(m.channel_id, m.message_id) for m in messages]
        await state_manager.mark_messages_processed(run_id, message_ids)

        # Complete run
        await state_manager.complete_run(run_id, len(messages))

        # Summary
        logger.info(
            "Completed successfully",
            articles=newspaper.total_articles,
            messages=newspaper.total_messages_processed,
            channels=newspaper.total_channels,
            llm_tokens=token_tracker.total_tokens,
        )

    except Exception as e:
        await state_manager.complete_run(run_id, 0, str(e))
        raise


if __name__ == "__main__":
    main()
