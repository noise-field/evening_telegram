"""Telegram bot for sending reports."""

from pathlib import Path
from typing import Optional

import structlog
from telegram import Bot
from telegram.constants import ParseMode

from ..models.data import Newspaper

logger = structlog.get_logger(__name__)


async def send_telegram_report(
    newspaper: Newspaper,
    bot_token: str,
    chat_id: int | list[int],
    html_path: Optional[str] = None,
) -> None:
    """
    Send newspaper summary to Telegram chat(s).

    Args:
        newspaper: Generated newspaper
        bot_token: Telegram bot token
        chat_id: Target chat ID or list of chat IDs
        html_path: Optional path to HTML file to attach
    """
    # Normalize chat_id to a list
    chat_ids = [chat_id] if isinstance(chat_id, int) else chat_id

    bot = Bot(token=bot_token)

    message_parts = [
        f"📰 <b>{newspaper.title}</b>",
        f"{newspaper.edition_date.strftime('%B %d, %Y')}",
        "",
        "<b>Top Stories:</b>",
        "",
    ]

    # Add section summaries
    for section in newspaper.sections:
        if not section.articles:
            continue

        message_parts.append(f"<b>{section.name}</b>")

        # List top 3 articles per section
        for article in section.articles[:3]:
            message_parts.append(f"• {article.headline}")

        message_parts.append("")

    # Add statistics
    message_parts.extend(
        [
            f"📊 {newspaper.total_articles} articles from {newspaper.total_channels} channels",
        ]
    )

    message_text = "\n".join(message_parts)

    # Send to all chat IDs
    for target_chat_id in chat_ids:
        try:
            # Send the summary message
            await bot.send_message(
                chat_id=target_chat_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            logger.info("Successfully sent report summary to Telegram", chat_id=target_chat_id)

            # Send HTML file as document attachment if provided
            if html_path and Path(html_path).exists():
                filename = Path(html_path).name
                with open(html_path, "rb") as html_file:
                    await bot.send_document(
                        chat_id=target_chat_id,
                        document=html_file,
                        filename=filename,
                        caption="📖 Full edition",
                    )
                logger.info(
                    "Successfully sent HTML file to Telegram",
                    chat_id=target_chat_id,
                    filename=filename,
                )

        except Exception as e:
            logger.error(
                "Failed to send Telegram report to chat",
                chat_id=target_chat_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue to next chat ID instead of raising
