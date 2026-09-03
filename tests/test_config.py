"""Smoke and unit tests for SchemaSlim configuration loading, validation, and CLI."""

import json
from pathlib import Path
from typing import Any, Dict
import pytest
from typer.testing import CliRunner

from schemaslim import __version__
from schemaslim.cli import app
from schemaslim.config.loader import (
    ConfigNotFoundError,
    ConfigValidationError,
    find_config_file,
    load_config,
    save_config,
)
from schemaslim.config.models import (
    Config,
    SchemaSlimSettings,
    SseServerConfig,
    StdioServerConfig,
)

runner = CliRunner()


class TestConfigModels:
    """Test Pydantic model behaviors and validation constraints."""

    def test_valid_config_parsing(self, valid_config_dict: Dict[str, Any]):
        cfg = Config.model_validate(valid_config_dict)
        assert len(cfg.mcpServers) == 3
        assert len(cfg.active_servers) == 2
        assert "disabled_server" not in cfg.active_servers
        assert isinstance(cfg.mcpServers["fetch"], StdioServerConfig)
        assert isinstance(cfg.mcpServers["remote"], SseServerConfig)
        assert cfg.settings.top_k == 7
        assert cfg.settings.log_level == "DEBUG"

    def test_claude_desktop_style_transport_inference(
        self, claude_style_config_dict: Dict[str, Any]
    ):
        cfg = Config.model_validate(claude_style_config_dict)
        assert isinstance(cfg.mcpServers["cli_tool"], StdioServerConfig)
        assert cfg.mcpServers["cli_tool"].command == "python"
        assert isinstance(cfg.mcpServers["sse_tool"], SseServerConfig)
        assert str(cfg.mcpServers["sse_tool"].url).rstrip("/") == "http://127.0.0.1:8000/sse"
        assert cfg.settings.top_k == 5  # default value

    def test_empty_command_validation_error(self):
        with pytest.raises(Exception):
            StdioServerConfig(command="   ")

    def test_invalid_url_validation_error(self):
        with pytest.raises(Exception):
            SseServerConfig(url="not-a-valid-url")  # type: ignore

    def test_invalid_log_level_validation_error(self):
        with pytest.raises(Exception):
            SchemaSlimSettings(log_level="NOT_A_LEVEL")

    def test_invalid_threshold_range(self):
        with pytest.raises(Exception):
            SchemaSlimSettings(similarity_threshold=1.5)


class TestConfigLoader:
    """Test loader file resolution, JSON decoding, and error handling."""

    def test_load_valid_file(self, temp_config_file: Path):
        cfg = load_config(temp_config_file)
        assert isinstance(cfg, Config)
        assert "fetch" in cfg.mcpServers

    def test_load_example_config_file(self, example_config_path: Path):
        cfg = load_config(example_config_path)
        assert isinstance(cfg, Config)
        assert "filesystem" in cfg.mcpServers
        assert "fetch" in cfg.mcpServers
        assert "remote_api" in cfg.mcpServers
        assert cfg.mcpServers["remote_api"].transport == "sse"

    def test_load_nonexistent_file_raises_not_found(self, tmp_path: Path):
        nonexistent = tmp_path / "does_not_exist.json"
        with pytest.raises(ConfigNotFoundError) as exc_info:
            load_config(nonexistent)
        assert "not found" in str(exc_info.value).lower()

    def test_load_invalid_json_raises_validation_error(self, tmp_path: Path):
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{ unclosed json: ", encoding="utf-8")
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(corrupt)
        assert "json decode error" in str(exc_info.value).lower()

    def test_load_non_dict_json_raises_validation_error(self, tmp_path: Path):
        list_json = tmp_path / "list.json"
        list_json.write_text("[\"item1\", \"item2\"]", encoding="utf-8")
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(list_json)
        assert "must be a json object" in str(exc_info.value).lower()

    def test_env_var_config_discovery(self, temp_config_file: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SCHEMASLIM_CONFIG", str(temp_config_file))
        resolved = find_config_file()
        assert resolved == temp_config_file.resolve()
        cfg = load_config()
        assert isinstance(cfg, Config)

    def test_save_config_roundtrip(self, tmp_path: Path, valid_config_dict: Dict[str, Any]):
        original_cfg = Config.model_validate(valid_config_dict)
        dest = tmp_path / "subdir" / "saved_config.json"
        saved_path = save_config(original_cfg, dest)
        assert saved_path.is_file()

        loaded_cfg = load_config(saved_path)
        assert len(loaded_cfg.mcpServers) == len(original_cfg.mcpServers)
        assert loaded_cfg.settings.top_k == original_cfg.settings.top_k


class TestCliCommands:
    """Test CLI subcommands via Typer CliRunner."""

    def test_version_command(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout
        assert "SchemaSlim" in result.stdout

    def test_config_validate_success(self, temp_config_file: Path):
        result = runner.invoke(app, ["config", "validate", str(temp_config_file)])
        assert result.exit_code == 0
        assert "Configuration Valid" in result.stdout
        assert "Configuration is valid" in result.stdout

    def test_config_validate_verbose(self, temp_config_file: Path):
        result = runner.invoke(app, ["config", "validate", str(temp_config_file), "--verbose"])
        assert result.exit_code == 0
        assert "Configured MCP Servers" in result.stdout
        assert "fetch" in result.stdout

    def test_config_validate_missing_file(self, tmp_path: Path):
        missing = tmp_path / "missing.json"
        result = runner.invoke(app, ["config", "validate", str(missing)])
        assert result.exit_code == 1
        assert "Configuration Not Found" in result.stdout

    def test_config_show(self, temp_config_file: Path):
        result = runner.invoke(app, ["config", "show", str(temp_config_file)])
        assert result.exit_code == 0
        assert "mcpServers" in result.stdout
        assert "fetch" in result.stdout

    def test_config_init(self, tmp_path: Path):
        target = tmp_path / "new_schemaslim.json"
        result = runner.invoke(app, ["config", "init", str(target)])
        assert result.exit_code == 0
        assert target.is_file()

        # Try without --force when file already exists
        result_fail = runner.invoke(app, ["config", "init", str(target)])
        assert result_fail.exit_code == 1
        assert "File already exists" in result_fail.stdout

        # Overwrite with --force
        result_force = runner.invoke(app, ["config", "init", str(target), "--force"])
        assert result_force.exit_code == 0

    def test_index_help(self):
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        assert "Harvest tool schemas" in result.stdout

    def test_search_help(self):
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "hybrid semantic search" in result.stdout
