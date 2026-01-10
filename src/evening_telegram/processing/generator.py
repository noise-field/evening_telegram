"""Article generation from message clusters."""

import logging
import uuid
from datetime import datetime

from ..llm.client import LLMClient
from ..llm.prompts import format_article_generation_prompt
from ..models.data import Article, ArticleType, MessageCluster

logger = logging.getLogger(__name__)


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
    logger.info(f"Generating {cluster.suggested_type.value} article for: {cluster.topic_summary}")

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
        logger.error(f"Failed to generate article for cluster {cluster.cluster_id}: {e}")
        return None

    # Extract article components
    headline = response.get("headline", "Untitled")
    subheadline = response.get("subheadline")
    body = response.get("body", "")
    stance_summary = response.get("stance_summary")

    if not body:
        logger.warning(f"Empty article body for cluster {cluster.cluster_id}")
        return None

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

    logger.info(f"Generated article: {headline}")
    return article
