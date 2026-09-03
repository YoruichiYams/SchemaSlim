"""Telemetry manager and token estimation engine for SchemaSlim proxy events."""

import collections
import json
import math
import threading
import time
from typing import Any, Dict, List, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field, model_validator


def estimate_tokens(content: Any) -> int:
    """Lightweight heuristic token counter without heavy dependencies.

    Uses ~4 characters per token for serialized JSON/code/text representations,
    which closely tracks standard BPE tokenizers for structured schemas.
    """
    if not content:
        return 0

    try:
        if isinstance(content, str):
            text = content
        elif hasattr(content, "model_dump_json"):
            try:
                text = content.model_dump_json()
            except RecursionError:
                return 1000
            except Exception:
                text = ""
        elif isinstance(content, (dict, list)):
            try:
                text = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
            except (RecursionError, ValueError):
                return 1000
            except Exception:
                try:
                    text = str(content)
                except RecursionError:
                    return 1000
                except Exception:
                    text = ""
        else:
            try:
                text = str(content)
            except RecursionError:
                return 1000
            except Exception:
                text = ""
    except RecursionError:
        return 1000
    except Exception:
        return 1000

    if not text:
        return 0

    # ~4 characters per token heuristic
    return max(1, math.ceil(len(text) / 4.0))


def estimate_tools_tokens(tools: Sequence[Any]) -> int:
    """Estimate total tokens required to represent a collection of tools in context.

    Converts tools (whether IndexedTool, Tool objects, or dicts) into canonical
    MCP tool definitions before computing the token footprint.
    """
    if not tools:
        return 0

    canonical_tools: List[Dict[str, Any]] = []
    for tool in tools:
        if hasattr(tool, "tool_name"):
            # IndexedTool instance
            canonical_tools.append(
                {
                    "name": tool.namespaced_name if hasattr(tool, "namespaced_name") else tool.tool_name,
                    "description": tool.description or "",
                    "inputSchema": tool.parameters if hasattr(tool, "parameters") else {},
                }
            )
        elif hasattr(tool, "name"):
            # mcp.types.Tool instance
            input_schema = getattr(tool, "inputSchema", None)
            if input_schema is None:
                input_schema = getattr(tool, "input_schema", {})
            canonical_tools.append(
                {
                    "name": tool.name,
                    "description": getattr(tool, "description", "") or "",
                    "inputSchema": input_schema or {},
                }
            )
        elif isinstance(tool, dict):
            canonical_tools.append(
                {
                    "name": tool.get("name", tool.get("namespaced_name", "")),
                    "description": tool.get("description", ""),
                    "inputSchema": tool.get("inputSchema", tool.get("parameters", {})),
                }
            )
        else:
            canonical_tools.append({"raw": str(tool)})

    return estimate_tokens(canonical_tools)


class ProxyEvent(BaseModel):
    """Model representing an individual proxied MCP event (search or tool call)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of the event")
    event_type: Literal["search", "call"] = Field(..., description="Event type: 'search' or 'call'")
    tool_name: str = Field(..., description="Target tool identifier or search query summary")
    latency_ms: float = Field(..., ge=0.0, description="Execution latency in milliseconds")
    tokens_baseline: int = Field(..., ge=0, description="Baseline tokens for full tool catalog")
    tokens_actual: int = Field(..., ge=0, description="Actual tokens used by SchemaSlim proxy")
    tokens_saved: int = Field(default=0, ge=0, description="Tokens saved (baseline - actual, clamped to 0)")
    status: Literal["success", "error"] = Field(default="success", description="Outcome status: success or error")

    @model_validator(mode="before")
    @classmethod
    def calculate_tokens_saved(cls, data: Any) -> Any:
        """Ensure tokens_saved is accurately calculated if not explicitly specified."""
        if isinstance(data, dict):
            baseline = int(data.get("tokens_baseline", 0))
            actual = int(data.get("tokens_actual", 0))
            if "tokens_saved" not in data or data["tokens_saved"] is None:
                data["tokens_saved"] = max(0, baseline - actual)
        return data


class TelemetrySummary(BaseModel):
    """Aggregated session telemetry summary."""

    total_requests: int = 0
    search_requests: int = 0
    call_requests: int = 0
    error_requests: int = 0
    total_tokens_baseline: int = 0
    total_tokens_actual: int = 0
    total_tokens_saved: int = 0
    avg_compression_pct: float = 0.0
    avg_latency_ms: float = 0.0
    avg_search_latency_ms: float = 0.0
    avg_call_latency_ms: float = 0.0
    baseline_catalog_tokens: int = 0


class TelemetryTracker:
    """Thread-safe telemetry tracker maintaining a circular event buffer and aggregated metrics."""

    def __init__(self, max_events: int = 100, baseline_tokens: int = 0) -> None:
        self._lock = threading.Lock()
        self.max_events = max_events
        self.baseline_tokens = baseline_tokens
        self._events: collections.deque[ProxyEvent] = collections.deque(maxlen=max_events)

        # Aggregate counters
        self._total_requests: int = 0
        self._search_requests: int = 0
        self._call_requests: int = 0
        self._error_requests: int = 0
        self._total_baseline_tokens: int = 0
        self._total_actual_tokens: int = 0
        self._total_tokens_saved: int = 0
        self._total_latency_ms: float = 0.0
        self._total_search_latency_ms: float = 0.0
        self._total_call_latency_ms: float = 0.0

    def set_baseline_tokens(self, tokens: int) -> None:
        """Update the cached baseline catalog token count."""
        with self._lock:
            self.baseline_tokens = max(0, tokens)

    def record_event(self, event: ProxyEvent) -> None:
        """Record an event, update circular buffer, and accumulate aggregated metrics."""
        with self._lock:
            self._events.append(event)
            self._total_requests += 1

            if event.status == "error":
                self._error_requests += 1

            if event.event_type == "search":
                self._search_requests += 1
                self._total_search_latency_ms += event.latency_ms
            elif event.event_type == "call":
                self._call_requests += 1
                self._total_call_latency_ms += event.latency_ms

            self._total_latency_ms += event.latency_ms
            self._total_baseline_tokens += event.tokens_baseline
            self._total_actual_tokens += event.tokens_actual
            self._total_tokens_saved += event.tokens_saved

    def get_recent_events(self, limit: Optional[int] = None) -> List[ProxyEvent]:
        """Return a snapshot list of recent events (newest first)."""
        with self._lock:
            items = list(self._events)
            items.reverse()
            if limit is not None and limit > 0:
                return items[:limit]
            return items

    def get_summary(self) -> TelemetrySummary:
        """Compute and return aggregated telemetry summary."""
        with self._lock:
            total = self._total_requests
            avg_latency = (self._total_latency_ms / total) if total > 0 else 0.0
            avg_search_lat = (
                (self._total_search_latency_ms / self._search_requests)
                if self._search_requests > 0
                else 0.0
            )
            avg_call_lat = (
                (self._total_call_latency_ms / self._call_requests)
                if self._call_requests > 0
                else 0.0
            )

            if self._total_baseline_tokens > 0:
                compression_pct = (
                    self._total_tokens_saved / self._total_baseline_tokens
                ) * 100.0
            else:
                compression_pct = 0.0

            return TelemetrySummary(
                total_requests=self._total_requests,
                search_requests=self._search_requests,
                call_requests=self._call_requests,
                error_requests=self._error_requests,
                total_tokens_baseline=self._total_baseline_tokens,
                total_tokens_actual=self._total_actual_tokens,
                total_tokens_saved=self._total_tokens_saved,
                avg_compression_pct=round(compression_pct, 1),
                avg_latency_ms=round(avg_latency, 2),
                avg_search_latency_ms=round(avg_search_lat, 2),
                avg_call_latency_ms=round(avg_call_lat, 2),
                baseline_catalog_tokens=self.baseline_tokens,
            )

    def reset(self) -> None:
        """Reset all tracked metrics and clear the circular buffer."""
        with self._lock:
            self._events.clear()
            self._total_requests = 0
            self._search_requests = 0
            self._call_requests = 0
            self._error_requests = 0
            self._total_baseline_tokens = 0
            self._total_actual_tokens = 0
            self._total_tokens_saved = 0
            self._total_latency_ms = 0.0
            self._total_search_latency_ms = 0.0
            self._total_call_latency_ms = 0.0


# Module-level singleton
_GLOBAL_TRACKER: Optional[TelemetryTracker] = None
_GLOBAL_LOCK = threading.Lock()


def get_tracker() -> TelemetryTracker:
    """Get or create the global TelemetryTracker instance."""
    global _GLOBAL_TRACKER
    with _GLOBAL_LOCK:
        if _GLOBAL_TRACKER is None:
            _GLOBAL_TRACKER = TelemetryTracker()
        return _GLOBAL_TRACKER


def reset_tracker() -> None:
    """Reset the global TelemetryTracker instance."""
    global _GLOBAL_TRACKER
    with _GLOBAL_LOCK:
        if _GLOBAL_TRACKER is not None:
            _GLOBAL_TRACKER.reset()
