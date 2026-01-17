# The Evening Telegram

## Specification Document v1.0

---

## 1. Project Overview

### 1.1 Problem Statement

Modern Telegram channels, like most social media, create a compulsive urge to stay "updated" through constant checking. Many channels repeat identical information with minor variations—they are not genuine news outlets but attention-seeking operations that aggregate and repackage content from each other. This results in:

- **Information overload**: Hours spent scrolling through repetitive content
- **FOMO-driven behavior**: Anxiety about missing updates
- **Low signal-to-noise ratio**: Genuine news buried under duplicates and noise

### 1.2 Solution

**The Evening Telegram** is a Python daemon application that:

1. Runs continuously as a background service
2. Manages multiple subscriptions, each with its own configuration
3. Reads messages from user-specified Telegram channels over configurable time periods
4. Uses an LLM to identify recurring themes, deduplicate information, and cluster topics
5. Generates professionally-styled HTML "newspapers" with categorized articles
6. Delivers reports via local file, Telegram bot message, and/or email at scheduled times
7. Supports different update frequencies per subscription (e.g., daily for politics, weekly for AI news)

### 1.3 Design Principles

- **Daemon mode**: Runs as a background service with configurable subscriptions and schedules
- **Multiple subscriptions**: Each subscription has its own channels, schedule, output format, and delivery method
- **Flexible scheduling**: Support for daily, weekly, and custom time-based report generation
- **Configurable**: Channels, time periods, language, LLM provider, and output options are user-defined per subscription
- **Attribution-first**: Every claim links back to its source message(s)
- **Cost-transparent**: Token usage reported in the output footer
- **Minimal API calls**: State management to avoid re-fetching already-processed content

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Configuration                                  │
│                    (YAML file + CLI overrides)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        1. INGESTION LAYER                               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │  Telegram       │    │   Message       │    │    State        │     │
│  │  MTProto Client │───▶│   Normalizer    │───▶│    Manager      │     │
│  │  (Telethon)     │    │                 │    │   (SQLite)      │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     2. PROCESSING LAYER (LLM)                           │
│  ┌──────────────────────────────────┐    ┌─────────────────────────┐   │
│  │   Deduplication & Clustering     │    │   Article Generation    │   │
│  │   (single LLM pass per batch)    │───▶│   (per topic)           │   │
│  └──────────────────────────────────┘    └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         3. OUTPUT LAYER                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │   HTML          │    │   Telegram      │    │    Email        │     │
│  │   Generator     │    │   Bot Sender    │    │    Sender       │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

The application is intentionally designed as a **thin wrapper** around two APIs:
1. **Telegram API** (MTProto for reading, Bot API for sending)
2. **OpenAI-compatible LLM API** (for all semantic analysis and content generation)

All "intelligence" is delegated to the LLM—no local ML models or heavy dependencies.

### 2.2 Component Overview

| Component | Responsibility |
|-----------|----------------|
| **Config Manager** | Load, validate, and merge YAML config with CLI arguments |
| **Telegram Client** | Authenticate and fetch messages via MTProto (Telethon) |
| **Message Normalizer** | Extract text, handle forwards, normalize structure |
| **State Manager** | Track processed messages, manage incremental runs |
| **Clusterer** | LLM-based deduplication, topic clustering, and section assignment |
| **Article Generator** | LLM-powered content generation with source attribution |
| **HTML Renderer** | Generate newspaper-style HTML output |
| **Telegram Bot Sender** | Send report via Telegram Bot API |
| **Email Sender** | Send report via SMTP |
| **Token Tracker** | Accumulate and report LLM token usage |

---

## 3. Configuration

### 3.1 Configuration File Structure

The application uses a YAML configuration file (default: `~/.config/evening-telegram/config.yaml`).

```yaml
# ~/.config/evening-telegram/config.yaml

# =============================================================================
# TELEGRAM AUTHENTICATION
# =============================================================================
telegram:
  # MTProto API credentials (from https://my.telegram.org/apps)
  api_id: 12345678
  api_hash: "your_api_hash_here"

  # Phone number for the account (international format)
  phone: "+1234567890"

  # Session file location (stores auth session to avoid re-login)
  session_file: "~/.config/evening-telegram/telegram.session"

# =============================================================================
# LLM CONFIGURATION (default for all subscriptions)
# =============================================================================
llm:
  # OpenAI-compatible API endpoint
  # Examples:
  #   - OpenAI: https://api.openai.com/v1
  #   - Anthropic (via proxy): https://your-proxy.com/v1
  #   - Ollama: http://localhost:11434/v1
  #   - Together.ai: https://api.together.xyz/v1
  #   - OpenRouter: https://openrouter.ai/api/v1
  base_url: "https://api.openai.com/v1"

  # API key (can also be set via EVENING_TELEGRAM_LLM_API_KEY env var)
  api_key: "sk-..."

  # Model identifier
  model: "gpt-4o"

  # Temperature for generation (0.0 = deterministic, 1.0 = creative)
  temperature: 0.3

  # Maximum tokens per LLM call
  max_tokens: 4096

  # Request timeout in seconds
  timeout: 120

# =============================================================================
# SUBSCRIPTIONS
# =============================================================================
subscriptions:
  # Each subscription is a separate news digest with its own settings

  politics_daily:
    # Subscription name (used for logging and file naming)
    name: "Daily Politics & Finance"

    # Channels to monitor for this subscription
    channels:
      - "@politics_channel"
      - "@financial_news"
      - "@world_news"

    # Report generation schedule
    schedule:
      # Default lookback period (used when time entry doesn't specify one)
      lookback: "12 hours"

      # Time(s) to generate reports (24-hour format)
      # Can specify multiple times for multiple reports per day
      # Each time can optionally have its own lookback period
      times:
        - "10:00"  # Morning briefing - uses default lookback (12 hours)
        - "22:00"  # Evening briefing - uses default lookback (12 hours)

      # Alternative format with per-time lookback values:
      # times:
      #   - time: "08:00"
      #     lookback: "12 hours"  # Overnight: covers 20:00-08:00
      #   - time: "14:00"
      #     lookback: "6 hours"   # Midday: covers 08:00-14:00
      #   - time: "20:00"
      #     lookback: "6 hours"   # Evening: covers 14:00-20:00

    # Output configuration
    output:
      language: "en"
      newspaper_name: "Politics & Finance Daily"
      tagline: "Your daily briefing on politics and markets"

      # HTML output path (supports strftime formatting)
      html_path: "~/evening-telegram/politics/%Y-%m-%d-%H%M.html"

      # Delivery methods
      save_html: true
      send_telegram: true
      send_email: false

      # Telegram delivery (optional, overrides global)
      telegram:
        bot_token: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        chat_id: 123456789

      # Email delivery (optional)
      email:
        to:
          - "user@example.com"
        from_address: "politics@example.com"
        from_name: "Politics Daily"

    # Processing options (optional, uses defaults if not specified)
    processing:
      min_sources_for_article: 2
      max_messages: 0
      include_external_forwards: true
      clustering_batch_size: 50

  ai_weekly:
    name: "AI Weekly Digest"

    channels:
      - "@ai_news"
      - "@ml_research"
      - "@llm_updates"

    schedule:
      # Weekly lookback
      lookback: "7 days"

      # Day of week (0=Monday, 6=Sunday) and time
      day_of_week: 0  # Monday
      time: "09:00"

    output:
      language: "en"
      newspaper_name: "AI Weekly"
      tagline: "Your weekly AI and ML digest"
      html_path: "~/evening-telegram/ai-weekly/%Y-W%U.html"

      save_html: true
      send_telegram: true
      send_email: true

      telegram:
        bot_token: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        chat_id: 987654321

      email:
        to:
          - "user@example.com"
        from_address: "ai-weekly@example.com"
        from_name: "AI Weekly Digest"

# =============================================================================
# GLOBAL EMAIL CONFIGURATION (optional, for subscriptions without specific config)
# =============================================================================
email:
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: "your-email@gmail.com"
  smtp_password: "app-specific-password"  # or set EVENING_TELEGRAM_SMTP_PASSWORD
  use_tls: true

# =============================================================================
# STATE MANAGEMENT
# =============================================================================
state:
  # SQLite database for tracking processed messages per subscription
  db_path: "~/.config/evening-telegram/state.db"

  # Run mode:
  #   - "since_last": Only process messages since last successful run per subscription
  #   - "full": Always process the full lookback period (may reprocess)
  mode: "since_last"

# =============================================================================
# LOGGING
# =============================================================================
logging:
  level: "INFO"
  file: "~/.config/evening-telegram/evening-telegram.log"
```

### 3.2 Environment Variables

Sensitive values can be provided via environment variables (these override config file values):

| Variable | Config Path | Description |
|----------|-------------|-------------|
| `EVENING_TELEGRAM_API_ID` | `telegram.api_id` | Telegram API ID |
| `EVENING_TELEGRAM_API_HASH` | `telegram.api_hash` | Telegram API hash |
| `EVENING_TELEGRAM_BOT_TOKEN` | `telegram.bot_token` | Bot token for sending |
| `EVENING_TELEGRAM_LLM_API_KEY` | `llm.api_key` | LLM provider API key |
| `EVENING_TELEGRAM_SMTP_PASSWORD` | `email.smtp_password` | SMTP password |

### 3.3 CLI Interface

```bash
# Start daemon mode (runs continuously)
evening-telegram daemon

# Specify custom config file for daemon
evening-telegram daemon --config /path/to/config.yaml

# Run a specific subscription once (one-off mode)
evening-telegram run --subscription politics_daily

# Run with custom lookback period (one-off mode)
evening-telegram run --subscription ai_weekly --lookback "14 days"

# Run all subscriptions once (useful for testing)
evening-telegram run-all

# Override output options (one-off mode)
evening-telegram run --subscription politics_daily --output ~/custom-output.html
evening-telegram run --subscription politics_daily --no-telegram --no-email  # HTML only

# Dry run (fetch and process, but don't send or save)
evening-telegram run --subscription politics_daily --dry-run

# Verbose output
evening-telegram daemon -v
evening-telegram run --subscription politics_daily -vv  # Debug level

# List configured subscriptions
evening-telegram list-subscriptions

# Test schedule for a subscription (shows next execution times)
evening-telegram test-schedule --subscription politics_daily
```

---

## 4. Data Models

### 4.1 Core Data Structures

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

class ArticleType(Enum):
    HARD_NEWS = "hard_news"      # Factual reporting
    OPINION = "opinion"          # Editorial/commentary
    BRIEF = "brief"              # Short news item
    FEATURE = "feature"          # Longer-form piece

@dataclass
class MediaReference:
    """Reference to media attached to a message."""
    type: str                    # "photo", "video", "document", "audio"
    telegram_url: str            # Direct link to media in Telegram
    caption: Optional[str]       # Media caption if any
    thumbnail_url: Optional[str] # For video/document previews

@dataclass
class SourceMessage:
    """A single message from a Telegram channel."""
    message_id: int
    channel_id: int
    channel_username: str        # @username or numeric ID as string
    channel_title: str           # Human-readable channel name
    timestamp: datetime
    text: str                    # Message text content
    
    # Forward information (if this message was forwarded)
    is_forward: bool = False
    forward_from_channel: Optional[str] = None
    forward_from_title: Optional[str] = None
    forward_date: Optional[datetime] = None
    
    # Media attachments
    media: list[MediaReference] = field(default_factory=list)
    
    # External links mentioned in the message
    external_links: list[str] = field(default_factory=list)
    
    # Computed fields
    telegram_link: str = ""      # t.me link to this message
    
    def __post_init__(self):
        if not self.telegram_link:
            # Construct link: https://t.me/c/CHANNEL_ID/MESSAGE_ID for private
            # or https://t.me/username/MESSAGE_ID for public
            if self.channel_username.startswith("@"):
                username = self.channel_username[1:]
                self.telegram_link = f"https://t.me/{username}/{self.message_id}"
            else:
                # Private channel - use c/ format
                channel_id_str = str(self.channel_id).replace("-100", "")
                self.telegram_link = f"https://t.me/c/{channel_id_str}/{self.message_id}"

@dataclass
class MessageCluster:
    """A group of semantically similar messages about the same topic."""
    cluster_id: str
    messages: list[SourceMessage]
    
    # LLM-generated summary of what this cluster is about
    topic_summary: str = ""
    
    # Suggested section for this cluster
    suggested_section: str = ""
    
    # Suggested article type
    suggested_type: ArticleType = ArticleType.HARD_NEWS
    
    @property
    def source_count(self) -> int:
        """Number of unique channels in this cluster."""
        return len(set(m.channel_id for m in self.messages))
    
    @property
    def earliest_timestamp(self) -> datetime:
        return min(m.timestamp for m in self.messages)
    
    @property
    def latest_timestamp(self) -> datetime:
        return max(m.timestamp for m in self.messages)

@dataclass
class Article:
    """A generated newspaper article."""
    article_id: str
    headline: str
    subheadline: Optional[str]
    body: str                    # HTML-formatted body text
    article_type: ArticleType
    section: str                 # e.g., "Politics", "Technology", "World"
    
    # Source attribution
    source_clusters: list[MessageCluster]
    
    # For opinions: the stance/perspective being represented
    stance_summary: Optional[str] = None
    
    # Generation metadata
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
    """A section of the newspaper (e.g., 'Politics', 'Technology')."""
    name: str
    articles: list[Article]
    order: int                   # Display order (lower = earlier)

@dataclass
class Newspaper:
    """The complete generated newspaper."""
    edition_id: str              # Unique identifier for this edition
    title: str                   # e.g., "The Evening Telegram"
    tagline: str
    edition_date: datetime
    period_start: datetime
    period_end: datetime
    language: str
    
    sections: list[NewspaperSection]
    
    # Statistics
    total_messages_processed: int
    total_channels: int
    
    # Token usage
    token_usage: dict = field(default_factory=dict)
    # Structure: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    
    @property
    def total_articles(self) -> int:
        return sum(len(s.articles) for s in self.sections)
```

### 4.2 State Management Schema

```sql
-- SQLite schema for state management

-- Track the last successful run
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    messages_processed INTEGER DEFAULT 0,
    error_message TEXT
);

-- Track processed messages to avoid reprocessing
CREATE TABLE IF NOT EXISTS processed_messages (
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    processed_at TIMESTAMP NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (channel_id, message_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

-- Index for efficient "since last run" queries
CREATE INDEX IF NOT EXISTS idx_processed_messages_run 
ON processed_messages(run_id);

-- Cache channel metadata to reduce API calls
CREATE TABLE IF NOT EXISTS channel_cache (
    channel_id INTEGER PRIMARY KEY,
    username TEXT,
    title TEXT,
    is_private BOOLEAN,
    last_updated TIMESTAMP
);
```

---

## 5. Processing Pipeline

### 5.1 Ingestion Stage

#### 5.1.1 Telegram Client Initialization

```python
# Pseudocode for client initialization
async def initialize_telegram_client(config: TelegramConfig) -> TelegramClient:
    """
    Initialize and authenticate the Telethon client.
    
    First run will prompt for phone code/2FA.
    Subsequent runs use stored session.
    """
    client = TelegramClient(
        session=config.session_file,
        api_id=config.api_id,
        api_hash=config.api_hash
    )
    
    await client.start(phone=config.phone)
    
    return client
```

#### 5.1.2 Message Fetching

For each configured channel:

1. Resolve channel entity (handle both usernames and IDs)
2. Determine the time window:
   - If `mode == "since_last"`: from last successful run's `period_end` to now
   - If `mode == "full"`: from `now - lookback` to now
3. Fetch messages within the time window
4. Skip messages already in `processed_messages` table
5. Normalize each message into `SourceMessage` format

#### 5.1.3 Message Normalization

For each raw Telegram message:

```python
def normalize_message(raw_message, channel_info) -> SourceMessage:
    """
    Convert a raw Telethon message to our normalized format.
    
    Handles:
    - Text extraction (including captions)
    - Forward detection and source attribution
    - Media reference extraction
    - URL extraction from text
    - Telegram link construction
    """
    
    # Extract text content
    text = raw_message.text or raw_message.caption or ""
    
    # Handle forwards
    is_forward = raw_message.forward is not None
    forward_from_channel = None
    forward_from_title = None
    forward_date = None
    
    if is_forward and raw_message.forward.chat:
        forward_from_channel = getattr(raw_message.forward.chat, 'username', None)
        forward_from_title = getattr(raw_message.forward.chat, 'title', str(raw_message.forward.chat.id))
        forward_date = raw_message.forward.date
    
    # Extract media references
    media = extract_media_references(raw_message)
    
    # Extract external links
    external_links = extract_urls(text)
    
    return SourceMessage(
        message_id=raw_message.id,
        channel_id=channel_info.id,
        channel_username=f"@{channel_info.username}" if channel_info.username else str(channel_info.id),
        channel_title=channel_info.title,
        timestamp=raw_message.date,
        text=text,
        is_forward=is_forward,
        forward_from_channel=forward_from_channel,
        forward_from_title=forward_from_title,
        forward_date=forward_date,
        media=media,
        external_links=external_links
    )
```

### 5.2 Deduplication & Clustering Stage

All semantic analysis is performed by the LLM, keeping the application as a thin wrapper around API calls.

#### 5.2.1 LLM-Based Deduplication and Clustering

```python
async def deduplicate_and_cluster(
    messages: list[SourceMessage],
    llm_client: LLMClient
) -> list[MessageCluster]:
    """
    Use LLM to identify duplicate content and cluster into topics.
    
    This is done in a single pass (or batched passes for large volumes)
    to minimize API calls while handling both deduplication and topic
    identification.
    
    Approach:
    1. Format messages with IDs for reference
    2. Send to LLM with prompt asking to:
       - Identify messages that cover the same story/event
       - Group related messages into coherent topics
       - Suggest article type for each topic
       - Suggest newspaper section for each topic
    3. Parse structured response into MessageCluster objects
    
    For large message volumes (>100 messages), batch into chunks
    and do a second pass to merge related clusters across batches.
    """
```

#### 5.2.2 Batching Strategy for Large Volumes

```python
async def process_large_batch(
    messages: list[SourceMessage],
    llm_client: LLMClient,
    batch_size: int = 50
) -> list[MessageCluster]:
    """
    Handle large message volumes by batching.
    
    1. Split messages into batches of ~50
    2. Process each batch independently to get initial clusters
    3. Create summaries of each cluster
    4. Send cluster summaries to LLM for cross-batch merging
    5. Return final merged clusters
    
    This two-pass approach keeps individual prompts manageable
    while still catching duplicates across batches.
    """
```

### 5.3 Article Generation Stage

#### 5.3.1 Section Assignment

Sections are assigned during the clustering phase (5.2). The LLM chooses from these candidate sections based on content:

```python
CANDIDATE_SECTIONS = [
    "Breaking News",    # Time-sensitive, high importance
    "Politics",         # Government, elections, policy
    "World",            # International news
    "Business",         # Economy, markets, companies
    "Technology",       # Tech industry, gadgets, digital
    "Science",          # Research, discoveries
    "Culture",          # Entertainment, arts, lifestyle
    "Sports",           # Sports news
    "Opinion",          # Commentary, editorials
    "In Brief",         # Minor stories, single-source items
]
# These are passed to the LLM in the clustering prompt.
# The LLM may suggest sections outside this list if appropriate.
```

#### 5.3.2 Article Generation

Generate articles from clusters:

```python
async def generate_article(
    cluster: MessageCluster,
    article_type: ArticleType,
    section: str,
    language: str,
    llm_client: LLMClient
) -> Article:
    """
    Generate a newspaper article from a message cluster.
    
    Different prompts for different article types:
    
    HARD_NEWS:
    - Factual, objective tone
    - Inverted pyramid structure (most important info first)
    - No editorializing
    - Clear attribution for all claims
    
    OPINION:
    - Preserve the original stance/perspective from sources
    - More lively, engaging writing style
    - Can include analysis and commentary
    - Must clearly indicate this is opinion
    
    BRIEF:
    - 1-2 sentences
    - Just the essential facts
    - Single attribution
    
    All articles must:
    - Be written in the target language
    - Include inline source citations
    - Generate appropriate headline and subheadline
    """
```

#### 5.3.3 LLM Prompt Templates

**Deduplication & Clustering Prompt:**

```
You are an editor at a newspaper reviewing incoming news items from multiple sources.

Your task is to:
1. DEDUPLICATE: Identify messages that report on the same story/event (even if worded differently)
2. CLUSTER: Group related items into coherent topics/themes (aim for 5-15 distinct topics)
3. CLASSIFY: For each topic, determine the article type:
   - HARD_NEWS: Factual reporting of events
   - OPINION: Commentary, editorials, or opinion pieces
   - BRIEF: Minor items not warranting a full article
4. CATEGORIZE: Suggest a newspaper section for each topic

Messages from the SAME channel reporting on the same story are updates, not duplicates—keep them together in one topic.

News items (format: [ID] Channel: Message):
{formatted_messages}

Respond in JSON format:
{
  "topics": [
    {
      "topic_id": "topic_1",
      "summary": "Brief description of this topic/story",
      "message_ids": [1, 3, 7, 12],
      "article_type": "HARD_NEWS",
      "section": "Politics",
      "is_opinion": false
    },
    ...
  ]
}
```

**Cross-Batch Merging Prompt (for large volumes):**

```
You are an editor consolidating topic clusters from different batches.

Below are topic summaries from separate processing batches. Some topics may actually be the same story reported across batches.

Your task:
1. Identify topics that should be MERGED (same underlying story)
2. Return merge instructions

Topic summaries:
{formatted_cluster_summaries}

Respond in JSON format:
{
  "merges": [
    {
      "keep": "batch1_topic_3",
      "merge_into_it": ["batch2_topic_1", "batch3_topic_5"],
      "combined_summary": "Updated summary for merged topic"
    },
    ...
  ],
  "unchanged": ["batch1_topic_1", "batch2_topic_2", ...]
}
```

**Hard News Generation Prompt:**

```
You are a journalist writing for {newspaper_name}. Write a news article based on the following source material.

REQUIREMENTS:
- Write in {language}
- Use inverted pyramid structure (most important facts first)
- Be factual and objective - no editorializing
- Every factual claim must be attributable to a source
- Use inline citations in the format [Source: Channel Name]
- Generate a compelling but accurate headline
- Generate a subheadline that adds context

SOURCE MATERIAL:
{formatted_cluster_content}

FORMAT YOUR RESPONSE AS JSON:
{
  "headline": "...",
  "subheadline": "...",
  "body": "HTML-formatted article body with [Source: X] citations"
}
```

**Opinion Generation Prompt:**

```
You are a columnist writing for {newspaper_name}. Write an opinion piece based on the following commentary from various sources.

REQUIREMENTS:
- Write in {language}
- Preserve the original stance and perspective from the sources
- Write in an engaging, lively style appropriate for opinion journalism
- Clearly indicate whose views are being represented
- Use inline citations [Source: Channel Name]
- Generate an attention-grabbing headline

The sources express the following viewpoint(s):
{stance_summary}

SOURCE MATERIAL:
{formatted_cluster_content}

FORMAT YOUR RESPONSE AS JSON:
{
  "headline": "...",
  "subheadline": "...",
  "stance_summary": "One sentence summary of the perspective",
  "body": "HTML-formatted opinion piece with [Source: X] citations"
}
```

### 5.4 Token Tracking

```python
class TokenTracker:
    """Accumulate token usage across all LLM calls."""
    
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
    
    def record(self, response):
        """Record usage from an LLM API response."""
        if hasattr(response, 'usage'):
            self.prompt_tokens += response.usage.prompt_tokens
            self.completion_tokens += response.usage.completion_tokens
            self.calls += 1
    
    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
    
    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "api_calls": self.calls
        }
```

---

## 6. Output Generation

### 6.1 HTML Template

The HTML output should mimic professional newspaper websites (NYT, WaPo style). Key design elements:

#### 6.1.1 Design Specifications

- **Typography**: Serif fonts for headlines and body (e.g., Georgia, Charter, or Google Fonts equivalent)
- **Layout**: Responsive grid, single-column on mobile, multi-column on desktop
- **Header**: Newspaper name, edition date, period covered
- **Navigation**: Sticky section navigation
- **Articles**: Clear visual hierarchy, proper spacing
- **Citations**: Subtle but accessible source links
- **Footer**: Generation metadata, token usage, channel list

#### 6.1.2 HTML Structure

```html
<!DOCTYPE html>
<html lang="{language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{newspaper_name} - {edition_date}</title>
    <style>
        /* Embedded CSS - newspaper styling */
        /* See detailed CSS specification below */
    </style>
</head>
<body>
    <header class="masthead">
        <div class="masthead-content">
            <h1 class="newspaper-name">{newspaper_name}</h1>
            <p class="tagline">{tagline}</p>
            <div class="edition-info">
                <time datetime="{edition_date_iso}">{edition_date_formatted}</time>
                <span class="period">Covering {period_start} to {period_end}</span>
            </div>
        </div>
    </header>
    
    <nav class="section-nav">
        <ul>
            {for section in sections}
            <li><a href="#section-{section.slug}">{section.name}</a></li>
            {endfor}
        </ul>
    </nav>
    
    <main class="content">
        {for section in sections}
        <section id="section-{section.slug}" class="newspaper-section">
            <h2 class="section-header">{section.name}</h2>
            
            <div class="articles-grid">
                {for article in section.articles}
                <article class="article article-{article.type}">
                    <header class="article-header">
                        <h3 class="headline">{article.headline}</h3>
                        {if article.subheadline}
                        <p class="subheadline">{article.subheadline}</p>
                        {endif}
                        <div class="article-meta">
                            <span class="sources">
                                Sources: {article.source_channels | join(", ")}
                            </span>
                        </div>
                    </header>
                    
                    <div class="article-body">
                        {article.body}
                    </div>
                    
                    <footer class="article-footer">
                        <details class="source-details">
                            <summary>View sources ({article.all_sources | length})</summary>
                            <ul class="source-list">
                                {for source in article.all_sources}
                                <li>
                                    <a href="{source.telegram_link}" target="_blank">
                                        {source.channel_title}
                                    </a>
                                    <time>{source.timestamp}</time>
                                    {if source.is_forward}
                                    <span class="forward-note">
                                        (via {source.forward_from_title})
                                    </span>
                                    {endif}
                                </li>
                                {endfor}
                            </ul>
                        </details>
                    </footer>
                </article>
                {endfor}
            </div>
        </section>
        {endfor}
    </main>
    
    <footer class="newspaper-footer">
        <div class="generation-info">
            <p>
                Generated by The Evening Telegram on {generation_timestamp}
            </p>
            <p class="stats">
                {total_messages_processed} messages from {total_channels} channels
                processed into {total_articles} articles.
            </p>
            <p class="token-usage">
                LLM Usage: {token_usage.total_tokens} tokens
                ({token_usage.prompt_tokens} prompt + {token_usage.completion_tokens} completion)
                across {token_usage.api_calls} API calls.
            </p>
        </div>
        
        <details class="channel-list">
            <summary>Monitored Channels</summary>
            <ul>
                {for channel in channels}
                <li>{channel.title} ({channel.username})</li>
                {endfor}
            </ul>
        </details>
    </footer>
</body>
</html>
```

#### 6.1.3 CSS Specifications

The CSS should include:

```css
/* Key design tokens */
:root {
    --font-headline: Charter, Georgia, "Times New Roman", serif;
    --font-body: Charter, Georgia, "Times New Roman", serif;
    --font-ui: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    
    --color-text: #1a1a1a;
    --color-text-secondary: #666;
    --color-accent: #326891;
    --color-border: #e0e0e0;
    --color-background: #fff;
    --color-background-alt: #f7f7f7;
    
    --max-width: 1200px;
    --article-max-width: 720px;
}

/* Responsive grid for articles */
.articles-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
}

/* Lead article takes full width */
.article:first-child {
    grid-column: 1 / -1;
}

/* Citation styling */
.source-citation {
    color: var(--color-accent);
    text-decoration: none;
    border-bottom: 1px dotted var(--color-accent);
}

/* Opinion articles have distinct styling */
.article-opinion {
    border-left: 4px solid var(--color-accent);
    padding-left: 1rem;
}

.article-opinion::before {
    content: "OPINION";
    font-family: var(--font-ui);
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--color-accent);
    letter-spacing: 0.05em;
}
```

### 6.2 Telegram Bot Delivery

The bot should send two messages:

1. **Summary message** with:
   - Edition name, date, period
   - Section summaries: Brief list of top stories per section
   - Statistics footer

2. **HTML file attachment**: The full HTML newspaper as a document attachment

```python
async def send_telegram_report(
    newspaper: Newspaper,
    bot_token: str,
    chat_id: int,
    html_path: Optional[str] = None
):
    """
    Send newspaper summary to Telegram.

    First message format (using Telegram's HTML formatting):

    📰 <b>The Evening Telegram</b>
    {edition_date}

    <b>Top Stories:</b>

    <b>Politics</b>
    • {headline_1}
    • {headline_2}

    <b>Technology</b>
    • {headline_3}

    ...

    📊 {total_articles} articles from {total_channels} channels

    Then, if html_path is provided, send the HTML file as a document
    attachment with caption "📖 Full edition"
    """
```

### 6.3 Email Delivery

Send the complete HTML as an email:

```python
async def send_email_report(
    newspaper: Newspaper,
    html_content: str,
    config: EmailConfig
):
    """
    Send newspaper as HTML email.
    
    - Subject: "{newspaper_name} - {edition_date}"
    - Body: Full HTML content (inline CSS for email compatibility)
    - Consider: Attach HTML as file AND inline for different email clients
    """
```

---

## 7. Error Handling

### 7.1 Error Categories

| Category | Examples | Handling Strategy |
|----------|----------|-------------------|
| **Auth Errors** | Invalid API credentials, session expired | Fail fast, clear message, prompt re-auth |
| **Rate Limits** | Telegram flood wait, LLM rate limits | Exponential backoff with jitter |
| **Network Errors** | Timeouts, connection refused | Retry with backoff, eventual failure |
| **Channel Errors** | Channel not found, no access | Log warning, skip channel, continue |
| **LLM Errors** | Invalid response format, content filter | Retry once, fallback to raw content |
| **State Errors** | Corrupted DB, lock contention | Attempt repair, fallback to full mode |

### 7.2 Graceful Degradation

If critical errors occur during processing:

1. **Partial output**: Generate newspaper with successfully processed content
2. **Error section**: Add "Processing Notes" section listing any issues
3. **State preservation**: Don't mark failed items as processed
4. **Notification**: Include error summary in Telegram/email delivery

---

## 8. Project Structure

```
evening-telegram/
├── pyproject.toml              # Project metadata and dependencies
├── README.md                   # User documentation
├── LICENSE                     # License file
│
├── src/
│   └── evening_telegram/
│       ├── __init__.py
│       ├── __main__.py         # CLI entry point
│       ├── cli.py              # Click CLI definition
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── models.py       # Pydantic config models
│       │   └── loader.py       # Config file + env loading
│       │
│       ├── telegram/
│       │   ├── __init__.py
│       │   ├── client.py       # Telethon client wrapper
│       │   ├── fetcher.py      # Message fetching logic
│       │   └── bot.py          # Bot API for sending
│       │
│       ├── processing/
│       │   ├── __init__.py
│       │   ├── normalizer.py   # Message normalization
│       │   ├── clusterer.py    # LLM-based deduplication & clustering
│       │   └── generator.py    # Article generation
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── client.py       # OpenAI-compatible client
│       │   ├── prompts.py      # Prompt templates
│       │   └── tracker.py      # Token usage tracking
│       │
│       ├── output/
│       │   ├── __init__.py
│       │   ├── html.py         # HTML generation (Jinja2)
│       │   ├── telegram.py     # Telegram delivery
│       │   └── email.py        # Email delivery
│       │
│       ├── state/
│       │   ├── __init__.py
│       │   └── db.py           # SQLite state management
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   └── data.py         # Core data models
│       │
│       └── templates/
│           └── newspaper.html  # Jinja2 HTML template
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_config.py
│   ├── test_fetcher.py
│   ├── test_processing.py
│   ├── test_generator.py
│   └── test_output.py
│
└── examples/
    └── config.example.yaml     # Example configuration
```

### 8.1 Key Dependencies

```toml
[project]
name = "evening-telegram"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "telethon>=1.34",           # Telegram MTProto client
    "python-telegram-bot>=20",  # Telegram Bot API
    "openai>=1.0",              # OpenAI-compatible LLM client
    "pydantic>=2.0",            # Configuration validation
    "pydantic-settings>=2.0",   # Settings management
    "click>=8.0",               # CLI framework
    "jinja2>=3.0",              # HTML templating
    "aiosmtplib>=3.0",          # Async SMTP
    "aiosqlite>=0.19",          # Async SQLite
    "rich>=13.0",               # Terminal output formatting
    "python-dateutil>=2.8",     # Date parsing
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "ruff>=0.1",
    "mypy>=1.0",
]
```

---

## 9. Security Considerations

### 9.1 Credential Storage

- **Never commit credentials** to version control
- Support environment variables for all secrets
- Session files contain auth tokens - set appropriate file permissions (600)
- Consider adding `.session` files to `.gitignore` template

### 9.2 Data Privacy

- Message content may be sensitive - consider adding option to not log message text
- State DB contains message IDs which could be used to reconstruct reading history
- HTML output should not be hosted publicly without consideration of content licensing

### 9.3 Rate Limiting Compliance

- Respect Telegram's rate limits (implement flood wait handling)
- Respect LLM provider rate limits
- Add configurable delays between API calls if needed

---

## 10. Future Enhancements

The following are out of scope for v1.0 but documented for future consideration:

### 10.1 Near-term

- [ ] RSS feed output
- [ ] PDF generation (for archival)
- [ ] Multi-language support (different output languages per run)
- [ ] Custom section definitions
- [ ] Message filtering by keywords

### 10.2 Medium-term

- [ ] Web UI for configuration
- [ ] Scheduled runs without cron (built-in scheduler)
- [ ] Multiple report profiles (daily summary vs weekly digest)
- [ ] Sentiment analysis overlay
- [ ] Read/unread tracking integration

### 10.3 Long-term

- [ ] Multi-user support
- [ ] Content recommendation based on reading patterns
- [ ] Integration with other platforms (Twitter/X, RSS feeds)
- [ ] Local LLM support optimization (quantized models)

---

## Appendix A: Running as a System Service

### Systemd Service (Linux)

Create `/etc/systemd/system/evening-telegram.service`:

```ini
[Unit]
Description=The Evening Telegram - News digest daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username
ExecStart=/usr/local/bin/evening-telegram daemon --config /home/your-username/.config/evening-telegram/config.yaml
Restart=always
RestartSec=10

# Environment variables for secrets
Environment="EVENING_TELEGRAM_LLM_API_KEY=your-key-here"
Environment="EVENING_TELEGRAM_SMTP_PASSWORD=your-password-here"

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable evening-telegram
sudo systemctl start evening-telegram
sudo systemctl status evening-telegram
```

View logs:
```bash
sudo journalctl -u evening-telegram -f
```

### Alternative: Screen/Tmux

```bash
# Using screen
screen -S evening-telegram
evening-telegram daemon
# Detach with Ctrl+A, D

# Reattach
screen -r evening-telegram

# Using tmux
tmux new -s evening-telegram
evening-telegram daemon
# Detach with Ctrl+B, D

# Reattach
tmux attach -t evening-telegram
```

---

## Appendix B: First Run Checklist

1. [ ] Obtain Telegram API credentials from https://my.telegram.org/apps
2. [ ] Create Telegram bot(s) via @BotFather for each subscription (or use one bot for all)
3. [ ] Find your chat ID(s) (use @userinfobot or similar)
4. [ ] Obtain LLM API credentials from your chosen provider
5. [ ] Create configuration file from example with your subscriptions
6. [ ] Run `evening-telegram run --subscription <name> --dry-run` to complete Telegram auth and test
7. [ ] Test each subscription individually with `--dry-run` flag
8. [ ] Verify schedules with `evening-telegram test-schedule --subscription <name>`
9. [ ] Start daemon with `evening-telegram daemon` or set up as systemd service

---

## Appendix C: Troubleshooting

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| "SessionPasswordNeededError" | 2FA enabled on Telegram account | Run interactively, enter 2FA code when prompted |
| "ChannelPrivateError" | Account not subscribed to private channel | Subscribe to channel first via Telegram app |
| Empty output | All messages already processed | Use `--mode full` or extend lookback period |
| High token usage | Too many messages in period | Reduce lookback period or add `max_messages` limit |
| Malformed JSON from LLM | Model returning invalid format | Check model compatibility, adjust prompts, lower temperature |

---

*End of Specification*
