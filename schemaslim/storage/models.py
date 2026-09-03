"""Data models for indexed MCP tools and semantic search results."""

import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


def compute_schema_hash(description: str, parameters: Dict[str, Any]) -> str:
    """Calculate deterministic SHA-256 hash for tool description and parameters schema."""
    canonical_payload = {
        "description": (description or "").strip(),
        "parameters": parameters or {},
    }
    serialized = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_embedding_text(
    namespaced_name: str,
    description: str,
    parameters: Dict[str, Any],
) -> str:
    """Generate synthetic text representation optimized for semantic embeddings."""
    param_items: List[str] = []
    if isinstance(parameters, dict):
        properties = parameters.get("properties", {})
        if isinstance(properties, dict):
            for param_name, param_spec in properties.items():
                if isinstance(param_spec, dict):
                    p_desc = param_spec.get("description", "").strip()
                    p_type = param_spec.get("type", "")
                    details = []
                    if p_type:
                        details.append(f"type={p_type}")
                    if p_desc:
                        details.append(f"desc={p_desc}")
                    detail_str = f" ({', '.join(details)})" if details else ""
                    param_items.append(f"{param_name}{detail_str}")
                else:
                    param_items.append(str(param_name))

    params_line = ", ".join(param_items) if param_items else "none"
    clean_desc = (description or "No description provided.").strip()

    return f"tool: {namespaced_name}\ndescription: {clean_desc}\nparameters: {params_line}"


class IndexedTool(BaseModel):
    """Pydantic model representing an indexed MCP tool."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    server_name: str = Field(..., description="Origin MCP server name")
    tool_name: str = Field(..., description="Original tool name on server")
    namespaced_name: str = Field(
        ..., description="Unique namespaced identifier: {server_name}__{tool_name}"
    )
    description: str = Field(
        default="", description="Tool description provided by MCP server"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema of tool arguments"
    )
    schema_hash: str = Field(
        ..., description="SHA-256 hash of description and parameters"
    )
    text_for_embedding: str = Field(
        ..., description="Synthetic text used to generate vector embedding"
    )

    @classmethod
    def create(
        cls,
        server_name: str,
        tool_name: str,
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> "IndexedTool":
        """Factory constructor ensuring consistent namespacing and hashing."""
        params = parameters or {}
        desc = description or ""
        namespaced = f"{server_name}__{tool_name}"
        h = compute_schema_hash(desc, params)
        embedding_text = build_embedding_text(namespaced, desc, params)

        return cls(
            server_name=server_name,
            tool_name=tool_name,
            namespaced_name=namespaced,
            description=desc,
            parameters=params,
            schema_hash=h,
            text_for_embedding=embedding_text,
        )

    @classmethod
    def from_mcp_tool(cls, server_name: str, tool: Any) -> "IndexedTool":
        """Construct IndexedTool from an mcp.types.Tool instance or dictionary."""
        if hasattr(tool, "name"):
            name = tool.name
            desc = getattr(tool, "description", "") or ""
            input_schema = getattr(tool, "inputSchema", None) or {}
        elif isinstance(tool, dict):
            name = tool.get("name", "")
            desc = tool.get("description", "") or ""
            input_schema = tool.get("inputSchema") or tool.get("parameters") or {}
        else:
            raise ValueError(f"Unsupported tool object format: {type(tool)}")

        if not isinstance(input_schema, dict):
            input_schema = {}

        return cls.create(
            server_name=server_name,
            tool_name=name,
            description=desc,
            parameters=input_schema,
        )


class SearchResult(BaseModel):
    """Ranked search result container."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool: IndexedTool
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized relevance score")
    vector_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Cosine similarity score"
    )
    lexical_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Normalized FTS5 BM25 score"
    )
