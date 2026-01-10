"""LLM-based message deduplication and clustering."""

import logging
from typing import Any

from ..llm.client import LLMClient
from ..llm.prompts import format_clustering_prompt, format_merge_clusters_prompt
from ..models.data import ArticleType, MessageCluster, SourceMessage

logger = logging.getLogger(__name__)


async def deduplicate_and_cluster(
    messages: list[SourceMessage],
    llm_client: LLMClient,
    batch_size: int = 50,
) -> list[MessageCluster]:
    """
    Use LLM to identify duplicate content and cluster into topics.

    Args:
        messages: List of source messages to cluster
        llm_client: LLM client for API calls
        batch_size: Size of batches for large volumes

    Returns:
        List of message clusters
    """
    if not messages:
        return []

    logger.info(f"Clustering {len(messages)} messages...")

    if len(messages) <= batch_size:
        # Process all messages in single batch
        clusters = await _cluster_batch(messages, llm_client)
    else:
        # Process in multiple batches and merge
        clusters = await _process_large_batch(messages, llm_client, batch_size)

    logger.info(f"Created {len(clusters)} clusters")
    return clusters


async def _cluster_batch(
    messages: list[SourceMessage],
    llm_client: LLMClient,
) -> list[MessageCluster]:
    """
    Cluster a single batch of messages.

    Args:
        messages: List of source messages
        llm_client: LLM client

    Returns:
        List of message clusters
    """
    prompt_messages = format_clustering_prompt(messages)

    try:
        response = await llm_client.chat_completion_json(prompt_messages)
    except Exception as e:
        logger.error(f"Failed to cluster messages: {e}")
        # Fallback: create one cluster per message
        return _create_fallback_clusters(messages)

    topics = response.get("topics", [])
    clusters = []

    for topic in topics:
        cluster = _create_cluster_from_topic(topic, messages)
        if cluster:
            clusters.append(cluster)

    return clusters


async def _process_large_batch(
    messages: list[SourceMessage],
    llm_client: LLMClient,
    batch_size: int,
) -> list[MessageCluster]:
    """
    Process large message volumes by batching and merging.

    Args:
        messages: List of source messages
        llm_client: LLM client
        batch_size: Size of each batch

    Returns:
        Merged list of message clusters
    """
    # Split into batches
    batches = [messages[i : i + batch_size] for i in range(0, len(messages), batch_size)]
    logger.info(f"Processing {len(batches)} batches of ~{batch_size} messages each")

    # Process each batch
    all_clusters: list[MessageCluster] = []
    for batch_idx, batch in enumerate(batches):
        logger.info(f"Processing batch {batch_idx + 1}/{len(batches)}")
        batch_clusters = await _cluster_batch(batch, llm_client)

        # Prefix cluster IDs with batch number
        for cluster in batch_clusters:
            cluster.cluster_id = f"batch{batch_idx}_{cluster.cluster_id}"

        all_clusters.extend(batch_clusters)

    # If only one batch, return as is
    if len(batches) == 1:
        return all_clusters

    # Merge related clusters across batches
    logger.info("Merging clusters across batches...")
    merged_clusters = await _merge_clusters(all_clusters, llm_client)

    return merged_clusters


async def _merge_clusters(
    clusters: list[MessageCluster],
    llm_client: LLMClient,
) -> list[MessageCluster]:
    """
    Merge related clusters from different batches.

    Args:
        clusters: List of clusters to potentially merge
        llm_client: LLM client

    Returns:
        Merged list of clusters
    """
    # Create cluster summaries for LLM
    cluster_summaries = [
        {
            "cluster_id": c.cluster_id,
            "summary": c.topic_summary,
            "section": c.suggested_section,
            "type": c.suggested_type.value,
        }
        for c in clusters
    ]

    prompt_messages = format_merge_clusters_prompt(cluster_summaries)

    try:
        response = await llm_client.chat_completion_json(prompt_messages)
    except Exception as e:
        logger.warning(f"Failed to merge clusters: {e}, using unmerged clusters")
        return clusters

    # Build cluster lookup
    cluster_map = {c.cluster_id: c for c in clusters}

    # Apply merges
    merges = response.get("merges", [])
    unchanged = response.get("unchanged", [])

    result_clusters: list[MessageCluster] = []

    # Process merges
    for merge in merges:
        keep_id = merge["keep"]
        merge_ids = merge["merge_into_it"]

        if keep_id not in cluster_map:
            continue

        main_cluster = cluster_map[keep_id]

        # Merge messages from other clusters
        for merge_id in merge_ids:
            if merge_id in cluster_map:
                main_cluster.messages.extend(cluster_map[merge_id].messages)

        # Update summary
        main_cluster.topic_summary = merge.get("combined_summary", main_cluster.topic_summary)

        result_clusters.append(main_cluster)

    # Add unchanged clusters
    for cluster_id in unchanged:
        if cluster_id in cluster_map:
            result_clusters.append(cluster_map[cluster_id])

    return result_clusters


def _create_cluster_from_topic(
    topic: dict[str, Any],
    messages: list[SourceMessage],
) -> MessageCluster | None:
    """
    Create a MessageCluster from LLM topic response.

    Args:
        topic: Topic dict from LLM response
        messages: Full list of messages

    Returns:
        MessageCluster or None if invalid
    """
    message_ids = topic.get("message_ids", [])
    if not message_ids:
        return None

    # Get messages by index (1-indexed in prompt)
    cluster_messages = []
    for msg_idx in message_ids:
        if 1 <= msg_idx <= len(messages):
            cluster_messages.append(messages[msg_idx - 1])

    if not cluster_messages:
        return None

    # Parse article type
    article_type_str = topic.get("article_type", "HARD_NEWS")
    try:
        article_type = ArticleType[article_type_str.upper()]
    except KeyError:
        article_type = ArticleType.HARD_NEWS

    return MessageCluster(
        cluster_id=topic.get("topic_id", f"topic_{id(topic)}"),
        messages=cluster_messages,
        topic_summary=topic.get("summary", ""),
        suggested_section=topic.get("section", "In Brief"),
        suggested_type=article_type,
    )


def _create_fallback_clusters(messages: list[SourceMessage]) -> list[MessageCluster]:
    """
    Create fallback clusters when LLM clustering fails.

    Args:
        messages: List of source messages

    Returns:
        List of single-message clusters
    """
    logger.warning("Creating fallback clusters (one per message)")
    clusters = []

    for idx, message in enumerate(messages):
        cluster = MessageCluster(
            cluster_id=f"fallback_{idx}",
            messages=[message],
            topic_summary=message.text[:100],
            suggested_section="In Brief",
            suggested_type=ArticleType.BRIEF,
        )
        clusters.append(cluster)

    return clusters
