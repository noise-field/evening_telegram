"""Telegram bot for sending reports."""

import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

from ..models.data import Newspaper

logger = logging.getLogger(__name__)


async def send_telegram_report(
    newspaper: Newspaper,
    bot_token: str,
    chat_id: int,
    html_url: Optional[str] = None,
) -> None:
    """
    Send newspaper summary to Telegram chat.

    Args:
        newspaper: Generated newspaper
        bot_token: Telegram bot token
        chat_id: Target chat ID
        html_url: Optional URL to full HTML edition
    """
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
            "",
        ]
    )

    # Add HTML link if provided
    if html_url:
        message_parts.append(f'📖 <a href="{html_url}">Read full edition</a>')

    message_text = "\n".join(message_parts)

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        logger.info(f"Successfully sent report to Telegram chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram report: {e}")
        raise
