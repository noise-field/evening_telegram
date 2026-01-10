"""Message fetching from Telegram channels."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from dateutil import parser as date_parser
from telethon import TelegramClient
from telethon.tl.types import Channel, Message

from ..config.models import PeriodConfig, ProcessingConfig
from ..models.data import MediaReference, SourceMessage

logger = structlog.get_logger(__name__)


async def fetch_messages(
    client: TelegramClient,
    channels: list[str],
    period_config: PeriodConfig,
    processing_config: ProcessingConfig,
    since_timestamp: Optional[datetime] = None,
    processed_message_ids: Optional[set[tuple[int, int]]] = None,
) -> list[SourceMessage]:
    """
    Fetch messages from specified channels within time period.

    Args:
        client: Authenticated Telegram client
        channels: List of channel usernames or IDs
        period_config: Time period configuration
        processing_config: Processing options
        since_timestamp: Override start time (for since_last mode)
        processed_message_ids: Set of (channel_id, message_id) already processed

    Returns:
        List of normalized source messages
    """
    if processed_message_ids is None:
        processed_message_ids = set()

    start_time, end_time = _determine_time_window(period_config, since_timestamp)
    logger.info(f"Fetching messages from {start_time} to {end_time}")

    all_messages: list[SourceMessage] = []

    for channel_identifier in channels:
        try:
            messages = await _fetch_channel_messages(
                client,
                channel_identifier,
                start_time,
                end_time,
                processing_config,
                processed_message_ids,
            )
            all_messages.extend(messages)
            logger.info(f"Fetched {len(messages)} messages from {channel_identifier}")
        except Exception as e:
            logger.warning(f"Failed to fetch messages from {channel_identifier}: {e}")
            continue

    # Apply max_messages limit if set
    if processing_config.max_messages > 0:
        all_messages = all_messages[: processing_config.max_messages]

    logger.info(f"Total messages fetched: {len(all_messages)}")
    return all_messages


def _determine_time_window(
    period_config: PeriodConfig,
    since_timestamp: Optional[datetime],
) -> tuple[datetime, datetime]:
    """Determine the time window for message fetching."""
    # CRITICAL FIX: Use timezone-aware datetime to match Telegram message timestamps
    end_time = datetime.now(timezone.utc)

    if since_timestamp is not None:
        start_time = since_timestamp
        # Ensure it's timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        logger.debug(f"Using since_timestamp: {since_timestamp}")
    elif period_config.from_time and period_config.to_time:
        start_time = date_parser.parse(period_config.from_time)
        end_time = date_parser.parse(period_config.to_time)
        # Ensure they're timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        logger.debug(f"Using explicit time range: {start_time} to {end_time}")
    else:
        lookback = period_config.lookback
        logger.debug(f"Parsing lookback: '{lookback}'")
        hours_match = re.match(r"(\d+)\s*hours?", lookback)
        days_match = re.match(r"(\d+)\s*days?", lookback)
        weeks_match = re.match(r"(\d+)\s*weeks?", lookback)

        if hours_match:
            delta = timedelta(hours=int(hours_match.group(1)))
            logger.debug(f"Matched hours: {hours_match.group(1)}")
        elif days_match:
            delta = timedelta(days=int(days_match.group(1)))
            logger.debug(f"Matched days: {days_match.group(1)}")
        elif weeks_match:
            delta = timedelta(weeks=int(weeks_match.group(1)))
            logger.debug(f"Matched weeks: {weeks_match.group(1)}")
        else:
            logger.warning(f"Could not parse lookback '{lookback}', defaulting to 24 hours")
            delta = timedelta(hours=24)

        start_time = end_time - delta
        logger.debug(f"Calculated time window: {start_time} to {end_time} (delta: {delta})")

    return start_time, end_time


async def _fetch_channel_messages(
    client: TelegramClient,
    channel_identifier: str,
    start_time: datetime,
    end_time: datetime,
    processing_config: ProcessingConfig,
    processed_message_ids: set[tuple[int, int]],
) -> list[SourceMessage]:
    """Fetch messages from a single channel."""
    logger.debug(f"Starting to fetch messages from {channel_identifier}")
    logger.debug(f"Time window: {start_time} to {end_time}")

    entity = await client.get_entity(channel_identifier)

    if not isinstance(entity, Channel):
        logger.warning(f"{channel_identifier} is not a channel, skipping")
        return []

    logger.debug(f"Channel entity: {entity.title} (ID: {entity.id})")
    messages: list[SourceMessage] = []

    messages_checked = 0
    messages_skipped_already_processed = 0
    messages_skipped_no_text = 0
    messages_skipped_external_forward = 0
    messages_skipped_time = 0

    # CRITICAL FIX: Don't use reverse=True with offset_date.
    # Instead, iterate from newest (default) and stop when we hit messages older than start_time.
    # This is more efficient and correct.
    logger.debug("Starting iteration from most recent messages")

    async for message in client.iter_messages(entity):
        messages_checked += 1

        if not isinstance(message, Message):
            logger.debug(f"Skipping non-Message object at position {messages_checked}")
            continue

        # Log the message date for debugging
        if messages_checked <= 5 or messages_checked % 100 == 0:
            logger.debug(f"Checked {messages_checked} messages, current message date: {message.date}")

        # When iterating from newest to oldest (default), stop when we hit messages before start_time
        if message.date < start_time:
            logger.debug(f"Message {message.id} date {message.date} is before start_time {start_time}, stopping iteration")
            break

        # Skip messages after end_time (shouldn't happen but be safe)
        if message.date > end_time:
            logger.debug(f"Message {message.id} date {message.date} is after end_time {end_time}, skipping")
            messages_skipped_time += 1
            continue

        # Skip if already processed
        if (entity.id, message.id) in processed_message_ids:
            logger.debug(f"Message {message.id} already processed, skipping")
            messages_skipped_already_processed += 1
            continue

        # Skip if no text content
        text = message.text or message.message or ""
        if not text and message.media and hasattr(message.media, "caption"):
            text = message.media.caption or ""

        if not text:
            logger.debug(f"Message {message.id} has no text content, skipping")
            messages_skipped_no_text += 1
            continue

        # Handle forwards
        is_forward = message.forward is not None
        if is_forward and not processing_config.include_external_forwards:
            if message.forward and hasattr(message.forward, "from_id"):
                logger.debug(f"Message {message.id} is external forward, skipping")
                messages_skipped_external_forward += 1
                continue

        normalized_message = _normalize_message(message, entity)
        messages.append(normalized_message)

        if len(messages) <= 5:
            logger.debug(f"Added message {message.id} to results (total: {len(messages)})")

    logger.info(f"Channel {channel_identifier} stats:")
    logger.info(f"  - Total messages checked: {messages_checked}")
    logger.info(f"  - Messages added: {len(messages)}")
    logger.info(f"  - Skipped (already processed): {messages_skipped_already_processed}")
    logger.info(f"  - Skipped (no text): {messages_skipped_no_text}")
    logger.info(f"  - Skipped (external forward): {messages_skipped_external_forward}")
    logger.info(f"  - Skipped (time filter): {messages_skipped_time}")

    return messages


def _normalize_message(message: Message, channel: Channel) -> SourceMessage:
    """Convert Telegram message to normalized SourceMessage."""
    text = message.text or message.message or ""

    # Handle forwards
    is_forward = message.forward is not None
    forward_from_channel = None
    forward_from_title = None
    forward_date = None

    if is_forward and message.forward:
        if hasattr(message.forward, "from_id") and message.forward.from_id:
            forward_from_channel = str(message.forward.from_id)
        if hasattr(message.forward, "chat") and message.forward.chat:
            forward_from_title = getattr(message.forward.chat, "title", "Unknown")
        forward_date = message.forward.date

    # Extract media references
    media = _extract_media_references(message)

    # Extract URLs
    external_links = _extract_urls(text)

    channel_username = f"@{channel.username}" if channel.username else str(channel.id)

    return SourceMessage(
        message_id=message.id,
        channel_id=channel.id,
        channel_username=channel_username,
        channel_title=channel.title or channel_username,
        timestamp=message.date,
        text=text,
        is_forward=is_forward,
        forward_from_channel=forward_from_channel,
        forward_from_title=forward_from_title,
        forward_date=forward_date,
        media=media,
        external_links=external_links,
    )


def _extract_media_references(message: Message) -> list[MediaReference]:
    """Extract media references from a message."""
    media_refs: list[MediaReference] = []

    if not message.media:
        return media_refs

    media_type = "unknown"
    if hasattr(message.media, "photo"):
        media_type = "photo"
    elif hasattr(message.media, "document"):
        media_type = "document"
    elif hasattr(message.media, "video"):
        media_type = "video"

    caption = getattr(message.media, "caption", None)

    # Construct telegram link for media
    telegram_url = f"https://t.me/c/{message.peer_id.channel_id}/{message.id}"

    media_refs.append(
        MediaReference(
            type=media_type,
            telegram_url=telegram_url,
            caption=caption,
        )
    )

    return media_refs


def _extract_urls(text: str) -> list[str]:
    """Extract URLs from message text."""
    url_pattern = r"https?://[^\s]+"
    return re.findall(url_pattern, text)
