"""Configuration data models using Pydantic."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramConfig(BaseModel):
    """Telegram authentication and bot configuration."""

    api_id: int
    api_hash: str
    phone: str
    session_file: Path = Path("~/.config/evening-telegram/telegram.session")
    bot_token: Optional[str] = None
    report_chat_id: Optional[int] = None


class PeriodConfig(BaseModel):
    """Time period configuration."""

    lookback: str = "24 hours"
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


class OutputConfig(BaseModel):
    """Output configuration."""

    language: str = "en"
    newspaper_name: str = "The Evening Telegram"
    tagline: str = "All the news that's fit to aggregate"
    html_path: Path = Path("~/evening-telegram/editions/%Y-%m-%d.html")
    save_html: bool = True
    send_telegram: bool = True
    send_email: bool = False


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


class Config(BaseSettings):
    """Main configuration model."""

    telegram: TelegramConfig
    channels: list[str]
    period: PeriodConfig
    llm: LLMConfig
    output: OutputConfig
    email: Optional[EmailConfig] = None
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = SettingsConfigDict(
        env_prefix="EVENING_TELEGRAM_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )
