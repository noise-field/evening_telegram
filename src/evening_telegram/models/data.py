"""Core data models for The Evening Telegram."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ArticleType(Enum):
    """Type of newspaper article."""

    HARD_NEWS = "hard_news"
    OPINION = "opinion"
    BRIEF = "brief"
    FEATURE = "feature"


@dataclass
class MediaReference:
    """Reference to media attached to a message."""

    type: str
    telegram_url: str
    caption: Optional[str] = None
    thumbnail_url: Optional[str] = None


@dataclass
class SourceMessage:
    """A single message from a Telegram channel."""

    message_id: int
    channel_id: int
    channel_username: str
    channel_title: str
    timestamp: datetime
    text: str
    is_forward: bool = False
    forward_from_channel: Optional[str] = None
    forward_from_title: Optional[str] = None
    forward_date: Optional[datetime] = None
    media: list[MediaReference] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    telegram_link: str = ""

    def __post_init__(self) -> None:
        """Construct Telegram link if not provided."""
        if not self.telegram_link:
            if self.channel_username.startswith("@"):
                username = self.channel_username[1:]
                self.telegram_link = f"https://t.me/{username}/{self.message_id}"
            else:
                channel_id_str = str(self.channel_id).replace("-100", "")
                self.telegram_link = f"https://t.me/c/{channel_id_str}/{self.message_id}"


@dataclass
class MessageCluster:
    """A group of semantically similar messages about the same topic."""

    cluster_id: str
    messages: list[SourceMessage]
    topic_summary: str = ""
    suggested_section: str = ""
    suggested_type: ArticleType = ArticleType.HARD_NEWS

    @property
    def source_count(self) -> int:
        """Number of unique channels in this cluster."""
        return len(set(m.channel_id for m in self.messages))

    @property
    def earliest_timestamp(self) -> datetime:
        """Earliest message timestamp in cluster."""
        return min(m.timestamp for m in self.messages)

    @property
    def latest_timestamp(self) -> datetime:
        """Latest message timestamp in cluster."""
        return max(m.timestamp for m in self.messages)


@dataclass
class Article:
    """A generated newspaper article."""

    article_id: str
    headline: str
    subheadline: Optional[str]
    body: str
    article_type: ArticleType
    section: str
    source_clusters: list[MessageCluster]
    stance_summary: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def all_sources(self) -> list[SourceMessage]:
        """Flatten all source messages from all clusters."""
        return [m for c in self.source_clusters for m in c.messages]

    @property
    def source_channels(self) -> list[str]:
        """Unique channel titles that contributed to this article."""
        return list(set(m.channel_title for m in self.all_sources))


@dataclass
class NewspaperSection:
    """A section of the newspaper."""

    name: str
    articles: list[Article]
    order: int


@dataclass
class Newspaper:
    """The complete generated newspaper."""

    edition_id: str
    title: str
    tagline: str
    edition_date: datetime
    period_start: datetime
    period_end: datetime
    language: str
    sections: list[NewspaperSection]
    total_messages_processed: int
    total_channels: int
    token_usage: dict = field(default_factory=dict)

    @property
    def total_articles(self) -> int:
        """Total number of articles across all sections."""
        return sum(len(s.articles) for s in self.sections)
