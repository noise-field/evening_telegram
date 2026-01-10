"""CLI interface for The Evening Telegram."""

import asyncio
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from .config import load_config
from .config.models import Config
from .llm.client import LLMClient
from .llm.tracker import TokenTracker
from .models.data import Article, ArticleType, Newspaper, NewspaperSection
from .output import generate_html, send_email_report
from .processing import deduplicate_and_cluster, generate_article
from .state import StateManager
from .telegram import TelegramClientWrapper, fetch_messages, send_telegram_report

console = Console()


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
    # Configure root logger at WARNING to suppress third-party package logs
    # This must be done early before any other logging happens
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
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
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose >= 2:
            console.print_exception()
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
    console.print("[bold]Loading configuration...[/bold]")
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

    # Set our application's logger to the desired level
    app_logger = logging.getLogger("evening_telegram")
    app_logger.setLevel(log_level)

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
            console.print(f"[dim]Running in incremental mode since {since_timestamp}[/dim]")

        # In since_last mode, skip already processed messages
        processed_ids = await state_manager.get_processed_message_ids()
        console.print(f"[dim]Found {len(processed_ids)} previously processed messages[/dim]")
    else:
        # In full mode, reprocess all messages in the time window
        console.print(f"[dim]Running in full mode - will process all messages in lookback period[/dim]")

    # Start new run
    # Use timezone-aware datetimes to match Telegram timestamps
    period_start = since_timestamp or datetime.now(timezone.utc)
    period_end = datetime.now(timezone.utc)
    run_id = await state_manager.start_run(period_start, period_end)

    try:
        # Fetch messages
        console.print(f"[bold]Fetching messages from {len(cfg.channels)} channels...[/bold]")

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
            console.print("[yellow]No new messages to process[/yellow]")
            await state_manager.complete_run(run_id, 0)
            return

        console.print(f"[green]Fetched {len(messages)} messages[/green]")

        # Initialize LLM client
        token_tracker = TokenTracker()
        llm_client = LLMClient(cfg.llm, token_tracker)

        # Cluster messages
        console.print("[bold]Clustering messages...[/bold]")
        clusters = await deduplicate_and_cluster(
            messages=messages,
            llm_client=llm_client,
            batch_size=cfg.processing.clustering_batch_size,
        )
        console.print(f"[green]Created {len(clusters)} topic clusters[/green]")

        # Filter clusters by minimum sources
        significant_clusters = [
            c for c in clusters if c.source_count >= cfg.processing.min_sources_for_article
        ]
        brief_clusters = [
            c for c in clusters if c.source_count < cfg.processing.min_sources_for_article
        ]

        console.print(
            f"[dim]{len(significant_clusters)} significant topics, {len(brief_clusters)} brief items[/dim]"
        )

        # Generate articles
        console.print("[bold]Generating articles...[/bold]")
        articles: list[Article] = []

        with console.status("[bold]Writing articles...") as status:
            for cluster in significant_clusters:
                article = await generate_article(
                    cluster=cluster,
                    language=cfg.output.language,
                    newspaper_name=cfg.output.newspaper_name,
                    llm_client=llm_client,
                )
                if article:
                    articles.append(article)
                    status.update(f"[bold]Generated {len(articles)} articles...")

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

        console.print(f"[green]Generated {len(articles)} articles[/green]")

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
            console.print("[yellow]Dry run mode - skipping output[/yellow]")
        else:
            html_content = ""
            html_path_str = ""

            # Generate HTML
            if cfg.output.save_html:
                console.print("[bold]Generating HTML...[/bold]")
                channel_info = [
                    {"username": ch, "title": ch} for ch in cfg.channels
                ]
                html_path_str = generate_html(newspaper, cfg.output.html_path, channel_info)
                console.print(f"[green]Saved HTML to {html_path_str}[/green]")

                # Read HTML content for email
                with open(html_path_str, "r", encoding="utf-8") as f:
                    html_content = f.read()

            # Send via Telegram
            if cfg.output.send_telegram and cfg.telegram.bot_token and cfg.telegram.report_chat_id:
                console.print("[bold]Sending to Telegram...[/bold]")
                await send_telegram_report(
                    newspaper=newspaper,
                    bot_token=cfg.telegram.bot_token,
                    chat_id=cfg.telegram.report_chat_id,
                    html_path=html_path_str if html_path_str else None,
                )
                console.print("[green]Sent to Telegram[/green]")

            # Send via email
            if cfg.output.send_email and cfg.email:
                console.print("[bold]Sending email...[/bold]")
                if not html_content:
                    # Generate HTML for email if not already generated
                    channel_info = [{"username": ch, "title": ch} for ch in cfg.channels]
                    from .output.html import generate_html as gen_html_string
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
                console.print("[green]Sent email[/green]")

        # Mark messages as processed
        message_ids = [(m.channel_id, m.message_id) for m in messages]
        await state_manager.mark_messages_processed(run_id, message_ids)

        # Complete run
        await state_manager.complete_run(run_id, len(messages))

        # Summary
        console.print("\n[bold green]✓ Completed successfully[/bold green]")
        console.print(f"  Articles: {newspaper.total_articles}")
        console.print(f"  Messages: {newspaper.total_messages_processed}")
        console.print(f"  Channels: {newspaper.total_channels}")
        console.print(f"  LLM tokens: {token_tracker.total_tokens:,}")

    except Exception as e:
        await state_manager.complete_run(run_id, 0, str(e))
        raise


if __name__ == "__main__":
    main()
