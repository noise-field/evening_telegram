"""Configuration file loader with environment variable support."""

import re
from pathlib import Path
from typing import Any, Optional

from envyaml import EnvYAML

from .models import Config


def _process_env_defaults(data: Any) -> Any:
    """
    Recursively process data to handle $VAR:default_value syntax.

    EnvYAML doesn't support default values, so we handle them manually.
    Converts strings like "$VAR:default" to just "default" when VAR is unset.
    """
    if isinstance(data, dict):
        return {k: _process_env_defaults(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_process_env_defaults(item) for item in data]
    elif isinstance(data, str):
        # Check if this is an unresolved env var with default: $VAR:default or $VAR
        # EnvYAML leaves these as literal strings when unset
        match = re.match(r'^\$([A-Z_][A-Z0-9_]*):(.+)$', data)
        if match:
            # Return the default value (after the colon)
            return match.group(2)
        return data
    else:
        return data


def load_config(config_path: Optional[Path] = None, overrides: Optional[dict[str, Any]] = None) -> Config:
    """
    Load configuration from YAML file with environment variable support.

    Supports $VAR for environment variables and $VAR:default_value for defaults.

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

    # Load config with environment variable substitution
    # strict=False allows unset variables to remain as $VAR strings
    env_config = EnvYAML(str(config_path), strict=False)

    # EnvYAML acts as a dict-like object, convert to plain dict
    # excluding environment variables by only taking keys from the YAML
    import yaml
    with open(config_path, 'r') as f:
        yaml_keys = set(yaml.safe_load(f).keys())

    config_data = {k: env_config[k] for k in yaml_keys if k in env_config}

    # Process any remaining $VAR:default syntax for unset variables
    config_data = _process_env_defaults(config_data)

    # Apply CLI overrides
    if overrides:
        config_data = _apply_overrides(config_data, overrides)

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
