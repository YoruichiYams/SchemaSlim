"""Unit and integration tests for ConfigMigrator and wrap/unwrap commands."""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from schemaslim.cli import app
from schemaslim.config.migrator import ConfigMigrator, MigrationError, MigrationResult

runner = CliRunner()


@pytest.fixture
def temp_migrator_env(tmp_path: Path):
    """Fixture providing isolated client config and global config paths."""
    client_dir = tmp_path / "client_app"
    client_dir.mkdir()
    client_file = client_dir / "claude_desktop_config.json"

    initial_client_content = {
        "$schema": "https://example.com/schema.json",
        "customSetting": "active",
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "ghp_mock_token"},
            },
            "postgres": {
                "command": "docker",
                "args": ["run", "-i", "postgres-mcp"],
            },
        },
    }
    client_file.write_text(json.dumps(initial_client_content, indent=2), encoding="utf-8")

    global_config = tmp_path / "schemaslim_global" / "config.json"
    migrator = ConfigMigrator(global_config_path=global_config)

    return client_file, global_config, migrator


def test_backup_and_restore_cycle(temp_migrator_env):
    """Verify that backup is created, verified, and unwrap restores the exact original file."""
    client_file, _, migrator = temp_migrator_env
    original_content = client_file.read_text(encoding="utf-8")

    # Create backup
    backup_file = migrator.backup_config(client_file)
    assert backup_file.is_file()
    assert backup_file.name == "claude_desktop_config.json.schemaslim.bak"
    assert backup_file.read_text(encoding="utf-8") == original_content

    # Corrupt or modify client file
    client_file.write_text(json.dumps({"mcpServers": {"corrupted": True}}), encoding="utf-8")

    # Restore from backup
    migrator.restore_backup(client_file)
    assert client_file.read_text(encoding="utf-8") == original_content
    assert not backup_file.exists()


def test_merge_servers_to_global(temp_migrator_env):
    """Verify that extracted client servers merge cleanly into global config."""
    client_file, global_config, migrator = temp_migrator_env

    # Pre-populate global config with an existing server
    global_config.parent.mkdir(parents=True, exist_ok=True)
    global_config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "existing_tool": {"command": "echo", "args": ["hello"]}
                },
                "settings": {"top_k": 5},
            }
        ),
        encoding="utf-8",
    )

    servers_to_merge = {
        "github": {"command": "npx", "args": ["-y", "github-mcp"]},
        "schemaslim": {"command": "uvx", "args": ["schemaslim", "serve"]},  # Should be skipped
    }

    path, count = migrator.merge_to_global(servers_to_merge)
    assert path == global_config.resolve()
    assert count == 1  # only github, schemaslim ignored

    merged_data = json.loads(global_config.read_text(encoding="utf-8"))
    assert "existing_tool" in merged_data["mcpServers"]
    assert "github" in merged_data["mcpServers"]
    assert "schemaslim" not in merged_data["mcpServers"]
    assert merged_data["settings"]["top_k"] == 5


def test_wrap_replaces_mcpservers_preserves_other_keys(temp_migrator_env):
    """Verify that wrap replaces mcpServers with schemaslim serve while preserving top-level keys."""
    client_file, global_config, migrator = temp_migrator_env

    result = migrator.wrap(target_path=client_file, auto_confirm=True, run_index=False)
    assert result.success is True
    assert result.servers_migrated == 2

    # Check client file contents
    new_client_data = json.loads(client_file.read_text(encoding="utf-8"))
    assert new_client_data["$schema"] == "https://example.com/schema.json"
    assert new_client_data["customSetting"] == "active"
    assert "mcpServers" in new_client_data
    assert list(new_client_data["mcpServers"].keys()) == ["schemaslim"]
    assert new_client_data["mcpServers"]["schemaslim"]["command"] == "uvx"
    assert new_client_data["mcpServers"]["schemaslim"]["args"] == ["schemaslim", "serve"]

    # Check backup file existence
    backup_file = client_file.with_name(client_file.name + ".schemaslim.bak")
    assert backup_file.is_file()

    # Check global config contents
    global_data = json.loads(global_config.read_text(encoding="utf-8"))
    assert "github" in global_data["mcpServers"]
    assert "postgres" in global_data["mcpServers"]


def test_wrap_already_wrapped_is_noop(temp_migrator_env):
    """Verify that wrapping an already virtualized configuration is a safe no-op."""
    client_file, _, migrator = temp_migrator_env

    # First wrap
    migrator.wrap(target_path=client_file, auto_confirm=True, run_index=False)

    # Second wrap
    res2 = migrator.wrap(target_path=client_file, auto_confirm=True, run_index=False)
    assert res2.success is True
    assert res2.servers_migrated == 0
    assert "already virtualized" in res2.message


def test_unwrap_restores_original_and_removes_backup(temp_migrator_env):
    """Verify that unwrap restores original client configuration and removes backup file."""
    client_file, _, migrator = temp_migrator_env
    original_text = client_file.read_text(encoding="utf-8")

    # Wrap
    migrator.wrap(target_path=client_file, auto_confirm=True, run_index=False)
    backup_file = client_file.with_name(client_file.name + ".schemaslim.bak")
    assert backup_file.is_file()

    # Unwrap
    unwrap_res = migrator.unwrap(target_path=client_file, auto_confirm=True)
    assert unwrap_res.success is True
    assert not backup_file.exists()
    assert json.loads(client_file.read_text(encoding="utf-8")) == json.loads(original_text)


def test_unwrap_missing_backup_raises_error(temp_migrator_env):
    """Verify that unwrap raises MigrationError when backup file is missing."""
    client_file, _, migrator = temp_migrator_env
    with pytest.raises(MigrationError) as exc_info:
        migrator.unwrap(target_path=client_file, auto_confirm=True)
    assert "Backup file not found" in str(exc_info.value)


def test_cli_wrap_with_yes_flag(temp_migrator_env, monkeypatch):
    """Verify CLI wrap command runs non-interactively with --yes / -y."""
    client_file, global_config, _ = temp_migrator_env

    # Redirect GLOBAL_CONFIG_PATH in migrator to temp path
    monkeypatch.setattr("schemaslim.config.migrator.GLOBAL_CONFIG_PATH", global_config)

    result = runner.invoke(
        app,
        ["wrap", "--path", str(client_file), "--yes", "--no-index"],
    )
    assert result.exit_code == 0
    assert "Successfully wrapped" in result.output

    # Client config should be wrapped
    client_data = json.loads(client_file.read_text(encoding="utf-8"))
    assert "schemaslim" in client_data["mcpServers"]


def test_cli_unwrap_with_yes_flag(temp_migrator_env, monkeypatch):
    """Verify CLI unwrap command runs non-interactively with --yes / -y."""
    client_file, global_config, migrator = temp_migrator_env

    monkeypatch.setattr("schemaslim.config.migrator.GLOBAL_CONFIG_PATH", global_config)

    # First wrap it
    migrator.wrap(target_path=client_file, auto_confirm=True, run_index=False)

    # Then unwrap via CLI
    result = runner.invoke(
        app,
        ["unwrap", "--path", str(client_file), "--yes"],
    )
    assert result.exit_code == 0
    assert "Successfully restored" in result.output

    # Client config should be restored
    client_data = json.loads(client_file.read_text(encoding="utf-8"))
    assert "github" in client_data["mcpServers"]
    assert "schemaslim" not in client_data["mcpServers"]


def test_wrap_user_cancelled(temp_migrator_env, monkeypatch):
    """Verify that when user cancels the interactive prompt, configuration is not changed."""
    client_file, _, migrator = temp_migrator_env
    original_text = client_file.read_text(encoding="utf-8")

    # Simulate user rejecting prompt
    monkeypatch.setattr(
        "schemaslim.ui.menu.prompt_confirmation",
        lambda *args, **kwargs: False,
    )

    result = migrator.wrap(target_path=client_file, auto_confirm=False, run_index=False)
    assert result.success is False
    assert result.cancelled is True
    assert client_file.read_text(encoding="utf-8") == original_text
    assert not client_file.with_name(client_file.name + ".schemaslim.bak").exists()
