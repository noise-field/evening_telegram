"""Telegram client wrapper using Telethon."""

from pathlib import Path

import structlog
from telethon import TelegramClient

from ..config.models import TelegramConfig

logger = structlog.get_logger(__name__)


class TelegramClientWrapper:
    """Wrapper around Telethon client with authentication."""

    def __init__(self, config: TelegramConfig):
        """
        Initialize Telegram client.

        Args:
            config: Telegram configuration
        """
        self.config = config
        session_path = Path(config.session_file).expanduser()
        session_path.parent.mkdir(parents=True, exist_ok=True)

        self.client = TelegramClient(
            str(session_path),
            config.api_id,
            config.api_hash,
        )

    async def __aenter__(self) -> TelegramClient:
        """Async context manager entry."""
        await self.client.start(phone=self.config.phone)
        logger.info("Telegram client started successfully")
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Async context manager exit."""
        await self.client.disconnect()
        logger.info("Telegram client disconnected")
