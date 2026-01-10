"""Message fetching from Telegram channels."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from dateutil import parser as date_parser
from telethon import TelegramClient
from telethon.tl.types import Channel, Message

from ..config.models import ProcessingConfig, ScheduleConfig
from ..models.data import MediaReference, SourceMessage

logger = structlog.get_logger(__name__)


async def fetch_messages(
    client: TelegramClient,
    channels: list[str],
    schedule_config: ScheduleConfig,
    processing_config: ProcessingConfig,
    since_timestamp: Optional[datetime] = None,
    processed_message_ids: Optional[set[tuple[int, int]]] = None,
) -> list[SourceMessage]:
    """
    Fetch messages from specified channels within time period.

    Args:
        client: Authenticated Telegram client
        channels: List of channel usernames or IDs
        schedule_config: Schedule configuration (contains lookback period)
        processing_config: Processing options
        since_timestamp: Override start time (for since_last mode)
        processed_message_ids: Set of (channel_id, message_id) already processed

    Returns:
        List of normalized source messages
    """
    if processed_message_ids is None:
        processed_message_ids = set()

    start_time, end_time = _determine_time_window(schedule_config, since_timestamp)
    logger.info("Fetching messages", start_time=start_time, end_time=end_time)

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
            logger.info("Fetched messages from channel", count=len(messages), channel=channel_identifier)
        except Exception as e:
            logger.warning("Failed to fetch messages from channel", channel=channel_identifier, error=str(e))
            continue

    # Apply max_messages limit if set
    if processing_config.max_messages > 0:
        all_messages = all_messages[: processing_config.max_messages]

    logger.info("Total messages fetched", count=len(all_messages))
    return all_messages


def _determine_time_window(
    schedule_config: ScheduleConfig,
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
        logger.debug("Using since_timestamp", timestamp=since_timestamp)
    elif schedule_config.from_time and schedule_config.to_time:
        start_time = date_parser.parse(schedule_config.from_time)
        end_time = date_parser.parse(schedule_config.to_time)
        # Ensure they're timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        logger.debug("Using explicit time range", start_time=start_time, end_time=end_time)
    else:
        lookback = schedule_config.lookback
        logger.debug("Parsing lookback", lookback=lookback)
        hours_match = re.match(r"(\d+)\s*hours?", lookback)
        days_match = re.match(r"(\d+)\s*days?", lookback)
        weeks_match = re.match(r"(\d+)\s*weeks?", lookback)

        if hours_match:
            delta = timedelta(hours=int(hours_match.group(1)))
            logger.debug("Matched hours", hours=hours_match.group(1))
        elif days_match:
            delta = timedelta(days=int(days_match.group(1)))
            logger.debug("Matched days", days=days_match.group(1))
        elif weeks_match:
            delta = timedelta(weeks=int(weeks_match.group(1)))
            logger.debug("Matched weeks", weeks=weeks_match.group(1))
        else:
            logger.warning("Could not parse lookback, defaulting to 24 hours", lookback=lookback)
            delta = timedelta(hours=24)

        start_time = end_time - delta
        logger.debug("Calculated time window", start_time=start_time, end_time=end_time, delta=str(delta))

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
    logger.debug("Starting to fetch messages from channel", channel=channel_identifier)
    logger.debug("Time window", start_time=start_time, end_time=end_time)

    entity = await client.get_entity(channel_identifier)

    if not isinstance(entity, Channel):
        logger.warning("Not a channel, skipping", channel=channel_identifier)
        return []

    logger.debug("Channel entity", title=entity.title, id=entity.id)
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
            logger.debug("Skipping non-Message object", position=messages_checked)
            continue

        # Log the message date for debugging
        if messages_checked <= 5 or messages_checked % 100 == 0:
            logger.debug("Checked messages", count=messages_checked, current_date=message.date)

        # When iterating from newest to oldest (default), stop when we hit messages before start_time
        if message.date < start_time:
            logger.debug("Message before start_time, stopping iteration",
                        message_id=message.id, message_date=message.date, start_time=start_time)
            break

        # Skip messages after end_time (shouldn't happen but be safe)
        if message.date > end_time:
            logger.debug("Message after end_time, skipping",
                        message_id=message.id, message_date=message.date, end_time=end_time)
            messages_skipped_time += 1
            continue

        # Skip if already processed
        if (entity.id, message.id) in processed_message_ids:
            logger.debug("Message already processed, skipping", message_id=message.id)
            messages_skipped_already_processed += 1
            continue

        # Skip if no text content
        text = message.text or message.message or ""
        if not text and message.media and hasattr(message.media, "caption"):
            text = message.media.caption or ""

        if not text:
            logger.debug("Message has no text content, skipping", message_id=message.id)
            messages_skipped_no_text += 1
            continue

        # Handle forwards
        is_forward = message.forward is not None
        if is_forward and not processing_config.include_external_forwards:
            if message.forward and hasattr(message.forward, "from_id"):
                logger.debug("Message is external forward, skipping", message_id=message.id)
                messages_skipped_external_forward += 1
                continue

        normalized_message = _normalize_message(message, entity)
        messages.append(normalized_message)

        if len(messages) <= 5:
            logger.debug("Added message to results", message_id=message.id, total=len(messages))

    logger.info("Channel stats",
                channel=channel_identifier,
                checked=messages_checked,
                added=len(messages),
                skipped_processed=messages_skipped_already_processed,
                skipped_no_text=messages_skipped_no_text,
                skipped_external=messages_skipped_external_forward,
                skipped_time=messages_skipped_time)

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
