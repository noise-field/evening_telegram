"""Configuration file loader with environment variable support."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml

from .models import Config


def load_config(config_path: Optional[Path] = None, overrides: Optional[dict[str, Any]] = None) -> Config:
    """
    Load configuration from YAML file with environment variable overrides.

    Args:
        config_path: Path to YAML configuration file
        overrides: Dictionary of override values from CLI

    Returns:
        Validated Config object
    """
    if config_path is None:
        config_path = Path("~/.config/evening-telegram/config.yaml")

    config_path = config_path.expanduser()

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    # Apply CLI overrides
    if overrides:
        config_data = _apply_overrides(config_data, overrides)

    # Apply environment variable overrides
    config_data = _apply_env_overrides(config_data)

    return Config(**config_data)


def _apply_overrides(config_data: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Apply CLI overrides to configuration data."""
    for key, value in overrides.items():
        if "." in key:
            parts = key.split(".")
            current = config_data
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        else:
            config_data[key] = value
    return config_data


def _apply_env_overrides(config_data: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides for sensitive values."""
    env_mappings = {
        "EVENING_TELEGRAM_API_ID": ("telegram", "api_id"),
        "EVENING_TELEGRAM_API_HASH": ("telegram", "api_hash"),
        "EVENING_TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
        "EVENING_TELEGRAM_LLM_API_KEY": ("llm", "api_key"),
        "EVENING_TELEGRAM_SMTP_PASSWORD": ("email", "smtp_password"),
    }

    for env_var, path in env_mappings.items():
        value = os.getenv(env_var)
        if value is not None:
            current = config_data
            for key in path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Handle type conversion for api_id
            if path[-1] == "api_id":
                value = int(value)

            current[path[-1]] = value

    return config_data
