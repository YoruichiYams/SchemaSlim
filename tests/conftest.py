"""Pytest fixtures for SchemaSlim tests."""

import json
from pathlib import Path
from typing import Any, Dict, Generator
import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).parent.parent.resolve()


@pytest.fixture
def example_config_path(project_root: Path) -> Path:
    """Return the path to schemaslim.example.json."""
    path = project_root / "schemaslim.example.json"
    assert path.is_file(), f"schemaslim.example.json must exist at {path}"
    return path


@pytest.fixture
def valid_config_dict() -> Dict[str, Any]:
    """Return a dictionary representing a full valid configuration."""
    return {
        "mcpServers": {
            "fetch": {
                "transport": "stdio",
                "command": "uvx",
                "args": ["mcp-server-fetch"],
                "env": {"DEBUG": "true"},
                "enabled": True,
                "description": "Fetcher tool",
            },
            "remote": {
                "transport": "sse",
                "url": "https://api.example.com/sse",
                "headers": {"Authorization": "Bearer test-key"},
                "enabled": True,
            },
            "disabled_server": {
                "command": "node",
                "args": ["server.js"],
                "enabled": False,
            },
        },
        "settings": {
            "db_path": "./test_index.db",
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "similarity_threshold": 0.5,
            "top_k": 7,
            "max_search_results": 15,
            "log_level": "DEBUG",
        },
    }


@pytest.fixture
def claude_style_config_dict() -> Dict[str, Any]:
    """Return a config dictionary omitting explicit transport fields (Claude Desktop style)."""
    return {
        "mcpServers": {
            "cli_tool": {
                "command": "python",
                "args": ["-m", "tool"],
            },
            "sse_tool": {
                "url": "http://127.0.0.1:8000/sse",
            },
        }
    }


@pytest.fixture
def temp_config_file(tmp_path: Path, valid_config_dict: Dict[str, Any]) -> Path:
    """Write valid_config_dict to a temporary file and return its Path."""
    cfg_file = tmp_path / "test_schemaslim.json"
    cfg_file.write_text(json.dumps(valid_config_dict, indent=2), encoding="utf-8")
    return cfg_file
