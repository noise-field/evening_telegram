"""Article generation from message clusters."""

import re
import uuid
from datetime import datetime

import structlog

from ..llm.client import LLMClient
from ..llm.prompts import format_article_generation_prompt
from ..models.data import Article, MessageCluster, SourceMessage

logger = structlog.get_logger(__name__)


def _make_sources_clickable(body: str, sources: list[SourceMessage]) -> str:
    """
    Convert [Source: Channel Name] citations in article body to clickable links.

    Args:
        body: HTML body text with [Source: X] citations
        sources: List of source messages for this article

    Returns:
        HTML body with clickable source citations
    """
    # Build a mapping of channel titles to their first message link
    # We use the first (earliest) message from each channel as the link target
    channel_links: dict[str, str] = {}

    for source in sources:
        if source.channel_title not in channel_links:
            # Use the telegram_link from SourceMessage which points to the specific message
            channel_links[source.channel_title] = source.telegram_link

    # Replace [Source: Channel Name] with clickable links
    # Pattern: [Source: Channel Name]
    # We need to escape channel names for regex and try each one
    modified_body = body

    for channel_title, message_url in channel_links.items():
        # Escape special regex characters in channel title
        escaped_title = re.escape(channel_title)
        # Pattern to match [Source: Channel Name]
        pattern = rf'\[Source:\s*{escaped_title}\]'
        # Replacement: clickable link styled similarly to the existing source links
        replacement = f'<a href="{message_url}" target="_blank" rel="noopener" style="color: #326891; text-decoration: none; border-bottom: 1px dotted #326891;">[Source: {channel_title}]</a>'
        modified_body = re.sub(pattern, replacement, modified_body, flags=re.IGNORECASE)

    return modified_body


async def generate_article(
    cluster: MessageCluster,
    language: str,
    newspaper_name: str,
    llm_client: LLMClient,
) -> Article | None:
    """
    Generate a newspaper article from a message cluster.

    Args:
        cluster: Message cluster to generate article from
        language: Target language for article
        newspaper_name: Name of the newspaper
        llm_client: LLM client for API calls

    Returns:
        Generated Article or None if generation fails
    """
    logger.info("Generating article",
                article_type=cluster.suggested_type.value,
                topic=cluster.topic_summary)

    prompt_messages = format_article_generation_prompt(
        cluster_messages=cluster.messages,
        article_type=cluster.suggested_type,
        section=cluster.suggested_section,
        language=language,
        newspaper_name=newspaper_name,
        topic_summary=cluster.topic_summary,
    )

    try:
        response = await llm_client.chat_completion_json(prompt_messages)
    except Exception as e:
        logger.error("Failed to generate article",
                    cluster_id=cluster.cluster_id,
                    error=str(e))
        return None

    # Extract article components
    headline = response.get("headline", "Untitled")
    subheadline = response.get("subheadline")
    body = response.get("body", "")
    stance_summary = response.get("stance_summary")

    if not body:
        logger.warning("Empty article body", cluster_id=cluster.cluster_id)
        return None

    # Post-process body to make [Source: X] citations clickable
    body = _make_sources_clickable(body, cluster.messages)

    article = Article(
        article_id=str(uuid.uuid4()),
        headline=headline,
        subheadline=subheadline,
        body=body,
        article_type=cluster.suggested_type,
        section=cluster.suggested_section,
        source_clusters=[cluster],
        stance_summary=stance_summary,
        generated_at=datetime.now(),
    )

    logger.info("Generated article", headline=headline)
    return article
