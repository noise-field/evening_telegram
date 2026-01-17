"""Pydantic schemas for LLM structured outputs."""

from pydantic import BaseModel, Field


class TopicSchema(BaseModel):
    """Schema for a single topic/cluster in clustering response."""

    topic_id: str = Field(description="Unique identifier for this topic")
    summary: str = Field(description="Brief description of this topic/story")
    message_ids: list[int] = Field(
        description="List of message IDs (1-indexed) belonging to this topic"
    )
    article_type: str = Field(description="Type of article: HARD_NEWS, OPINION, BRIEF, or FEATURE")
    section: str = Field(description="Newspaper section for this topic")


class ClusteringResponse(BaseModel):
    """Schema for deduplication and clustering response."""

    topics: list[TopicSchema] = Field(description="List of identified topics/clusters")


class MergeInstruction(BaseModel):
    """Schema for a single merge instruction."""

    keep: str = Field(description="Cluster ID to keep")
    merge_into_it: list[str] = Field(
        description="List of cluster IDs to merge into the kept cluster"
    )
    combined_summary: str = Field(description="Updated summary for the merged topic")


class MergeResponse(BaseModel):
    """Schema for cross-batch cluster merging response."""

    merges: list[MergeInstruction] = Field(
        description="List of merge instructions for clusters that should be combined"
    )
    unchanged: list[str] = Field(description="List of cluster IDs that should remain unchanged")


class ArticleResponse(BaseModel):
    """Schema for article generation response."""

    headline: str = Field(description="Article headline")
    subheadline: str | None = Field(default=None, description="Article subheadline (optional)")
    body: str = Field(description="HTML-formatted article body with [Source: X] citations")
    stance_summary: str | None = Field(
        default=None, description="One sentence summary of the perspective (for opinion pieces)"
    )


class ContentFilterResponse(BaseModel):
    """Schema for content filtering response."""

    legitimate: list[int] = Field(
        description="List of message IDs (1-indexed) that contain legitimate content"
    )
    trash: list[int] = Field(
        description="List of message IDs (1-indexed) that are ads, greetings, or spam"
    )
