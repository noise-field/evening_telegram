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
from .config.models import Config, SubscriptionConfig
from .daemon import EveningTelegramDaemon
from .llm.client import LLMClient
from .llm.tracker import TokenTracker
from .models.data import Article, ArticleType, Newspaper, NewspaperSection
from .output import generate_html, send_email_report
from .processing import deduplicate_and_cluster, generate_article
from .scheduler import SubscriptionScheduler
from .state import StateManager
from .telegram import TelegramClientWrapper, fetch_messages, send_telegram_report

logger = structlog.get_logger()


@click.group()
def cli():
    """The Evening Telegram - Generate newspaper-style digests from Telegram channels."""
    pass


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv)")
def daemon(config: Optional[Path], verbose: int) -> None:
    """Run in daemon mode with scheduled subscriptions."""
    try:
        asyncio.run(run_daemon(config, verbose))
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error in daemon", error=str(e), exc_info=verbose >= 2)
        sys.exit(1)


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--subscription",
    "-s",
    required=True,
    help="Subscription ID to run",
)
@click.option("--lookback", help="Override time lookback period (e.g., '24 hours', '7 days')")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Override HTML output path")
@click.option("--no-telegram", is_flag=True, help="Skip Telegram delivery")
@click.option("--no-email", is_flag=True, help="Skip email delivery")
@click.option("--dry-run", is_flag=True, help="Process but don't save or send")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv)")
def run(
    config: Optional[Path],
    subscription: str,
    lookback: Optional[str],
    output: Optional[Path],
    no_telegram: bool,
    no_email: bool,
    dry_run: bool,
    verbose: int,
) -> None:
    """Run a specific subscription once."""
    try:
        asyncio.run(
            run_single_subscription(
                config, subscription, lookback, output, no_telegram, no_email, dry_run, verbose
            )
        )
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=verbose >= 2)
        sys.exit(1)


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--dry-run", is_flag=True, help="Process but don't save or send")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv)")
def run_all(config: Optional[Path], dry_run: bool, verbose: int) -> None:
    """Run all subscriptions once."""
    try:
        asyncio.run(run_all_subscriptions(config, dry_run, verbose))
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=verbose >= 2)
        sys.exit(1)


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
def list_subscriptions(config: Optional[Path]) -> None:
    """List all configured subscriptions."""
    try:
        cfg = load_config(config, {})

        click.echo("\nConfigured Subscriptions:")
        click.echo("=" * 60)

        for sub_id, sub_config in cfg.subscriptions.items():
            click.echo(f"\nID: {sub_id}")
            click.echo(f"Name: {sub_config.name}")
            click.echo(f"Channels: {', '.join(sub_config.channels)}")
            click.echo(f"Lookback: {sub_config.schedule.lookback}")

            if sub_config.schedule.times:
                click.echo(f"Schedule: Daily at {', '.join(sub_config.schedule.times)}")
            elif sub_config.schedule.day_of_week is not None:
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                day_name = days[sub_config.schedule.day_of_week]
                click.echo(f"Schedule: Weekly on {day_name} at {sub_config.schedule.time}")

            click.echo(f"Output: {sub_config.output.newspaper_name}")

        click.echo("\n" + "=" * 60)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--subscription",
    "-s",
    required=True,
    help="Subscription ID to test",
)
@click.option(
    "--count",
    "-n",
    default=5,
    help="Number of next run times to show",
)
def test_schedule(config: Optional[Path], subscription: str, count: int) -> None:
    """Test schedule and show next execution times."""
    try:
        cfg = load_config(config, {})

        if subscription not in cfg.subscriptions:
            click.echo(f"Error: Subscription '{subscription}' not found", err=True)
            sys.exit(1)

        sub_config = cfg.subscriptions[subscription]

        # Create a temporary scheduler
        scheduler = SubscriptionScheduler(
            subscription_id=subscription,
            subscription_name=sub_config.name,
            schedule=sub_config.schedule,
            callback=lambda: None,
        )

        next_runs = scheduler.get_next_n_run_times(count)

        click.echo(f"\nSchedule Test for: {sub_config.name}")
        click.echo("=" * 60)
        click.echo(f"Lookback: {sub_config.schedule.lookback}")

        if sub_config.schedule.times:
            click.echo(f"Daily at: {', '.join(sub_config.schedule.times)}")
        elif sub_config.schedule.day_of_week is not None:
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            day_name = days[sub_config.schedule.day_of_week]
            click.echo(f"Weekly: {day_name} at {sub_config.schedule.time}")

        click.echo(f"\nNext {count} execution times:")
        click.echo("-" * 60)

        for i, run_time in enumerate(next_runs, 1):
            local_time = run_time.astimezone()
            click.echo(f"{i}. {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        click.echo("=" * 60 + "\n")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def run_daemon(config_path: Optional[Path], verbose: int) -> None:
    """Run the daemon with all subscriptions."""
    # Configure logging
    configure_logging(verbose)

    logger.info("Loading configuration")
    cfg = load_config(config_path, {})

    # Set logging level from config
    set_logging_level(cfg, verbose)

    if not cfg.subscriptions:
        logger.error("No subscriptions configured")
        sys.exit(1)

    # Create and start daemon
    daemon_instance = EveningTelegramDaemon(cfg)

    # Get the current event loop and set up signal handlers
    loop = asyncio.get_running_loop()
    daemon_instance.setup_signal_handlers(loop)

    await daemon_instance.start()


async def run_single_subscription(
    config_path: Optional[Path],
    subscription_id: str,
    lookback: Optional[str],
    output: Optional[Path],
    no_telegram: bool,
    no_email: bool,
    dry_run: bool,
    verbose: int,
) -> None:
    """Run a single subscription once."""
    # Configure logging
    configure_logging(verbose)

    logger.info("Loading configuration")
    cfg = load_config(config_path, {})

    # Set logging level from config
    set_logging_level(cfg, verbose)

    if subscription_id not in cfg.subscriptions:
        logger.error("Subscription not found", subscription_id=subscription_id)
        sys.exit(1)

    sub_config = cfg.subscriptions[subscription_id]

    # Apply overrides
    if lookback:
        sub_config.schedule.lookback = lookback
    if output:
        sub_config.output.html_path = output
    if no_telegram:
        sub_config.output.send_telegram = False
    if no_email:
        sub_config.output.send_email = False

    # Create daemon and run the subscription once
    daemon_instance = EveningTelegramDaemon(cfg)
    await daemon_instance.initialize()

    if dry_run:
        logger.warning("Dry run mode - skipping output")
        # TODO: Implement dry run mode
        logger.error("Dry run mode not yet implemented")
        return

    await daemon_instance.run_subscription(subscription_id, sub_config)


async def run_all_subscriptions(
    config_path: Optional[Path], dry_run: bool, verbose: int
) -> None:
    """Run all subscriptions once."""
    # Configure logging
    configure_logging(verbose)

    logger.info("Loading configuration")
    cfg = load_config(config_path, {})

    # Set logging level from config
    set_logging_level(cfg, verbose)

    if not cfg.subscriptions:
        logger.error("No subscriptions configured")
        sys.exit(1)

    # Create daemon
    daemon_instance = EveningTelegramDaemon(cfg)
    await daemon_instance.initialize()

    if dry_run:
        logger.warning("Dry run mode - skipping output")

    # Run each subscription
    for sub_id, sub_config in cfg.subscriptions.items():
        logger.info("Running subscription", subscription_id=sub_id, name=sub_config.name)

        try:
            await daemon_instance.run_subscription(sub_id, sub_config)
        except Exception as e:
            logger.error(
                "Failed to run subscription",
                subscription_id=sub_id,
                error=str(e),
                exc_info=True,
            )


def configure_logging(verbose: int) -> None:
    """Configure structlog with initial settings."""
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


def set_logging_level(cfg: Config, verbose: int) -> None:
    """Set logging level based on CLI flags or config."""
    log_level = logging.WARNING

    if verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG
    elif cfg.logging:
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        log_level = level_map.get(cfg.logging.level.upper(), logging.INFO)

    # Reconfigure structlog with proper log level
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if log_level <= logging.INFO else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
