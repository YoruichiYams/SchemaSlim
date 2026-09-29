"""Pydantic configuration models for SchemaSlim and external MCP servers."""

from pathlib import Path
import re
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class StdioServerConfig(BaseModel):
    """Configuration for an MCP server executed via Standard I/O (stdio)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    transport: Literal["stdio"] = "stdio"
    command: str = Field(..., description="Executable or command to run")
    args: List[str] = Field(
        default_factory=list, description="Command line arguments"
    )
    env: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the process"
    )
    cwd: Optional[str] = Field(
        default=None, description="Working directory for the process"
    )
    enabled: bool = Field(
        default=True, description="Whether this server is active"
    )
    description: Optional[str] = Field(
        default=None, description="Human-readable server description"
    )
    keep_alive: bool = Field(
        default=False,
        description="Whether to exempt this server from idle process reaping (for stateful connections)",
    )

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Server command must not be empty.")
        return trimmed


class SseServerConfig(BaseModel):
    """Configuration for an MCP server communicating via Server-Sent Events (SSE) / HTTP."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    transport: Literal["sse"] = "sse"
    url: HttpUrl = Field(..., description="SSE endpoint URL")
    headers: Dict[str, str] = Field(
        default_factory=dict, description="HTTP headers for SSE connection"
    )
    enabled: bool = Field(
        default=True, description="Whether this server is active"
    )
    description: Optional[str] = Field(
        default=None, description="Human-readable server description"
    )
    keep_alive: bool = Field(
        default=False,
        description="Whether to exempt this server from idle process reaping (for stateful connections)",
    )


def _discriminate_server(v: Any) -> Any:
    """Pre-validator to infer transport if omitted (standard Claude desktop config compatibility)."""
    if isinstance(v, dict):
        if "transport" not in v:
            if "url" in v:
                v = {**v, "transport": "sse"}
            elif "command" in v:
                v = {**v, "transport": "stdio"}
    return v


ServerConfig = Annotated[
    Union[StdioServerConfig, SseServerConfig],
    Field(discriminator="transport"),
]


class SchemaSlimSettings(BaseModel):
    """Internal settings for SchemaSlim proxy, semantic indexing, and search."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    db_path: str = Field(
        default="~/.schemaslim/index.db",
        description="Path to sqlite-vec database storing tool schemas and embeddings",
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="FastEmbed model identifier for semantic tool search",
    )
    similarity_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold to match tools",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Default number of tools to return in schemaslim_search",
    )
    max_search_results: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Hard upper limit of returned search candidates",
    )
    log_level: str = Field(
        default="INFO",
        description="Application logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        val = v.upper()
        if val not in allowed:
            raise ValueError(f"Invalid log_level '{v}'. Allowed: {sorted(allowed)}")
        return val

    @property
    def resolved_db_path(self) -> Path:
        """Expand user directory (~) and resolve absolute path."""
        return Path(self.db_path).expanduser().resolve()


DEFAULT_DESTRUCTIVE_PATTERNS: List[str] = [
    "delete",
    "drop",
    "destroy",
    "remove",
    "truncate",
    "write",
    "execute",
    "shell",
    "bash",
    "kill",
    "eval",
]


class SecurityPolicy(BaseModel):
    """Execution safety policy governing destructive and mutating tool calls."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    mode: Literal["permissive", "ask", "readonly"] = Field(
        default="ask",
        description="Enforcement mode: 'permissive' (unrestricted), 'ask' (confirmation required), or 'readonly' (blocked)",
    )
    destructive_patterns: List[str] = Field(
        default_factory=lambda: list(DEFAULT_DESTRUCTIVE_PATTERNS),
        description="Regex patterns matching mutating or destructive actions",
    )
    allowed_tools: List[str] = Field(
        default_factory=list,
        description="List of full tool names (server__tool) explicitly exempted from restrictions",
    )
    blocked_tools: List[str] = Field(
        default_factory=list,
        description="List of full tool names permanently denied execution",
    )


class Config(BaseModel):
    """Root configuration containing MCP server definitions, settings, and security policy."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    mcpServers: Dict[str, ServerConfig] = Field(
        default_factory=dict,
        description="Map of server identifiers to their MCP connection configs",
    )
    settings: SchemaSlimSettings = Field(
        default_factory=SchemaSlimSettings,
        description="SchemaSlim engine settings",
    )
    security: SecurityPolicy = Field(
        default_factory=SecurityPolicy,
        description="Execution safety policy for tool calls",
    )
    idle_timeout: Optional[float] = Field(
        default=None,
        description="Optional idle timeout in seconds before reaping inactive child processes. None or <= 0 disables reaping.",
    )

    @model_validator(mode="before")
    @classmethod
    def pre_process_servers(cls, data: Any) -> Any:
        """Normalize server dictionary values by inferring transport when omitted."""
        if isinstance(data, dict):
            servers = data.get("mcpServers")
            if isinstance(servers, dict):
                normalized_servers = {}
                for name, s_cfg in servers.items():
                    normalized_servers[name] = _discriminate_server(s_cfg)
                data = {**data, "mcpServers": normalized_servers}
        return data

    @field_validator("mcpServers")
    @classmethod
    def validate_server_names(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate server identifiers to prevent namespace collisions and Confused Deputy attacks."""
        server_name_regex = re.compile(r"^[a-zA-Z0-9_-]+$")
        for server_name in v.keys():
            if "__" in server_name:
                raise ValueError(
                    f"Invalid server identifier '{server_name}': cannot contain '__' "
                    "to prevent namespace collision attacks."
                )
            if not server_name_regex.match(server_name):
                raise ValueError(
                    f"Invalid server identifier '{server_name}': must contain only "
                    "alphanumeric characters, single underscores, and hyphens (^[a-zA-Z0-9_-]+$)."
                )
        return v

    @property
    def active_servers(self) -> Dict[str, ServerConfig]:
        """Return only servers where enabled is True."""
        return {k: v for k, v in self.mcpServers.items() if v.enabled}
