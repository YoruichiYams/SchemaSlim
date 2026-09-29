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
from schemaslim.config.models import (
    DEFAULT_DESTRUCTIVE_PATTERNS,
    Config,
    SecurityPolicy,
    StdioServerConfig,
)
from schemaslim.core.harvester import SchemaHarvester
from schemaslim.core.pool import MCPSessionPool, SessionCallError
from schemaslim.core.security import is_destructive
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


# ── 9. Destructive Call Boundary & Safety Policy (SCHEMASLIM-SEC-07) ─────────


def test_security_policy_config_parsing():
    """Verify parsing and validation of SecurityPolicy within Config."""
    # 1. Default policy values
    cfg_default = Config()
    assert cfg_default.security.mode == "ask"
    assert cfg_default.security.allowed_tools == []
    assert cfg_default.security.blocked_tools == []
    assert set(cfg_default.security.destructive_patterns) == set(DEFAULT_DESTRUCTIVE_PATTERNS)

    # 2. Custom policy values
    custom_data = {
        "security": {
            "mode": "readonly",
            "destructive_patterns": ["purge", "destroy"],
            "allowed_tools": ["fs__delete_temp"],
            "blocked_tools": ["admin__eval"],
        }
    }
    cfg_custom = Config.model_validate(custom_data)
    assert cfg_custom.security.mode == "readonly"
    assert cfg_custom.security.destructive_patterns == ["purge", "destroy"]
    assert cfg_custom.security.allowed_tools == ["fs__delete_temp"]
    assert cfg_custom.security.blocked_tools == ["admin__eval"]

    # 3. Invalid mode raises validation error
    with pytest.raises(ValidationError):
        Config.model_validate({"security": {"mode": "invalid_mode"}})


def test_is_destructive_pattern_detection():
    """Verify deterministic classification of destructive tool names and descriptions."""
    policy = SecurityPolicy()

    # Tool name pattern detection
    assert is_destructive("fs__delete_file", policy=policy) is True
    assert is_destructive("db__drop_table", policy=policy) is True
    assert is_destructive("bash__execute", policy=policy) is True
    assert is_destructive("terminal__shell", policy=policy) is True
    assert is_destructive("process__kill", policy=policy) is True
    assert is_destructive("calc__eval", policy=policy) is True
    assert is_destructive("fs__remove_dir", policy=policy) is True
    assert is_destructive("data__truncate_table", policy=policy) is True
    assert is_destructive("fs__write_file", policy=policy) is True

    # Safe tool names
    assert is_destructive("fs__read_file", policy=policy) is False
    assert is_destructive("git__status", policy=policy) is False
    assert is_destructive("db__list_tables", policy=policy) is False
    assert is_destructive("api__get_user", policy=policy) is False

    # Detection via description
    assert is_destructive("custom_tool", description="Permanently delete user data", policy=policy) is True
    assert is_destructive("custom_query", description="Drop database tables if corrupt", policy=policy) is True
    assert is_destructive("fetcher", description="Fetch HTTP contents safely", policy=policy) is False


def test_is_destructive_allowed_and_blocked_tools():
    """Verify that allowed_tools overrides patterns and blocked_tools forces True."""
    # Whitelist exemption
    policy_allowed = SecurityPolicy(allowed_tools=["fs__delete_file"])
    assert is_destructive("fs__delete_file", policy=policy_allowed) is False

    # Blacklist forced block
    policy_blocked = SecurityPolicy(blocked_tools=["fs__read_file"])
    assert is_destructive("fs__read_file", policy=policy_blocked) is True


@pytest.mark.asyncio
async def test_security_guard_blocked_tool_execution():
    """Verify that tools listed in blocked_tools are unconditionally rejected."""
    mock_pool = MagicMock()
    mock_pool.call_tool = AsyncMock()

    policy = SecurityPolicy(blocked_tools=["danger__run"])
    server = VirtualMCPServer(pool=mock_pool, security_policy=policy)

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "danger__run", "arguments": {}},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error is True
    assert "Tool 'danger__run' is blocked by security policy" in result.content[0].text
    mock_pool.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_security_guard_readonly_mode():
    """Verify that destructive tools are blocked when security mode is 'readonly'."""
    mock_pool = MagicMock()
    mock_pool.call_tool = AsyncMock()

    policy = SecurityPolicy(mode="readonly")
    server = VirtualMCPServer(pool=mock_pool, security_policy=policy)

    # 1. Destructive tool rejected
    destr_params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "fs__delete_file", "arguments": {"path": "/foo"}},
    )
    result = await server._handle_call_tool(None, destr_params)
    assert result.is_error is True
    assert "Execution denied: tool is destructive and security mode is 'readonly'" in result.content[0].text
    mock_pool.call_tool.assert_not_called()

    # 2. Non-destructive tool permitted
    mock_pool.call_tool.return_value = types.CallToolResult(
        content=[types.TextContent(type="text", text="file contents")],
        is_error=False,
    )
    safe_params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "fs__read_file", "arguments": {"path": "/foo"}},
    )
    safe_result = await server._handle_call_tool(None, safe_params)
    assert safe_result.is_error is False
    mock_pool.call_tool.assert_awaited_once_with("fs__read_file", {"path": "/foo"})


@pytest.mark.asyncio
async def test_security_guard_ask_mode_rejection_without_confirmed():
    """Verify that ask mode challenges unconfirmed destructive calls with a security warning."""
    mock_pool = MagicMock()
    mock_pool.call_tool = AsyncMock()

    policy = SecurityPolicy(mode="ask")
    server = VirtualMCPServer(pool=mock_pool, security_policy=policy)

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "db__drop_table", "arguments": {"table": "logs"}},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error is True
    assert "Security Warning: Tool 'db__drop_table' has been flagged as destructive/mutating" in result.content[0].text
    assert "'_confirmed': true" in result.content[0].text
    mock_pool.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_security_guard_ask_mode_confirmed_execution_and_sanitization():
    """Verify that providing _confirmed: true permits execution and strips _confirmed from arguments."""
    mock_pool = MagicMock()
    mock_pool.call_tool = AsyncMock(
        return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text="table dropped")],
            is_error=False,
        )
    )

    policy = SecurityPolicy(mode="ask")
    server = VirtualMCPServer(pool=mock_pool, security_policy=policy)

    # Pass _confirmed in tool arguments
    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={
            "namespaced_name": "db__drop_table",
            "arguments": {"table": "logs", "_confirmed": True},
        },
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error is False
    assert "table dropped" in result.content[0].text
    # Verify _confirmed was stripped before forwarding to child session
    mock_pool.call_tool.assert_awaited_once_with("db__drop_table", {"table": "logs"})


@pytest.mark.asyncio
async def test_security_guard_permissive_mode_bypasses_confirmation():
    """Verify that permissive mode allows destructive tool execution without confirmation."""
    mock_pool = MagicMock()
    mock_pool.call_tool = AsyncMock(
        return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text="executed")],
            is_error=False,
        )
    )

    policy = SecurityPolicy(mode="permissive")
    server = VirtualMCPServer(pool=mock_pool, security_policy=policy)

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "bash__execute", "arguments": {"cmd": "rm -rf /tmp/test"}},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error is False
    mock_pool.call_tool.assert_awaited_once_with("bash__execute", {"cmd": "rm -rf /tmp/test"})


@pytest.mark.asyncio
async def test_schemaslim_search_injects_security_metadata(tmp_path: Path):
    """Verify that schemaslim_search injects is_destructive and security_mode into results."""
    db_path = tmp_path / "search_sec.db"
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [[0.1] * 384, [0.1] * 384]

    tools = [
        IndexedTool.create(
            server_name="fs",
            tool_name="delete_file",
            description="Delete file permanently",
            parameters={"type": "object"},
        ),
        IndexedTool.create(
            server_name="fs",
            tool_name="read_file",
            description="Read file safely",
            parameters={"type": "object"},
        ),
    ]

    with VectorStore(db_path=db_path, embedder=mock_embedder) as store:
        store.upsert_tools(tools)

    policy = SecurityPolicy(mode="ask")
    server = VirtualMCPServer(security_policy=policy)
    active_store = VectorStore(db_path=db_path, embedder=mock_embedder)
    server._store = active_store

    try:
        params = types.CallToolRequestParams(
            name="schemaslim_search",
            arguments={"query": "file", "limit": 10},
        )
        res = await server._handle_call_tool(None, params)
        assert not res.is_error

        payload = json.loads(res.content[0].text)
        assert payload["security_mode"] == "ask"
        assert len(payload["results"]) == 2

        results_by_name = {r["namespaced_name"]: r for r in payload["results"]}
        assert results_by_name["fs__delete_file"]["is_destructive"] is True
        assert results_by_name["fs__delete_file"]["security_mode"] == "ask"
        assert results_by_name["fs__read_file"]["is_destructive"] is False
        assert results_by_name["fs__read_file"]["security_mode"] == "ask"
    finally:
        active_store.close()


@pytest.mark.asyncio
async def test_blocked_tools_base_name_rejection_in_server():
    """Verify that specifying 'delete_file' in blocked_tools blocks 'filesystem__delete_file' even if _confirmed: true."""
    mock_pool = MagicMock()
    mock_pool.call_tool = AsyncMock()

    policy = SecurityPolicy(mode="ask", blocked_tools=["delete_file"])
    server = VirtualMCPServer(pool=mock_pool, security_policy=policy)

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={
            "namespaced_name": "filesystem__delete_file",
            "arguments": {"path": "/important.txt", "_confirmed": True},
        },
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error is True
    assert "Tool 'filesystem__delete_file' is blocked by security policy" in result.content[0].text
    mock_pool.call_tool.assert_not_called()


def test_inflected_verb_detection_in_description():
    """Verifies descriptions containing 'Deletes records', 'Dropping tables', 'Purges cache' trigger is_destructive=True."""
    policy = SecurityPolicy()

    assert is_destructive("data__sync", description="Deletes records older than 30 days", policy=policy) is True
    assert is_destructive("db__migration", description="Dropping tables and rebuilding schema", policy=policy) is True
    assert is_destructive("cache__manager", description="Purges cache entries on invalidate", policy=policy) is True
    assert is_destructive("service__task", description="Executing user tasks in isolated environment", policy=policy) is True
    assert is_destructive("data__audit", description="Read-only query of logs without mutation", policy=policy) is False


def test_server_name_namespace_does_not_trigger_false_positive():
    """Verifies delete_service__get_status is NOT marked destructive."""
    policy = SecurityPolicy()

    assert is_destructive("delete_service__get_status", description="Inspect system status and metrics", policy=policy) is False
    assert is_destructive("kill_daemon__read_health", description="Check daemon health endpoint", policy=policy) is False
    assert is_destructive("bash_runner__get_version", description="Get version info", policy=policy) is False


def test_expanded_destructive_patterns():
    """Verifies tools with exec, purge, unlink, run_command are detected as destructive."""
    policy = SecurityPolicy()

    assert is_destructive("terminal__exec", policy=policy) is True
    assert is_destructive("storage__purge", policy=policy) is True
    assert is_destructive("fs__unlink", policy=policy) is True
    assert is_destructive("runner__run_command", policy=policy) is True
    assert is_destructive("os__wipe_disk", policy=policy) is True
    assert is_destructive("git__patch_apply", policy=policy) is True
    assert is_destructive("db__modify_schema", policy=policy) is True
