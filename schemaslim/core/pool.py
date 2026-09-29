"""Persistent session pool for managing long-lived connections to child MCP servers."""

import asyncio
import sys
import time
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
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
        idle_timeout: Optional[float] = None,
    ) -> None:
        self.connect_timeout = connect_timeout
        self.call_timeout = call_timeout
        self.idle_timeout = idle_timeout
        self._sessions: Dict[str, ClientSession] = {}
        self._session_stacks: Dict[str, AsyncExitStack] = {}
        self._last_accessed: Dict[str, float] = {}
        self._in_flight: Dict[str, int] = {}
        self._exit_stack: Optional[AsyncExitStack] = None
        self._reaper_task: Optional[asyncio.Task] = None
        self._config: Optional[Config] = None
        self._initialized: bool = False

    @property
    def server_names(self) -> list[str]:
        """Return list of connected server names."""
        return list(self._sessions.keys())

    @property
    def is_initialized(self) -> bool:
        """Whether the pool has been initialized."""
        return self._initialized

    def get_last_accessed(self, server_name: str) -> Optional[float]:
        """Return the monotonic timestamp when server session was last accessed."""
        return self._last_accessed.get(server_name)

    async def initialize(self, config: Config) -> None:
        """Launch persistent child processes and sessions for all active servers.

        Args:
            config: SchemaSlim root configuration with mcpServers definitions.
        """
        if self._initialized:
            logger.warning("MCPSessionPool is already initialized, skipping.")
            return

        self._config = config
        if self.idle_timeout is None and config.idle_timeout is not None:
            self.idle_timeout = config.idle_timeout

        self._exit_stack = AsyncExitStack()
        active = config.active_servers

        if not active:
            logger.warning("No active servers in configuration; pool is empty.")
            self._initialized = True
            return

        logger.info("Initializing session pool for %d active servers...", len(active))

        now = time.monotonic()
        for server_name, server_config in active.items():
            try:
                session = await self._connect_server(server_name, server_config)
                self._sessions[server_name] = session
                if server_name not in self._session_stacks:
                    self._session_stacks[server_name] = AsyncExitStack()
                self._last_accessed[server_name] = now
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

        if self.idle_timeout is not None and self.idle_timeout > 0:
            self._reaper_task = asyncio.create_task(self._idle_reaper_loop())
            logger.info("Idle process reaper started with timeout=%.1fs", self.idle_timeout)

    async def _connect_server(
        self, server_name: str, config: ServerConfig
    ) -> ClientSession:
        """Establish a persistent connection to a single MCP server.

        Each session maintains its own AsyncExitStack so individual idle
        sessions can be cleanly terminated and reaped without affecting other
        active servers.
        """
        if server_name in self._session_stacks:
            await self._close_session(server_name)

        stack = AsyncExitStack()
        try:
            session = await asyncio.wait_for(
                self._do_connect_server(server_name, config, stack),
                timeout=self.connect_timeout,
            )
            self._session_stacks[server_name] = stack
            return session
        except asyncio.TimeoutError as exc:
            await stack.aclose()
            raise SessionCallError(
                f"Connection to server '{server_name}' timed out after {self.connect_timeout}s"
            ) from exc
        except Exception:
            await stack.aclose()
            raise

    async def _do_connect_server(
        self, server_name: str, config: ServerConfig, stack: Optional[AsyncExitStack] = None
    ) -> ClientSession:
        """Establish transport and initialize session context."""
        active_stack = stack or self._exit_stack
        assert active_stack is not None

        if isinstance(config, StdioServerConfig):
            return await self._connect_stdio(server_name, config, active_stack)
        elif isinstance(config, SseServerConfig):
            return await self._connect_sse(server_name, config, active_stack)
        else:
            raise ValueError(f"Unsupported server config type: {type(config)}")

    async def _connect_stdio(
        self, server_name: str, config: StdioServerConfig, stack: Optional[AsyncExitStack] = None
    ) -> ClientSession:
        """Connect to a stdio-based child MCP server."""
        active_stack = stack or self._exit_stack
        assert active_stack is not None

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

        read_stream, write_stream = await active_stack.enter_async_context(
            stdio_client(server_params)
        )
        session = await active_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        return session

    async def _connect_sse(
        self, server_name: str, config: SseServerConfig, stack: Optional[AsyncExitStack] = None
    ) -> ClientSession:
        """Connect to an SSE-based child MCP server with URL fallback and error reporting."""
        active_stack = stack or self._exit_stack
        assert active_stack is not None

        url_str = str(config.url)
        headers = dict(config.headers) if config.headers else None

        # Build candidate URLs (auto-probe /sse suffix if base URL has no path)
        candidate_urls = [url_str]
        parsed = urlparse(url_str)
        if (not parsed.path or parsed.path == "/") and not url_str.rstrip("/").endswith("/sse"):
            candidate_urls.append(url_str.rstrip("/") + "/sse")

        last_err: Optional[Exception] = None
        for current_url in candidate_urls:
            logger.debug("Connecting to SSE server '%s' at %s...", server_name, current_url)

            sub_stack = AsyncExitStack()
            try:
                read_stream, write_stream = await sub_stack.enter_async_context(
                    sse_client(url=current_url, headers=headers)
                )
                session = await sub_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                # Keep sub_stack alive through session pool lifecycle
                await active_stack.enter_async_context(sub_stack)
                logger.info("Successfully connected to SSE server '%s' at %s.", server_name, current_url)
                return session
            except (httpx.HTTPError, TimeoutError, asyncio.TimeoutError, Exception) as exc:
                await sub_stack.aclose()
                last_err = exc
                if current_url != candidate_urls[-1]:
                    logger.debug(
                        "SSE connection to '%s' failed at %s (%s). Trying fallback %s...",
                        server_name,
                        current_url,
                        exc,
                        candidate_urls[-1],
                    )
                    continue

                err_detail = f"SSE server '{server_name}' at {current_url} unreachable: {type(exc).__name__}: {exc}"
                sys.stderr.write(f"[schemaslim] {err_detail}\n")
                sys.stderr.flush()
                logger.error(err_detail)
                raise SessionCallError(err_detail) from exc

        raise last_err or SessionCallError(f"Failed to connect to SSE server '{server_name}'")

    async def _close_session(self, server_name: str) -> None:
        """Gracefully terminate a child session, closing its streams and removing handles."""
        self._sessions.pop(server_name, None)
        self._last_accessed.pop(server_name, None)
        stack = self._session_stacks.pop(server_name, None)
        if stack is not None:
            try:
                await stack.aclose()
            except Exception as exc:
                logger.warning("Error closing session context for '%s': %s: %s", server_name, type(exc).__name__, exc)
        logger.debug("Session closed for server '%s'.", server_name)

    async def _idle_reaper_loop(self) -> None:
        """Background task that periodically reaps child sessions exceeding idle_timeout."""
        assert self.idle_timeout is not None and self.idle_timeout > 0
        interval = min(max(self.idle_timeout / 2.0, 0.05), 30.0)

        while True:
            try:
                await asyncio.sleep(interval)
                now = time.monotonic()
                to_reap: List[str] = []
                for server_name, last in list(self._last_accessed.items()):
                    if self._in_flight.get(server_name, 0) > 0:
                        continue  # In-flight tool invocation, do not reap
                    # Check keep_alive exemption for stateful connections
                    if self._config is not None:
                        srv_cfg = self._config.active_servers.get(server_name)
                        if srv_cfg and getattr(srv_cfg, "keep_alive", False):
                            continue  # Stateful server explicitly exempted from reaping
                    if (now - last) >= self.idle_timeout:
                        to_reap.append(server_name)

                for server_name in to_reap:
                    logger.info(
                        "Reaping idle session for server '%s' (idle %.1fs >= timeout %.1fs).",
                        server_name,
                        now - self._last_accessed.get(server_name, now),
                        self.idle_timeout,
                    )
                    await self._close_session(server_name)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Error in idle reaper loop: %s: %s", type(exc).__name__, exc)

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

        # Transparent on-demand revival if server was reaped or not connected
        if server_name not in self._sessions and self._config is not None:
            active = self._config.active_servers
            if server_name in active:
                logger.info("On-demand reviving session for server '%s'...", server_name)
                try:
                    session = await self._connect_server(server_name, active[server_name])
                    self._sessions[server_name] = session
                    if server_name not in self._session_stacks:
                        self._session_stacks[server_name] = AsyncExitStack()
                    self._last_accessed[server_name] = time.monotonic()
                except Exception as exc:
                    raise SessionCallError(
                        f"Failed to revive session for server '{server_name}': "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc

        session = self._sessions.get(server_name)
        if session is None:
            available = ", ".join(self._sessions.keys()) or "(none)"
            raise SessionNotFoundError(
                f"No active session for server '{server_name}'. "
                f"Available servers: {available}"
            )

        self._in_flight[server_name] = self._in_flight.get(server_name, 0) + 1
        self._last_accessed[server_name] = time.monotonic()

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
        finally:
            self._in_flight[server_name] = max(0, self._in_flight.get(server_name, 1) - 1)
            self._last_accessed[server_name] = time.monotonic()

    async def shutdown(self) -> None:
        """Gracefully close all child sessions and transport connections."""
        logger.info("Shutting down session pool...")

        # 1. Cancel background reaper task
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except asyncio.CancelledError:
                pass
            self._reaper_task = None

        # 2. Close each server session context
        for server_name in list(self._session_stacks.keys()):
            await self._close_session(server_name)

        # 3. Clean up global exit stack if used
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception as exc:
                logger.error("Error during pool shutdown: %s: %s", type(exc).__name__, exc)
            finally:
                self._exit_stack = None

        self._sessions.clear()
        self._session_stacks.clear()
        self._last_accessed.clear()
        self._in_flight.clear()
        self._config = None
        self._initialized = False
        logger.info("Session pool shut down successfully.")
