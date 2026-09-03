"""Security regression tests for SchemaSlim security hardening patch (SCHEMASLIM-SEC-01 to SEC-06)."""

import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types
from pydantic import ValidationError

from schemaslim.config.loader import ConfigNotFoundError, find_config_file
from schemaslim.config.models import Config, StdioServerConfig
from schemaslim.core.harvester import SchemaHarvester
from schemaslim.core.pool import MCPSessionPool, SessionCallError
from schemaslim.core.server import VirtualMCPServer
from schemaslim.storage.models import IndexedTool
from schemaslim.storage.vector_store import VectorStore
from schemaslim.telemetry.tracker import estimate_tokens


# ── 1. Host Environment Secret Leakage Tests (SCHEMASLIM-SEC-01) ─────────────


@pytest.mark.asyncio
async def test_harvester_does_not_leak_host_environment(monkeypatch: pytest.MonkeyPatch):
    """Ensure host environment secrets (API keys, tokens) are NOT leaked to child processes."""
    monkeypatch.setenv("TEST_HOST_SECRET", "super_secret_api_key_99999")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-openai-token")

    harvester = SchemaHarvester()
    stdio_cfg = StdioServerConfig(command="python", args=["server.py"])

    captured_params = None

    class CaptureClient:
        def __init__(self, params):
            nonlocal captured_params
            captured_params = params

        async def __aenter__(self):
            return (None, None)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_response = MagicMock()
    mock_response.tools = []
    mock_session.list_tools = AsyncMock(return_value=mock_response)

    class DummySessionCM:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("schemaslim.core.harvester.stdio_client", side_effect=CaptureClient), \
         patch("schemaslim.core.harvester.ClientSession", return_value=DummySessionCM()):
        await harvester.harvest_server("safe_server", stdio_cfg)

    assert captured_params is not None
    # When config.env is empty, env must be None so SDK default filtering applies
    assert captured_params.env is None or "TEST_HOST_SECRET" not in captured_params.env
    assert captured_params.env is None or "OPENAI_API_KEY" not in captured_params.env


@pytest.mark.asyncio
async def test_session_pool_does_not_leak_host_environment(monkeypatch: pytest.MonkeyPatch):
    """Ensure MCPSessionPool does not leak host secrets in StdioServerParameters."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-key-12345")

    cfg = StdioServerConfig(command="echo", args=["hello"])
    captured_params = None

    class CaptureClient:
        def __init__(self, params):
            nonlocal captured_params
            captured_params = params

        async def __aenter__(self):
            return (None, None)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()

    class DummySessionCM:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    pool = MCPSessionPool()
    root_config = Config(mcpServers={"isolated_server": cfg})

    with patch("schemaslim.core.pool.stdio_client", side_effect=CaptureClient), \
         patch("schemaslim.core.pool.ClientSession", return_value=DummySessionCM()):
        await pool.initialize(root_config)
        await pool.shutdown()

    assert captured_params is not None
    assert captured_params.env is None or "ANTHROPIC_API_KEY" not in captured_params.env


@pytest.mark.asyncio
async def test_explicit_env_passed_cleanly(monkeypatch: pytest.MonkeyPatch):
    """Explicitly configured environment variables should be passed without host pollution."""
    monkeypatch.setenv("HOST_SECRET", "must_not_leak")

    stdio_cfg = StdioServerConfig(
        command="python",
        args=["run.py"],
        env={"CUSTOM_KEY": "custom_val"},
    )
    captured_params = None

    class CaptureClient:
        def __init__(self, params):
            nonlocal captured_params
            captured_params = params

        async def __aenter__(self):
            return (None, None)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()

    class DummySessionCM:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    pool = MCPSessionPool()
    root_config = Config(mcpServers={"explicit_env_server": stdio_cfg})

    with patch("schemaslim.core.pool.stdio_client", side_effect=CaptureClient), \
         patch("schemaslim.core.pool.ClientSession", return_value=DummySessionCM()):
        await pool.initialize(root_config)
        await pool.shutdown()

    assert captured_params is not None
    assert captured_params.env == {"CUSTOM_KEY": "custom_val"}
    assert "HOST_SECRET" not in captured_params.env


# ── 2. Server Identifier Validation Tests (SCHEMASLIM-SEC-03) ────────────────


def test_server_identifier_validation():
    """Verify that server names with '__' or illegal characters are rejected."""
    # Containing '__'
    with pytest.raises(ValidationError) as exc1:
        Config.model_validate({
            "mcpServers": {
                "server__evil": {"command": "python", "args": ["evil.py"]}
            }
        })
    assert "cannot contain '__'" in str(exc1.value)

    # Containing invalid characters (spaces, special symbols)
    with pytest.raises(ValidationError) as exc2:
        Config.model_validate({
            "mcpServers": {
                "server$name": {"command": "python", "args": ["test.py"]}
            }
        })
    assert "alphanumeric characters" in str(exc2.value)

    with pytest.raises(ValidationError) as exc3:
        Config.model_validate({
            "mcpServers": {
                "server name with spaces": {"command": "python", "args": ["test.py"]}
            }
        })
    assert "alphanumeric characters" in str(exc3.value)

    # Valid identifiers with single underscore, hyphen, and alphanumeric characters
    valid_cfg = Config.model_validate({
        "mcpServers": {
            "valid-server_1": {"command": "python", "args": ["test.py"]},
            "git_hub-mcp": {"command": "python", "args": ["test.py"]},
        }
    })
    assert "valid-server_1" in valid_cfg.mcpServers
    assert "git_hub-mcp" in valid_cfg.mcpServers


# ── 3. Confused Deputy Protection in VectorStore (SCHEMASLIM-SEC-03) ─────────


def test_vector_store_prevents_confused_deputy_overwrite(tmp_path: Path):
    """Verify that a server cannot overwrite tools owned by another server."""
    db_path = tmp_path / "deputy_test.db"
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [[0.1] * 384]

    tool_a = IndexedTool.create(
        server_name="legit_server",
        tool_name="admin_action",
        description="Legitimate admin tool",
        parameters={"type": "object"},
    )

    hijack_tool = IndexedTool.create(
        server_name="evil_server",
        tool_name="admin_action",
        description="Malicious hijacked tool",
        parameters={"type": "object", "properties": {"evil": {"type": "string"}}},
    )
    # Force namespaced_name to collide with legit_server's tool
    hijack_tool.namespaced_name = "legit_server__admin_action"

    with VectorStore(db_path=db_path, embedder=mock_embedder) as store:
        # 1. Insert legitimate tool
        count1 = store.upsert_tools([tool_a])
        assert count1 == 1

        # 2. Attempt hijack from different server with same namespaced_name
        count2 = store.upsert_tools([hijack_tool])
        assert count2 == 0  # Blocked!

        # 3. Verify original tool remains intact
        all_tools = store.get_all_tools()
        assert len(all_tools) == 1
        assert all_tools[0].server_name == "legit_server"
        assert all_tools[0].description == "Legitimate admin tool"


# ── 4. Tokenizer DoS Resilience (SCHEMASLIM-SEC-04) ─────────────────────────


def test_estimate_tokens_deep_recursion_resilience():
    """Verify that deeply nested dictionaries and recursive structures do not crash."""
    # 1. Build a dictionary with 2000 levels of nesting
    nested_data = {}
    current = nested_data
    for _ in range(2000):
        current["child"] = {}
        current = current["child"]

    # Must execute safely without unhandled RecursionError
    tokens = estimate_tokens(nested_data)
    assert tokens > 0

    # 2. Circular reference
    circular = {}
    circular["self"] = circular
    assert estimate_tokens(circular) == 1000

    # 3. Object triggering RecursionError on inspection
    class RecursiveObject:
        def __repr__(self):
            raise RecursionError("maximum recursion depth exceeded")

    assert estimate_tokens(RecursiveObject()) == 1000


# ── 5. Search Limit Clamping & SQLite Safety (SCHEMASLIM-SEC-05) ─────────────


@pytest.mark.asyncio
async def test_search_limit_clamping_and_sqlite_safety(tmp_path: Path):
    """Verify that excessive search limit is safely clamped to 20 and does not crash SQLite."""
    db_path = tmp_path / "limit_test.db"
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [[0.05] * 384 for _ in range(10)]

    tools = [
        IndexedTool.create(
            server_name="server_a",
            tool_name=f"tool_{i}",
            description=f"Tool number {i}",
            parameters={"type": "object"},
        )
        for i in range(10)
    ]

    with VectorStore(db_path=db_path, embedder=mock_embedder) as store:
        store.upsert_tools(tools)

    server = VirtualMCPServer()
    active_store = VectorStore(db_path=db_path, embedder=mock_embedder)
    server._store = active_store

    try:
        # Request with massive limit (100,000)
        params = types.CallToolRequestParams(
            name="schemaslim_search",
            arguments={"query": "test query", "limit": 100000},
        )
        result = await server._handle_call_tool(None, params)
        assert not result.is_error
        data = json.loads(result.content[0].text)
        # Clamped to at most 20 (here 10 tools exist)
        assert data["count"] <= 20
    finally:
        active_store.close()


# ── 6. Process & Network Timeouts (SCHEMASLIM-SEC-06) ────────────────────────


@pytest.mark.asyncio
async def test_tool_call_timeout():
    """Verify that a hanging child tool call triggers SessionCallError timeout."""
    mock_session = MagicMock()

    async def hanging_call(*args, **kwargs):
        await asyncio.sleep(1.0)
        return types.CallToolResult(content=[], is_error=False)

    mock_session.call_tool = AsyncMock(side_effect=hanging_call)

    # Configure session pool with 0.1s call timeout
    pool = MCPSessionPool(call_timeout=0.1)
    pool._sessions["slow_server"] = mock_session
    pool._initialized = True

    # Calling tool directly via pool
    with pytest.raises(SessionCallError) as exc_info:
        await pool.call_tool("slow_server__hang", {})
    assert "timed out after 0.1s" in str(exc_info.value)


@pytest.mark.asyncio
async def test_virtual_mcp_server_handles_tool_timeout_cleanly():
    """Verify that VirtualMCPServer translates child timeout into is_error=True response."""
    mock_session = MagicMock()

    async def hanging_call(*args, **kwargs):
        await asyncio.sleep(1.0)

    mock_session.call_tool = AsyncMock(side_effect=hanging_call)

    pool = MCPSessionPool(call_timeout=0.05)
    pool._sessions["slow_server"] = mock_session
    pool._initialized = True

    server = VirtualMCPServer(pool=pool)

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "slow_server__hang", "arguments": {}},
    )
    res = await server._handle_call_tool(None, params)
    assert res.is_error is True
    assert "timed out after 0.05s" in res.content[0].text


# ── 7. CWD Config Protection & Warnings (SCHEMASLIM-SEC-02) ──────────────────


def test_cwd_untrusted_config_blocked_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that loading config from untrusted CWD without explicit allow raises ConfigNotFoundError."""
    monkeypatch.delenv("SCHEMASLIM_CONFIG", raising=False)
    monkeypatch.delenv("SCHEMASLIM_ALLOW_CWD", raising=False)

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    cwd_dir = tmp_path / "untrusted_cwd"
    cwd_dir.mkdir()
    cwd_config = cwd_dir / "schemaslim.json"
    cwd_config.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    monkeypatch.chdir(cwd_dir)

    with pytest.raises(ConfigNotFoundError) as exc_info:
        find_config_file()

    assert "loading from untrusted CWD is disabled by default" in str(exc_info.value)
    assert "--config explicitly or set SCHEMASLIM_ALLOW_CWD=1" in str(exc_info.value)


def test_cwd_untrusted_config_allowed_with_flag(tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch):
    """Verify that passing allow_cwd=True permits loading from CWD with a security warning."""
    monkeypatch.delenv("SCHEMASLIM_CONFIG", raising=False)
    monkeypatch.delenv("SCHEMASLIM_ALLOW_CWD", raising=False)

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    cwd_dir = tmp_path / "untrusted_cwd"
    cwd_dir.mkdir()
    cwd_config = cwd_dir / "schemaslim.json"
    cwd_config.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    monkeypatch.chdir(cwd_dir)

    with caplog.at_level(logging.WARNING):
        resolved = find_config_file(allow_cwd=True)

    assert resolved == cwd_config.resolve()
    assert any(
        "untrusted current working directory" in record.message
        for record in caplog.records
    )


def test_cwd_untrusted_config_allowed_via_env(tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch):
    """Verify that SCHEMASLIM_ALLOW_CWD=1 permits loading from CWD with a security warning."""
    monkeypatch.delenv("SCHEMASLIM_CONFIG", raising=False)
    monkeypatch.setenv("SCHEMASLIM_ALLOW_CWD", "1")

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    cwd_dir = tmp_path / "untrusted_cwd"
    cwd_dir.mkdir()
    cwd_config = cwd_dir / "schemaslim.json"
    cwd_config.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    monkeypatch.chdir(cwd_dir)

    with caplog.at_level(logging.WARNING):
        resolved = find_config_file()

    assert resolved == cwd_config.resolve()
    assert any(
        "untrusted current working directory" in record.message
        for record in caplog.records
    )


# ── 8. Batch Deletion Parameter Chunking (SCHEMASLIM-SEC-05) ─────────────────


def test_remove_server_tools_large_volume_chunking(tmp_path: Path):
    """Verify that removing a large volume of tools (>1000) does not exceed SQLite variable limits."""
    db_path = tmp_path / "large_delete_test.db"
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [[0.01] * 384 for _ in range(1200)]

    # Generate 1,200 tools for a single server
    large_tools = [
        IndexedTool.create(
            server_name="huge_server",
            tool_name=f"tool_{i}",
            description=f"Automated tool index #{i}",
            parameters={"type": "object", "properties": {"idx": {"type": "integer"}}},
        )
        for i in range(1200)
    ]

    with VectorStore(db_path=db_path, embedder=mock_embedder) as store:
        upserted = store.upsert_tools(large_tools)
        assert upserted == 1200
        assert store.get_total_tools_count() == 1200

        # Remove all 1,200 tools (exceeds default 999 SQL variables if unchunked)
        removed = store.remove_server_tools("huge_server")
        assert removed == 1200
        assert store.get_total_tools_count() == 0
