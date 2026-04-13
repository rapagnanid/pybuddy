"""Configuration management for PyBuddy.

Reads and writes ~/.pybuddy/config.toml.
"""

import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


CONFIG_DIR = Path.home() / ".pybuddy"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "api": {"key": ""},
    "preferences": {"notify": False, "language": "it"},
}


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load configuration from TOML file, merging with defaults."""
    config = {k: dict(v) for k, v in DEFAULT_CONFIG.items()}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            saved = tomllib.load(f)
        for section, values in saved.items():
            if section in config:
                config[section].update(values)
            else:
                config[section] = values
    return config


def save_config(config: dict):
    """Save configuration to TOML file."""
    _ensure_config_dir()
    lines = []
    for section, values in config.items():
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            else:
                lines.append(f"{key} = {value}")
        lines.append("")
    CONFIG_FILE.write_text("\n".join(lines))


def get_api_key() -> str:
    """Get the API key, checking env var first then config file."""
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_key:
        return env_key
    config = load_config()
    return config.get("api", {}).get("key", "")


def set_config_value(key: str, value: str):
    """Set a config value using dot notation (e.g., 'api.key')."""
    config = load_config()
    parts = key.split(".", 1)
    if len(parts) == 2:
        section, field = parts
    else:
        section, field = "preferences", parts[0]

    if section not in config:
        config[section] = {}

    # Parse booleans
    if value.lower() in ("true", "yes", "1"):
        config[section][field] = True
    elif value.lower() in ("false", "no", "0"):
        config[section][field] = False
    else:
        config[section][field] = value

    save_config(config)
