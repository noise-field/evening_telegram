"""LLM prompt templates."""

from ..models.data import ArticleType, SourceMessage

CANDIDATE_SECTIONS = [
    "Breaking News",
    "Politics",
    "World",
    "Business",
    "Technology",
    "Science",
    "Culture",
    "Sports",
    "Opinion",
    "In Brief",
]


def format_clustering_prompt(
    messages: list[SourceMessage], sections: list[str] | None = None
) -> list[dict[str, str]]:
    """
    Format deduplication and clustering prompt.

    Args:
        messages: List of source messages to cluster
        sections: Optional list of custom section names. If not provided, uses CANDIDATE_SECTIONS.

    Returns:
        List of message dicts for LLM API
    """
    formatted_messages = []
    for i, msg in enumerate(messages, 1):
        formatted_messages.append(
            f"[{i}] {msg.channel_title}: {msg.text[:500]}"
            + ("..." if len(msg.text) > 500 else "")
        )

    messages_text = "\n\n".join(formatted_messages)

    # Use custom sections if provided, otherwise fall back to defaults
    section_list = sections if sections else CANDIDATE_SECTIONS

    system_prompt = f"""You are an editor at a newspaper reviewing incoming news items from multiple sources.

Your task is to:
1. DEDUPLICATE: Identify messages that report on the same story/event (even if worded differently)
2. CLUSTER: Group related items into coherent topics/themes (aim for 5-15 distinct topics)
3. CLASSIFY: For each topic, determine the article type:
   - HARD_NEWS: Factual reporting of events
   - OPINION: Commentary, editorials, or opinion pieces
   - BRIEF: Minor items not warranting a full article
4. CATEGORIZE: Suggest a newspaper section for each topic from: {', '.join(section_list)}

Messages from the SAME channel reporting on the same story are updates, not duplicates—keep them together in one topic.

IMPORTANT: Skip any messages that are greetings, ads, donation pleas, or promotional content.

Respond in JSON format with this structure:
{{
  "topics": [
    {{
      "topic_id": "topic_1",
      "summary": "Brief description of this topic/story",
      "message_ids": [1, 3, 7, 12],
      "article_type": "HARD_NEWS",
      "section": "Politics"
    }}
  ]
}}"""

    user_prompt = f"News items to cluster:\n\n{messages_text}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def format_article_generation_prompt(
    cluster_messages: list[SourceMessage],
    article_type: ArticleType,
    section: str,
    language: str,
    newspaper_name: str,
    topic_summary: str,
) -> list[dict[str, str]]:
    """
    Format article generation prompt.

    Args:
        cluster_messages: Messages in this cluster
        article_type: Type of article to generate
        section: Newspaper section
        language: Target language
        newspaper_name: Name of the newspaper
        topic_summary: Summary of the topic

    Returns:
        List of message dicts for LLM API
    """
    formatted_sources = []
    for i, msg in enumerate(cluster_messages, 1):
        formatted_sources.append(
            f"[Source {i}] {msg.channel_title} ({msg.timestamp.strftime('%Y-%m-%d %H:%M')}): {msg.text}"
        )

    sources_text = "\n\n".join(formatted_sources)

    if article_type == ArticleType.HARD_NEWS:
        system_prompt = f"""You are a journalist writing for {newspaper_name}. Write a news article based on the following source material.

REQUIREMENTS:
- Write in {language}
- Use inverted pyramid structure (most important facts first)
- Be factual and objective - no editorializing
- Every factual claim must be attributable to a source
- Use inline citations in the format [Source: Channel Name]
- Generate a compelling but accurate headline
- Generate a subheadline that adds context
- Format the body as HTML with proper paragraphs (<p> tags)

Topic: {topic_summary}

FORMAT YOUR RESPONSE AS JSON:
{{
  "headline": "...",
  "subheadline": "...",
  "body": "HTML-formatted article body with [Source: X] citations"
}}"""

    elif article_type == ArticleType.OPINION:
        system_prompt = f"""You are a columnist writing for {newspaper_name}. Write an opinion piece based on the following commentary from various sources.

REQUIREMENTS:
- Write in {language}
- Preserve the original stance and perspective from the sources
- Write in an engaging, lively style appropriate for opinion journalism
- Clearly indicate whose views are being represented
- Use inline citations [Source: Channel Name]
- Generate an attention-grabbing headline
- Format the body as HTML with proper paragraphs (<p> tags)

Topic: {topic_summary}

FORMAT YOUR RESPONSE AS JSON:
{{
  "headline": "...",
  "subheadline": "...",
  "stance_summary": "One sentence summary of the perspective",
  "body": "HTML-formatted opinion piece with [Source: X] citations"
}}"""

    elif article_type == ArticleType.BRIEF:
        system_prompt = f"""You are writing a brief news item for {newspaper_name}.

REQUIREMENTS:
- Write in {language}
- Keep it to 1-2 sentences
- Just the essential facts
- Include one source citation [Source: Channel Name]
- Generate a short, punchy headline

Topic: {topic_summary}

FORMAT YOUR RESPONSE AS JSON:
{{
  "headline": "...",
  "subheadline": null,
  "body": "One or two sentence summary with [Source: X] citation"
}}"""

    else:  # FEATURE
        system_prompt = f"""You are a feature writer for {newspaper_name}. Write a longer-form article based on the following source material.

REQUIREMENTS:
- Write in {language}
- Provide context and analysis beyond just the facts
- Use engaging narrative style while remaining informative
- Include inline citations [Source: Channel Name]
- Generate a compelling headline that captures the essence
- Format the body as HTML with proper paragraphs (<p> tags)

Topic: {topic_summary}

FORMAT YOUR RESPONSE AS JSON:
{{
  "headline": "...",
  "subheadline": "...",
  "body": "HTML-formatted feature article with [Source: X] citations"
}}"""

    user_prompt = f"SOURCE MATERIAL:\n\n{sources_text}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def format_merge_clusters_prompt(cluster_summaries: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Format cross-batch cluster merging prompt.

    Args:
        cluster_summaries: List of cluster summary dicts

    Returns:
        List of message dicts for LLM API
    """
    formatted_summaries = []
    for cs in cluster_summaries:
        formatted_summaries.append(
            f"[{cs['cluster_id']}] Section: {cs['section']}, Type: {cs['type']}\n"
            f"Summary: {cs['summary']}"
        )

    summaries_text = "\n\n".join(formatted_summaries)

    system_prompt = """You are an editor consolidating topic clusters from different batches.

Below are topic summaries from separate processing batches. Some topics may actually be the same story reported across batches.

Your task:
1. Identify topics that should be MERGED (same underlying story)
2. Return merge instructions

Respond in JSON format:
{
  "merges": [
    {
      "keep": "batch1_topic_3",
      "merge_into_it": ["batch2_topic_1", "batch3_topic_5"],
      "combined_summary": "Updated summary for merged topic"
    }
  ],
  "unchanged": ["batch1_topic_1", "batch2_topic_2", ...]
}"""

    user_prompt = f"Topic summaries:\n\n{summaries_text}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
