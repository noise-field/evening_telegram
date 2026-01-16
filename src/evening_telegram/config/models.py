"""Configuration data models using Pydantic."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramConfig(BaseModel):
    """Telegram authentication configuration."""

    api_id: int
    api_hash: str
    phone: str
    session_file: Path = Path("~/.config/evening-telegram/telegram.session")


class TelegramDeliveryConfig(BaseModel):
    """Telegram delivery configuration for a subscription."""

    bot_token: str
    chat_id: int | list[int]  # Single chat ID or list of chat IDs


class ScheduleConfig(BaseModel):
    """Schedule configuration for a subscription."""

    lookback: str = "24 hours"

    # For daily/multiple times per day schedules
    times: Optional[list[str]] = None  # e.g., ["10:00", "22:00"]

    # For weekly schedules
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday
    time: Optional[str] = None  # e.g., "09:00"

    # For explicit time ranges (overrides lookback)
    from_time: Optional[str] = Field(None, alias="from")
    to_time: Optional[str] = Field(None, alias="to")


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    base_url: str = "https://api.openai.com/v1"
    api_key: str
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120
    structured_output: bool = False  # Enable Structured Output mode for supported models


class SubscriptionEmailConfig(BaseModel):
    """Email configuration specific to a subscription."""

    to: list[str]
    from_address: Optional[str] = None
    from_name: Optional[str] = None


class OutputConfig(BaseModel):
    """Output configuration for a subscription."""

    language: str = "en"
    newspaper_name: str = "The Evening Telegram"
    tagline: str = "All the news that's fit to aggregate"
    html_path: Path = Path("~/evening-telegram/editions/%Y-%m-%d.html")
    save_html: bool = True
    send_telegram: bool = True
    send_email: bool = False
    timezone: str = "local"  # "local" for system timezone, or IANA timezone like "America/New_York", "Europe/London"

    # Optional per-subscription delivery configs
    telegram: Optional[TelegramDeliveryConfig] = None
    email: Optional[SubscriptionEmailConfig] = None

    sections: list[str] = Field(
        default=[
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
    )


class EmailConfig(BaseModel):
    """Email delivery configuration."""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    use_tls: bool = True
    to: list[str]
    from_address: str
    from_name: str = "The Evening Telegram"


class ProcessingConfig(BaseModel):
    """Processing options configuration."""

    min_sources_for_article: int = 2
    max_messages: int = 0
    include_external_forwards: bool = True
    clustering_batch_size: int = 50


class StateConfig(BaseModel):
    """State management configuration."""

    db_path: Path = Path("~/.config/evening-telegram/state.db")
    mode: str = "since_last"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: Optional[Path] = Path("~/.config/evening-telegram/evening-telegram.log")


class SubscriptionConfig(BaseModel):
    """Configuration for a single subscription."""

    name: str
    channels: list[str]
    schedule: ScheduleConfig
    output: OutputConfig
    processing: Optional[ProcessingConfig] = None


class Config(BaseSettings):
    """Main configuration model."""

    telegram: TelegramConfig
    llm: LLMConfig
    subscriptions: dict[str, SubscriptionConfig]

    # Global email config (fallback for subscriptions)
    email: Optional[EmailConfig] = None

    state: StateConfig = Field(default_factory=StateConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = SettingsConfigDict(
        env_prefix="EVENING_TELEGRAM_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )
