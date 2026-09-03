"""Schema harvester for querying external MCP servers and extracting tool definitions."""

import asyncio
from typing import Dict, List, Optional, Tuple
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from schemaslim.config.models import (
    Config,
    ServerConfig,
    SseServerConfig,
    StdioServerConfig,
)
from schemaslim.storage.models import IndexedTool
from schemaslim.utils.logger import get_logger

logger = get_logger("harvester")


class SchemaHarvester:
    """Asynchronously connects to external MCP servers and harvests their tool schemas."""

    def __init__(self, default_timeout: float = 10.0) -> None:
        """Initialize harvester.

        Args:
            default_timeout: Timeout in seconds for connecting and fetching tools per server.
        """
        self.default_timeout = default_timeout

    async def harvest_server(
        self,
        server_name: str,
        config: ServerConfig,
        timeout: Optional[float] = None,
    ) -> List[IndexedTool]:
        """Harvest tools from a single MCP server.

        Args:
            server_name: Logical name assigned to this server.
            config: Server configuration (StdioServerConfig or SseServerConfig).
            timeout: Optional override for operation timeout.

        Returns:
            List of parsed IndexedTool objects.

        Raises:
            Exception: If connection or schema retrieval fails.
        """
        effective_timeout = timeout or self.default_timeout

        if isinstance(config, StdioServerConfig):
            return await self._harvest_stdio(server_name, config, effective_timeout)
        elif isinstance(config, SseServerConfig):
            return await self._harvest_sse(server_name, config, effective_timeout)
        else:
            raise ValueError(f"Unsupported server config type: {type(config)}")

    async def _harvest_stdio(
        self,
        server_name: str,
        config: StdioServerConfig,
        timeout: float,
    ) -> List[IndexedTool]:
        """Harvest tools via Standard I/O subprocess transport."""
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

        async def _run_stdio_session() -> List[IndexedTool]:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    response = await session.list_tools()
                    tools = [
                        IndexedTool.from_mcp_tool(server_name, t)
                        for t in response.tools
                    ]
                    logger.info(
                        "Harvested %d tools from stdio server '%s'.",
                        len(tools),
                        server_name,
                    )
                    return tools

        return await asyncio.wait_for(_run_stdio_session(), timeout=timeout)

    async def _harvest_sse(
        self,
        server_name: str,
        config: SseServerConfig,
        timeout: float,
    ) -> List[IndexedTool]:
        """Harvest tools via SSE/HTTP network transport."""
        url_str = str(config.url)
        headers = dict(config.headers) if config.headers else None

        logger.debug("Connecting to SSE server '%s' at %s...", server_name, url_str)

        async def _run_sse_session() -> List[IndexedTool]:
            async with sse_client(
                url=url_str,
                headers=headers,
                timeout=min(5.0, timeout),
            ) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    response = await session.list_tools()
                    tools = [
                        IndexedTool.from_mcp_tool(server_name, t)
                        for t in response.tools
                    ]
                    logger.info(
                        "Harvested %d tools from SSE server '%s'.",
                        len(tools),
                        server_name,
                    )
                    return tools

        return await asyncio.wait_for(_run_sse_session(), timeout=timeout)

    async def harvest_all(
        self,
        config: Config,
        timeout_per_server: Optional[float] = None,
    ) -> Tuple[List[IndexedTool], Dict[str, str]]:
        """Harvest tools across all active servers in parallel with failure isolation.

        Args:
            config: SchemaSlim root configuration.
            timeout_per_server: Per-server timeout in seconds.

        Returns:
            Tuple of (all_harvested_tools, failed_servers_dict) where failed_servers_dict
            maps failed server names to their error descriptions.
        """
        active = config.active_servers
        if not active:
            logger.warning("No active servers found in configuration.")
            return [], {}

        timeout = timeout_per_server or self.default_timeout
        server_names = list(active.keys())
        tasks = [
            self.harvest_server(name, active[name], timeout=timeout)
            for name in server_names
        ]

        logger.info(
            "Starting parallel harvest for %d active servers...", len(server_names)
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_tools: List[IndexedTool] = []
        failures: Dict[str, str] = {}

        for name, outcome in zip(server_names, results):
            if isinstance(outcome, BaseException):
                err_msg = f"{type(outcome).__name__}: {outcome}"
                failures[name] = err_msg
                logger.error("Failed to harvest server '%s': %s", name, err_msg)
            else:
                all_tools.extend(outcome)

        logger.info(
            "Harvesting complete: %d total tools collected, %d servers failed.",
            len(all_tools),
            len(failures),
        )
        return all_tools, failures
