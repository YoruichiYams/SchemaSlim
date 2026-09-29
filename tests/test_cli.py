"""Comprehensive test suite for SchemaSlim CLI and Terminal Menu interaction."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from schemaslim import __version__
from schemaslim.cli import app
from schemaslim.config.models import Config, StdioServerConfig
from schemaslim.storage.models import IndexedTool, SearchResult
from schemaslim.ui.menu import _read_key, make_header, prompt_confirmation, select_option

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. UI Menu & Interactive Keypress Tests (schemaslim/ui/menu.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMenuPrimitives:
    """Test terminal formatting, escape sequences, and interactive menu loops."""

    def test_make_header_formatting(self):
        hdr = make_header("Test Title", width=40)
        assert hdr.startswith("◆ TEST TITLE ─")
        assert len(hdr) >= 40

        # Small width clamp
        hdr_small = make_header("A Very Long Header Title That Exceeds Width", width=10)
        assert hdr_small.endswith("───")

    def test_read_key_windows(self):
        """Test Windows msvcrt key mappings."""
        with patch("sys.platform", "win32"), patch("msvcrt.getwch") as mock_getwch:
            # Test UP arrow (\xe0 + H)
            mock_getwch.side_effect = ["\xe0", "H"]
            assert _read_key() == "UP"

            # Test DOWN arrow (\x00 + P)
            mock_getwch.side_effect = ["\x00", "P"]
            assert _read_key() == "DOWN"

            # Test other special key (\xe0 + K)
            mock_getwch.side_effect = ["\xe0", "K"]
            assert _read_key() == "OTHER"

            # Test ENTER (\r and \n)
            mock_getwch.side_effect = ["\r"]
            assert _read_key() == "ENTER"
            mock_getwch.side_effect = ["\n"]
            assert _read_key() == "ENTER"

            # Test SPACE
            mock_getwch.side_effect = [" "]
            assert _read_key() == "SPACE"

            # Test quick-keys (y, n, q)
            mock_getwch.side_effect = ["Y"]
            assert _read_key() == "y"
            mock_getwch.side_effect = ["N"]
            assert _read_key() == "n"
            mock_getwch.side_effect = ["q"]
            assert _read_key() == "q"

            # Test regular char
            mock_getwch.side_effect = ["a"]
            assert _read_key() == "a"

            # Test KeyboardInterrupt (\x03)
            mock_getwch.side_effect = ["\x03"]
            with pytest.raises(KeyboardInterrupt):
                _read_key()

    def test_read_key_posix(self):
        """Test POSIX termios / tty key mappings."""
        mock_termios = MagicMock()
        mock_tty = MagicMock()
        with patch.dict(sys.modules, {"termios": mock_termios, "tty": mock_tty}), \
             patch("sys.platform", "linux"), \
             patch("sys.stdin.fileno", return_value=0), \
             patch("sys.stdin.read") as mock_read:

            # Test UP arrow (\x1b + [ + A)
            mock_read.side_effect = ["\x1b", "[", "A"]
            assert _read_key() == "UP"

            # Test DOWN arrow (\x1b + [ + B)
            mock_read.side_effect = ["\x1b", "[", "B"]
            assert _read_key() == "DOWN"

            # Test lone ESC
            mock_read.side_effect = ["\x1b", "x"]
            assert _read_key() == "ESC"

            # Test ENTER and SPACE
            mock_read.side_effect = ["\n"]
            assert _read_key() == "ENTER"
            mock_read.side_effect = [" "]
            assert _read_key() == "SPACE"

            # Test quick-keys
            mock_read.side_effect = ["Y"]
            assert _read_key() == "y"

            # Test regular char
            mock_read.side_effect = ["z"]
            assert _read_key() == "z"

            # Test KeyboardInterrupt
            mock_read.side_effect = ["\x03"]
            with pytest.raises(KeyboardInterrupt):
                _read_key()

    def test_prompt_confirmation_non_interactive(self):
        with patch("sys.stdin.isatty", return_value=False):
            assert prompt_confirmation(default=True) is True
            assert prompt_confirmation(default=False) is False

    def test_prompt_confirmation_interactive_keys(self):
        with patch("sys.stdin.isatty", return_value=True):
            # Quick-confirm via 'y'
            with patch("schemaslim.ui.menu._read_key", side_effect=["y"]):
                assert prompt_confirmation(default=False) is True

            # Quick-cancel via 'n'
            with patch("schemaslim.ui.menu._read_key", side_effect=["n"]):
                assert prompt_confirmation(default=True) is False

            # Quick-cancel via 'q'
            with patch("schemaslim.ui.menu._read_key", side_effect=["q"]):
                assert prompt_confirmation(default=True) is False

            # Toggle with SPACE then confirm with ENTER
            with patch("schemaslim.ui.menu._read_key", side_effect=["SPACE", "ENTER"]):
                # Started with True (idx 0), toggled to False (idx 1) -> returns False
                assert prompt_confirmation(default=True) is False

            # Toggle with UP then confirm with ENTER
            with patch("schemaslim.ui.menu._read_key", side_effect=["UP", "ENTER"]):
                assert prompt_confirmation(default=False) is True

            # KeyboardInterrupt returns False
            with patch("schemaslim.ui.menu._read_key", side_effect=KeyboardInterrupt):
                assert prompt_confirmation(default=True) is False

    def test_select_option_non_interactive(self):
        with patch("sys.stdin.isatty", return_value=False):
            assert select_option(options=[("A", "a"), ("B", "b")], default_index=1) == 1
            # Empty or single option returns default immediately
            assert select_option(options=[("Only", "one")], default_index=0) == 0

    def test_select_option_interactive_navigation(self):
        opts = [("Opt1", "det1"), ("Opt2", "det2"), ("Opt3", "det3")]
        with patch("sys.stdin.isatty", return_value=True):
            # Navigate DOWN then ENTER -> index 1
            with patch("schemaslim.ui.menu._read_key", side_effect=["DOWN", "ENTER"]):
                assert select_option(options=opts, default_index=0) == 1

            # Navigate UP (wraps around) then ENTER -> index 2
            with patch("schemaslim.ui.menu._read_key", side_effect=["UP", "ENTER"]):
                assert select_option(options=opts, default_index=0) == 2

            # Quit key 'q' returns current index
            with patch("schemaslim.ui.menu._read_key", side_effect=["q"]):
                assert select_option(options=opts, default_index=1) == 1

            # KeyboardInterrupt returns default_index
            with patch("schemaslim.ui.menu._read_key", side_effect=KeyboardInterrupt):
                assert select_option(options=opts, default_index=2) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SchemaSlim Core CLI Commands (schemaslim/cli.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCliCommands:
    """Test CLI commands, flags, argument parsing, and error branches."""

    def test_version_command(self):
        res = runner.invoke(app, ["version"])
        assert res.exit_code == 0
        assert f"v{__version__}" in res.stdout

        res2 = runner.invoke(app, ["--version"])
        assert res2.exit_code == 0
        assert f"v{__version__}" in res2.stdout

    def test_help_command(self):
        res = runner.invoke(app, ["--help"])
        assert res.exit_code == 0
        assert "SchemaSlim: Lightweight local virtualizing reverse-proxy" in res.stdout

    def test_config_validate_valid_and_invalid(self, tmp_path: Path):
        valid_file = tmp_path / "valid.json"
        valid_file.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

        # Valid with auto-discovery or explicit path
        res = runner.invoke(app, ["config", "validate", str(valid_file), "-v"])
        assert res.exit_code == 0
        assert "valid" in res.stdout.lower()

        # Missing file
        res_missing = runner.invoke(app, ["config", "validate", str(tmp_path / "nonexistent.json")])
        assert res_missing.exit_code == 1

        # Invalid schema
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text(json.dumps({"mcpServers": {"bad__server": {}}}), encoding="utf-8")
        res_invalid = runner.invoke(app, ["config", "validate", str(invalid_file), "--allow-cwd"])
        assert res_invalid.exit_code == 1

    def test_config_show_command(self, tmp_path: Path):
        cfg_file = tmp_path / "schemaslim.json"
        cfg_file.write_text(
            json.dumps({"mcpServers": {"demo": {"command": "python", "args": ["demo.py"]}}}),
            encoding="utf-8",
        )
        res = runner.invoke(app, ["config", "show", str(cfg_file), "--allow-cwd"])
        assert res.exit_code == 0
        assert "demo" in res.stdout

        # Show missing config fails
        res_fail = runner.invoke(app, ["config", "show", str(tmp_path / "missing.json")])
        assert res_fail.exit_code == 1

    def test_config_init_command(self, tmp_path: Path):
        out_file = tmp_path / "new_schemaslim.json"
        res = runner.invoke(app, ["config", "init", str(out_file)])
        assert res.exit_code == 0
        assert out_file.exists()

        # Fails if already exists without force
        res_exists = runner.invoke(app, ["config", "init", str(out_file)])
        assert res_exists.exit_code == 1

        # Overwrites with force
        res_force = runner.invoke(app, ["config", "init", str(out_file), "-f"])
        assert res_force.exit_code == 0

    def test_stats_command(self, tmp_path: Path):
        db_file = tmp_path / "test.db"
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(
            json.dumps({"mcpServers": {}, "settings": {"db_path": str(db_file)}}),
            encoding="utf-8",
        )

        res = runner.invoke(app, ["stats", "-c", str(cfg_file), "--allow-cwd"])
        assert res.exit_code == 0
        assert "Empty" in res.stdout or "Indexed Tools" in res.stdout

        # Fails on missing config
        res_err = runner.invoke(app, ["stats", "-c", str(tmp_path / "missing.json")])
        assert res_err.exit_code == 1

    def test_search_command_empty_and_results(self, tmp_path: Path):
        db_file = tmp_path / "test.db"
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(
            json.dumps({"mcpServers": {}, "settings": {"db_path": str(db_file)}}),
            encoding="utf-8",
        )

        # Fails when DB is empty
        res_empty = runner.invoke(app, ["search", "test query", "-c", str(cfg_file), "--allow-cwd"])
        assert res_empty.exit_code == 1
        assert "Vector DB is empty" in res_empty.stdout

        # Mock vector store with results
        mock_tool = IndexedTool.create(
            server_name="srv",
            tool_name="tool",
            description="A sample tool description",
            parameters={},
        )
        mock_result = SearchResult(
            tool=mock_tool,
            score=0.88,
            vector_score=0.9,
            lexical_score=0.8,
        )
        with patch("schemaslim.cli.VectorStore") as mock_vs_cls:
            mock_vs = MagicMock()
            mock_vs.get_total_tools_count.return_value = 5
            mock_vs.hybrid_search.return_value = [mock_result]
            mock_vs_cls.return_value.__enter__.return_value = mock_vs

            res_found = runner.invoke(app, ["search", "query", "-c", str(cfg_file), "--allow-cwd"])
            assert res_found.exit_code == 0
            assert "srv__tool" in res_found.stdout

            # Mock no results matching
            mock_vs.hybrid_search.return_value = []
            res_none = runner.invoke(app, ["search", "nomatch", "-c", str(cfg_file), "--allow-cwd"])
            assert res_none.exit_code == 0
            assert "No tools found matching query" in res_none.stdout

    def test_index_command(self, tmp_path: Path):
        cfg_file = tmp_path / "cfg.json"
        cfg_file.write_text(
            json.dumps({
                "mcpServers": {
                    "demo": {"command": "python", "args": ["demo.py"]}
                },
                "settings": {"db_path": str(tmp_path / "index.db")}
            }),
            encoding="utf-8",
        )

        mock_tool = IndexedTool.create(
            server_name="demo",
            tool_name="hello",
            description="Says hello",
            parameters={},
        )

        with patch("schemaslim.cli.SchemaHarvester.harvest_all", return_value=([mock_tool], {})):
            res = runner.invoke(app, ["index", "-c", str(cfg_file), "--allow-cwd", "-f"])
            assert res.exit_code == 0
            assert "Indexing complete" in res.stdout

        # Test index with no active servers
        empty_cfg = tmp_path / "empty_cfg.json"
        empty_cfg.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
        res_empty = runner.invoke(app, ["index", "-c", str(empty_cfg), "--allow-cwd"])
        assert res_empty.exit_code == 0
        assert "No active MCP servers found" in res_empty.stdout

    def test_benchmark_command(self):
        mock_report = MagicMock()
        mock_report.servers_count = 2
        mock_report.total_tools = 10
        mock_report.tokens_baseline = 2500
        mock_report.avg_tokens_virtualized = 280
        mock_report.avg_tokens_saved = 2220
        mock_report.compression_pct = 88.8
        mock_report.latency_mean_ms = 1.2
        mock_report.latency_p50_ms = 1.1
        mock_report.latency_p95_ms = 1.5
        mock_report.queries_detail = []
        mock_report.model_dump_json.return_value = '{"compression_pct": 88.8}'

        with patch("schemaslim.benchmark.BenchmarkRunner.run", return_value=mock_report):
            res = runner.invoke(app, ["benchmark", "-r", "3"])
            assert res.exit_code == 0
            assert "Benchmark Summary" in res.stdout or "BENCHMARK" in res.stdout

            # Test benchmark JSON output
            res_json = runner.invoke(app, ["benchmark", "-o", "json"])
            assert res_json.exit_code == 0
            assert "compression_pct" in res_json.stdout

            # Test invalid output format
            res_invalid = runner.invoke(app, ["benchmark", "-o", "invalid_format"])
            assert res_invalid.exit_code == 1

    def test_wrap_and_unwrap_cli_flows(self, tmp_path: Path):
        client_cfg = tmp_path / "claude_desktop_config.json"
        client_cfg.write_text(
            json.dumps({"mcpServers": {"local": {"command": "node", "args": ["app.js"]}}}),
            encoding="utf-8",
        )

        # Wrap with --yes and --no-index
        res_wrap = runner.invoke(app, ["wrap", "--path", str(client_cfg), "--yes", "--no-index"])
        assert res_wrap.exit_code == 0
        assert "Virtualization Active" in res_wrap.stdout

        # Unwrap with --yes
        res_unwrap = runner.invoke(app, ["unwrap", "--path", str(client_cfg), "--yes"])
        assert res_unwrap.exit_code == 0
        assert "Original configuration restored" in res_unwrap.stdout

        # Wrap failure on invalid file
        res_fail = runner.invoke(app, ["wrap", "--path", str(tmp_path / "nonexistent.json"), "--yes"])
        assert res_fail.exit_code == 1

        # Unwrap failure without backup
        res_unwrap_fail = runner.invoke(app, ["unwrap", "--path", str(client_cfg), "--yes"])
        assert res_unwrap_fail.exit_code == 1

    def test_serve_cli_missing_config_fails(self, tmp_path: Path):
        # Serve with non-existent config exits with code 1
        res = runner.invoke(app, ["serve", "-c", str(tmp_path / "does_not_exist.json")])
        assert res.exit_code == 1
