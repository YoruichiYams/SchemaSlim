"""Configuration loader and validator for SchemaSlim."""

import json
import os
from pathlib import Path
from typing import List, Optional, Union
from pydantic import ValidationError

from schemaslim.config.models import (
    Config,
    SchemaSlimSettings,
    StdioServerConfig,
)
from schemaslim.utils.logger import get_logger

logger = get_logger("config")

DEFAULT_CONFIG_FILENAMES: List[str] = [
    "schemaslim.json",
    ".schemaslim.json",
]


class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass


class ConfigNotFoundError(ConfigError):
    """Raised when no valid configuration file can be located."""
    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration content fails Pydantic schema validation."""
    pass


def find_config_file(
    explicit_path: Optional[Union[str, Path]] = None,
    allow_cwd: bool = False,
) -> Path:
    """Find configuration file path.

    Resolution precedence (Hardened):
    1. explicit_path argument if given.
    2. SCHEMASLIM_CONFIG environment variable.
    3. Global user configuration (~/.schemaslim/config.json or $XDG_CONFIG_HOME/schemaslim/config.json).
    4. ./schemaslim.json or ./.schemaslim.json in current working directory ONLY if allow_cwd=True
       or SCHEMASLIM_ALLOW_CWD=1 (otherwise raises ConfigNotFoundError).

    Returns:
        Resolved Path to existing config file.

    Raises:
        ConfigNotFoundError: If no config file is found or if untrusted CWD config is blocked.
    """
    # 1. Explicit path
    if explicit_path:
        p = Path(explicit_path).expanduser().resolve()
        if not p.is_file():
            raise ConfigNotFoundError(f"Specified configuration file not found: {p}")
        return p

    # 2. Environment variable
    env_path = os.getenv("SCHEMASLIM_CONFIG")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if not p.is_file():
            raise ConfigNotFoundError(
                f"Configuration file from SCHEMASLIM_CONFIG not found: {p}"
            )
        return p

    # 3. Global user configuration (trusted)
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    xdg_path = Path(xdg_config) / "schemaslim" / "config.json" if xdg_config else None

    home_candidates = [
        Path.home() / ".schemaslim" / "config.json",
        *( [xdg_path] if xdg_path else [] ),
        Path.home() / ".config" / "schemaslim" / "config.json",
    ]
    for candidate in home_candidates:
        if candidate.is_file():
            return candidate.resolve()

    # 4. Current working directory fallback (blocked by default unless explicitly allowed)
    is_cwd_allowed = allow_cwd or os.getenv("SCHEMASLIM_ALLOW_CWD") in ("1", "true", "True")
    cwd = Path.cwd()
    for name in DEFAULT_CONFIG_FILENAMES:
        candidate = cwd / name
        if candidate.is_file():
            resolved = candidate.resolve()
            if not is_cwd_allowed:
                raise ConfigNotFoundError(
                    f"Found config in current directory ({resolved}), but loading from "
                    "untrusted CWD is disabled by default. Pass --config explicitly or set SCHEMASLIM_ALLOW_CWD=1"
                )
            logger.warning(
                "Using configuration file from untrusted current working directory: %s",
                resolved,
            )
            return resolved

    raise ConfigNotFoundError(
        "No configuration file found. Looked in: explicit path, SCHEMASLIM_CONFIG, "
        "and ~/.schemaslim/config.json."
    )


def load_config(
    path: Optional[Union[str, Path]] = None,
    allow_cwd: bool = False,
) -> Config:
    """Load and validate SchemaSlim configuration from file.

    Args:
        path: Optional path to configuration file.
        allow_cwd: Whether to allow loading from untrusted current working directory.

    Returns:
        Validated Config model instance.

    Raises:
        ConfigNotFoundError: If file does not exist or untrusted CWD loading is blocked.
        ConfigValidationError: If file is invalid JSON or violates schema.
    """
    config_path = find_config_file(path, allow_cwd=allow_cwd)
    logger.debug("Loading configuration from: %s", config_path)

    try:
        content = config_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ConfigError(f"Failed to read configuration file {config_path}: {e}") from e

    try:
        raw_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ConfigValidationError(
            f"JSON decode error in {config_path} (line {e.lineno}, col {e.colno}): {e.msg}"
        ) from e

    if not isinstance(raw_data, dict):
        raise ConfigValidationError(
            f"Configuration root in {config_path} must be a JSON object/dictionary."
        )

    try:
        config = Config.model_validate(raw_data)
        logger.info(
            "Configuration successfully loaded from %s (%d servers configured)",
            config_path,
            len(config.mcpServers),
        )
        return config
    except ValidationError as e:
        error_lines = []
        for err in e.errors():
            loc = " -> ".join(str(item) for item in err["loc"])
            msg = err["msg"]
            error_lines.append(f"  - [{loc}]: {msg}")
        detailed_msg = "\n".join(error_lines)
        raise ConfigValidationError(
            f"Configuration validation failed for {config_path}:\n{detailed_msg}"
        ) from e


def save_config(config: Config, path: Union[str, Path], indent: int = 2) -> Path:
    """Save configuration to target file path, creating directories as needed."""
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    serialized = config.model_dump_json(indent=indent, by_alias=True, exclude_none=True)
    p.write_text(serialized, encoding="utf-8")
    logger.info("Saved configuration to %s", p)
    return p


def create_default_config() -> Config:
    """Generate a starter/example configuration instance."""
    return Config(
        mcpServers={
            "fetch": StdioServerConfig(
                command="uvx",
                args=["mcp-server-fetch"],
                description="Web content fetcher and markdown extractor",
            ),
        },
        settings=SchemaSlimSettings(
            db_path="~/.schemaslim/index.db",
            embedding_model="BAAI/bge-small-en-v1.5",
            similarity_threshold=0.45,
            top_k=5,
            log_level="INFO",
        ),
    )
