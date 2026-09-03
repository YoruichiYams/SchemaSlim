"""Persistent session pool for managing long-lived connections to child MCP servers."""

import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from schemaslim.config.models import (
    Config,
    ServerConfig,
    SseServerConfig,
    StdioServerConfig,
)
from schemaslim.utils.logger import get_logger

logger = get_logger("pool")


class SessionNotFoundError(Exception):
    """Raised when a requested server session does not exist in the pool."""


class SessionCallError(Exception):
    """Raised when a tool call to a child session fails."""


class MCPSessionPool:
    """Manages persistent connections to child MCP servers.

    Uses AsyncExitStack to own all transport and session context managers,
    enabling deterministic cleanup via a single shutdown() call.
    """

    def __init__(
        self,
        connect_timeout: float = 15.0,
        call_timeout: float = 60.0,
    ) -> None:
        self.connect_timeout = connect_timeout
        self.call_timeout = call_timeout
        self._sessions: Dict[str, ClientSession] = {}
        self._exit_stack: Optional[AsyncExitStack] = None
        self._initialized: bool = False

    @property
    def server_names(self) -> list[str]:
        """Return list of connected server names."""
        return list(self._sessions.keys())

    @property
    def is_initialized(self) -> bool:
        """Whether the pool has been initialized."""
        return self._initialized

    async def initialize(self, config: Config) -> None:
        """Launch persistent child processes and sessions for all active servers.

        Args:
            config: SchemaSlim root configuration with mcpServers definitions.
        """
        if self._initialized:
            logger.warning("MCPSessionPool is already initialized, skipping.")
            return

        self._exit_stack = AsyncExitStack()
        active = config.active_servers

        if not active:
            logger.warning("No active servers in configuration; pool is empty.")
            self._initialized = True
            return

        logger.info("Initializing session pool for %d active servers...", len(active))

        for server_name, server_config in active.items():
            try:
                session = await self._connect_server(server_name, server_config)
                self._sessions[server_name] = session
                logger.info("Session established for server '%s'.", server_name)
            except Exception as exc:
                logger.error(
                    "Failed to connect to server '%s': %s: %s",
                    server_name,
                    type(exc).__name__,
                    exc,
                )

        self._initialized = True
        logger.info(
            "Session pool initialized: %d/%d servers connected.",
            len(self._sessions),
            len(active),
        )

    async def _connect_server(
        self, server_name: str, config: ServerConfig
    ) -> ClientSession:
        """Establish a persistent connection to a single MCP server.

        The transport and session context managers are entered via the
        shared AsyncExitStack so they remain alive until shutdown().
        """
        try:
            return await asyncio.wait_for(
                self._do_connect_server(server_name, config),
                timeout=self.connect_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise SessionCallError(
                f"Connection to server '{server_name}' timed out after {self.connect_timeout}s"
            ) from exc

    async def _do_connect_server(
        self, server_name: str, config: ServerConfig
    ) -> ClientSession:
        """Establish transport and initialize session context."""
        assert self._exit_stack is not None

        if isinstance(config, StdioServerConfig):
            return await self._connect_stdio(server_name, config)
        elif isinstance(config, SseServerConfig):
            return await self._connect_sse(server_name, config)
        else:
            raise ValueError(f"Unsupported server config type: {type(config)}")

    async def _connect_stdio(
        self, server_name: str, config: StdioServerConfig
    ) -> ClientSession:
        """Connect to a stdio-based child MCP server."""
        assert self._exit_stack is not None

        # Pass configured environment variables if set, otherwise let MCP SDK
        # use its safe default environment filter (prevents host secret leakage).
        env = dict(config.env) if config.env else None

        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=env,
            cwd=config.cwd,
        )

        logger.debug(
            "Connecting to stdio server '%s' (%s %s)...",
            server_name,
            config.command,
            " ".join(config.args),
        )

        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        return session

    async def _connect_sse(
        self, server_name: str, config: SseServerConfig
    ) -> ClientSession:
        """Connect to an SSE-based child MCP server."""
        assert self._exit_stack is not None

        url_str = str(config.url)
        headers = dict(config.headers) if config.headers else None

        logger.debug("Connecting to SSE server '%s' at %s...", server_name, url_str)

        read_stream, write_stream = await self._exit_stack.enter_async_context(
            sse_client(url=url_str, headers=headers)
        )
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        return session

    async def call_tool(
        self, namespaced_name: str, arguments: Dict[str, Any]
    ) -> CallToolResult:
        """Execute a tool call on the appropriate child server session.

        Args:
            namespaced_name: Tool identifier in format '{server_name}__{tool_name}'.
            arguments: Tool arguments dictionary.

        Returns:
            Raw CallToolResult from the child server.

        Raises:
            SessionNotFoundError: If the server is not in the pool.
            SessionCallError: If the tool invocation fails.
        """
        if not self._initialized:
            raise RuntimeError("MCPSessionPool has not been initialized.")

        parts = namespaced_name.split("__", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(
                f"Invalid namespaced_name format: '{namespaced_name}'. "
                "Expected '{server_name}__{tool_name}'."
            )

        server_name, tool_name = parts

        session = self._sessions.get(server_name)
        if session is None:
            available = ", ".join(self._sessions.keys()) or "(none)"
            raise SessionNotFoundError(
                f"No active session for server '{server_name}'. "
                f"Available servers: {available}"
            )

        try:
            logger.debug(
                "Calling tool '%s' on server '%s' with args: %s",
                tool_name,
                server_name,
                arguments,
            )
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=self.call_timeout,
            )
            logger.debug(
                "Tool '%s' on '%s' returned successfully (is_error=%s).",
                tool_name,
                server_name,
                result.is_error,
            )
            return result
        except asyncio.TimeoutError as exc:
            raise SessionCallError(
                f"Tool execution timed out after {self.call_timeout}s"
            ) from exc
        except Exception as exc:
            raise SessionCallError(
                f"Failed to call tool '{tool_name}' on server '{server_name}': "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    async def shutdown(self) -> None:
        """Gracefully close all child sessions and transport connections."""
        if self._exit_stack is not None:
            logger.info("Shutting down session pool...")
            try:
                await self._exit_stack.aclose()
            except Exception as exc:
                logger.error("Error during pool shutdown: %s: %s", type(exc).__name__, exc)
            finally:
                self._exit_stack = None
                self._sessions.clear()
                self._initialized = False
            logger.info("Session pool shut down successfully.")
