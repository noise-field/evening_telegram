"""Content filtering to remove trash messages (ads, greetings, etc)."""

import structlog

from ..llm.client import LLMClient
from ..llm.prompts import format_content_filter_prompt
from ..llm.schemas import ContentFilterResponse
from ..models.data import SourceMessage

logger = structlog.get_logger(__name__)


async def filter_messages(
    messages: list[SourceMessage],
    llm_client: LLMClient,
    batch_size: int = 100,
) -> tuple[list[SourceMessage], list[SourceMessage]]:
    """
    Filter messages to separate legitimate content from trash.

    This function uses the LLM to classify messages as either:
    - LEGITIMATE: News, commentary, announcements, opinions
    - TRASH: Ads, greetings, wishes, spam, social pleasantries

    Args:
        messages: List of source messages to filter
        llm_client: LLM client for API calls
        batch_size: Size of batches for large volumes

    Returns:
        Tuple of (legitimate_messages, trash_messages)
    """
    if not messages:
        return [], []

    logger.info("Filtering messages", count=len(messages))

    legitimate_messages = []
    trash_messages = []

    # Process messages in batches to avoid exceeding token limits
    batches = [messages[i : i + batch_size] for i in range(0, len(messages), batch_size)]

    for batch_idx, batch in enumerate(batches):
        logger.info(
            "Filtering batch",
            batch=batch_idx + 1,
            total=len(batches),
            batch_size=len(batch),
        )

        try:
            batch_legitimate, batch_trash = await _filter_batch(batch, llm_client)
            legitimate_messages.extend(batch_legitimate)
            trash_messages.extend(batch_trash)
        except Exception as e:
            logger.error("Failed to filter batch, keeping all messages", error=str(e))
            # On error, keep all messages as legitimate to avoid losing content
            legitimate_messages.extend(batch)

    logger.info(
        "Filtering complete",
        legitimate=len(legitimate_messages),
        trash=len(trash_messages),
        trash_percentage=round(len(trash_messages) / len(messages) * 100, 1) if messages else 0,
    )

    return legitimate_messages, trash_messages


async def _filter_batch(
    messages: list[SourceMessage],
    llm_client: LLMClient,
) -> tuple[list[SourceMessage], list[SourceMessage]]:
    """
    Filter a single batch of messages.

    Args:
        messages: List of source messages
        llm_client: LLM client

    Returns:
        Tuple of (legitimate_messages, trash_messages)
    """
    prompt_messages = format_content_filter_prompt(messages)

    if llm_client.config.structured_output:
        # Use structured output API with Pydantic schema
        response = await llm_client.chat_completion_structured(
            prompt_messages,
            response_format=ContentFilterResponse,
        )
        legitimate_ids = set(response.legitimate)
        trash_ids = set(response.trash)
    else:
        # Use traditional JSON mode
        response_dict = await llm_client.chat_completion_json(prompt_messages)
        legitimate_ids = set(response_dict.get("legitimate", []))
        trash_ids = set(response_dict.get("trash", []))

    legitimate_messages = []
    trash_messages = []

    for idx, msg in enumerate(messages, 1):
        if idx in legitimate_ids:
            legitimate_messages.append(msg)
        elif idx in trash_ids:
            trash_messages.append(msg)
        else:
            # If LLM didn't classify it, keep it as legitimate to be safe
            logger.warning(
                "Message not classified by LLM, keeping as legitimate",
                message_id=msg.message_id,
                channel=msg.channel_title,
            )
            legitimate_messages.append(msg)

    return legitimate_messages, trash_messages
