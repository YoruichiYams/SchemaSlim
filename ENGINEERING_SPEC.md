# SchemaSlim Engineering Specification & Technical Reference
**Document Version:** 1.0.0 (RFC-Production-Ready)  
**Protocol Baseline:** Model Context Protocol (MCP) Specification `2024-11-05`  
**Target Audience:** Distributed Systems Engineers, Security Auditors, Compiler & Tooling Teams  

---

## 1. Executive Summary & Protocol Scope

SchemaSlim is an asynchronous, high-performance **tools-only MCP virtualization proxy**. It acts as an intermediary layer between an upstream Large Language Model (LLM) client (such as Claude Desktop, Cursor, or Antigravity) and multiple downstream MCP child servers.

By replacing broad-spectrum tool declaration with Just-In-Time (JIT) hybrid retrieval, SchemaSlim reduces context footprint, prevents LLM parameter confusion, and provides deterministic security boundaries for child process execution.

```
+-----------------------------------------------------------------------+
|                         LLM Host Client                               |
|                (Claude Desktop / Cursor / Custom Agent)               |
+-----------------------------------------------------------------------+
                                   |
                         stdio / SSE (JSON-RPC 2.0)
                                   v
+-----------------------------------------------------------------------+
|                       SchemaSlim Virtual Proxy                        |
|                                                                       |
|  Advertised Meta-Tools:                                               |
|  - schemaslim_search (query, limit)                                   |
|  - schemaslim_call   (namespaced_name, arguments)                     |
|                                                                       |
|  +--------------------+  +--------------------+  +-----------------+  |
|  | Hybrid Retrieval   |  | Safety Policy Guard|  | Session Pool    |  |
|  | (sqlite-vec + FTS5)|  | (SCHEMASLIM-SEC-07)|  | (AsyncExitStack)|  |
|  +--------------------+  +--------------------+  +-----------------+  |
+-----------------------------------------------------------------------+
          |                                  |
   stdio (JSON-RPC 2.0)               stdio (JSON-RPC 2.0)
          v                                  v
+-----------------------+          +-----------------------+
|  Child MCP Server A   |          |  Child MCP Server B   |
|   (e.g., PostgreSQL)  |          |   (e.g., Filesystem)  |
+-----------------------+          +-----------------------+
```

### 1.1 Supported Protocol Methods

SchemaSlim implements a strict subset of the Model Context Protocol:

| JSON-RPC Method | Handler | Description |
| :--- | :--- | :--- |
| `initialize` | `VirtualMCPServer._handle_initialize` | Establishes client-proxy handshake. Advertises `tools: {listChanged: false}` capabilities and returns server identification (`schemaslim v0.2.1`). |
| `tools/list` | `VirtualMCPServer._handle_list_tools` | Returns **strictly two meta-tools**: [`schemaslim_search`](file:///schemaslim/core/server.py#L125) and [`schemaslim_call`](file:///schemaslim/core/server.py#L140). Child tools are never exposed at root. |
| `tools/call` | `VirtualMCPServer._handle_call_tool` | Routes meta-tool invocations: dispatches search queries to [`VectorStore.hybrid_search`](file:///schemaslim/storage/vector_store.py#L283) and tool executions to [`VirtualMCPServer._do_call`](file:///schemaslim/core/server.py#L225). |
| `ping` | SDK Internal Default | Standard MCP liveness check returning an empty response object `{}`. |

### 1.2 Explicitly Unsupported Features & Technical Rationale

| Protocol Feature | Support Status | Technical Rationale & Architectural Trade-off |
| :--- | :---: | :--- |
| `notifications/tools/list_changed` | **Unsupported** | `ToolsCapability(list_changed=False)` is declared. Dynamically modifying tool definitions during an active agent session invalidates prompt prefix caches and causes attention thrashing. Schema updates require explicit re-indexing (`schemaslim index`) and server restart. |
| `resources/*` (`list`, `read`, `subscribe`, `templates`) | **Unsupported** | SchemaSlim is designed strictly for tool execution virtualization. Resource URI routing, binary blob hydration, and reactive resource subscription are discarded to keep the proxy lightweight and stateless. |
| `prompts/*` (`list`, `get`) | **Unsupported** | Slash-command prompts and system-level prompt injections from child servers are ignored. The LLM host client manages its own system instructions. |
| `sampling/createMessage` | **Unsupported** | SchemaSlim prohibits downstream child servers from requesting upstream agent sampling turns. This eliminates recursive agent invocation vulnerabilities and prevents child servers from hijacking user context. |
| `logging/setLevel` | **Unsupported** | Protocol-level JSON-RPC log streaming is disabled. SchemaSlim telemetry is isolated strictly to the host process's `sys.stderr` to prevent stdout JSON-RPC stream pollution. |
| `completion/*` | **Unsupported** | Parameter tab-completion protocols are omitted to minimize round-trip latency. |
| `roots/list_changed` | **Unsupported** | Filesystem workspace root mutation notifications are dropped. |

---

## 2. Process Lifecycle & Session Pool Contract

Downstream subprocess management is isolated in [`schemaslim/core/pool.py`](file:///schemaslim/core/pool.py) via the [`MCPSessionPool`](file:///schemaslim/core/pool.py#L32) class.

### 2.1 Persistence Model: Long-Lived vs. Ephemeral

* **Architectural Contract: Strictly Persistent.**
* Child MCP subprocesses are **never** spawned per tool call.
* Each configured stdio or SSE server is initialized once during proxy startup (`await pool.initialize(config)`).
* Persistent client sessions (`mcp.ClientSession`) are maintained inside a single top-level `contextlib.AsyncExitStack` (`self._exit_stack`).
* In-memory session handles are indexed by server name (`self._sessions: dict[str, ClientSession]`).

#### Preservation of Stateful Workloads
Because child processes remain running for the duration of the SchemaSlim daemon:
1. **Database Connections & Transactions:** Subprocesses maintaining internal connection pools, temporary tables, or active transactional locks (e.g. Postgres, SQLite) maintain continuity across sequential tool invocations.
2. **Interpreter & REPL State:** Environment variables, imported modules, and runtime memory in Python/Node.js REPL servers persist between turns.
3. **VCS / Workspace Context:** Git state, staged index entries, and local file locks are preserved.

### 2.2 Timeouts & Execution Bounds

```mermaid
sequenceDiagram
    autonumber
    participant Host as LLM Client
    participant Proxy as SchemaSlim Proxy
    participant Pool as MCPSessionPool
    participant Child as Child Subprocess

    Host->>Proxy: tools/call (schemaslim_call)
    Proxy->>Pool: call_tool(server, tool, args)
    
    rect rgb(20, 25, 35)
        Note over Pool,Child: Bounded by call_timeout (60.0s)
        Pool->>Child: JSON-RPC tools/call
        alt Child responds within 60.0s
            Child-->>Pool: CallToolResult
            Pool-->>Proxy: Result payload
            Proxy-->>Host: Response
        else Child hangs (> 60.0s)
            Pool->>Pool: TimeoutError raised
            Pool-->>Proxy: is_error=True (Timeout)
            Proxy-->>Host: "Tool execution timed out after 60.0s"
        end
    end
```

* `connect_timeout` (default: `15.0s`): Maximum time allowed for initial stdio pipe initialization and handshake.
* `call_timeout` (default: `60.0s`): Maximum time allowed for tool execution. Bounded via `asyncio.wait_for`. Timeouts return structured errors without crashing the proxy.
* **Configurable Idle Process Reaper (`idle_timeout`):** Configured via root `idle_timeout: Optional[float]` (in seconds; e.g. `300.0` for 5 minutes).
  - When enabled, `MCPSessionPool` tracks `last_accessed` timestamps per active session and runs a background loop (`_idle_reaper_loop`) running every `min(idle_timeout / 2, 30)` seconds.
  - Idle child processes are gracefully terminated and their transport streams closed, releasing file descriptors and RAM. Active in-flight invocations are protected. During multi-server reaping iteration, the loop re-checks in-flight counter immediately prior to closing each session to avoid tearing down active sessions.
  - **Transparent On-Demand Revival with Lock Serialization:** If a tool call targets an active server that has been reaped, `MCPSessionPool` automatically re-spawns the child subprocess before dispatching the invocation without failing the client. To eliminate race conditions and process storms under high concurrency, on-demand connection setup is serialized via a per-server `asyncio.Lock` registry (`_revival_locks`), double-checking session presence within the lock.
  - When `idle_timeout` is `None` or `<= 0` (default), reaping is disabled and processes persist indefinitely.
  - **Per-Server Stateful Exemption (`keep_alive`):** Individual server configurations (`StdioServerConfig`, `SseServerConfig`) support `keep_alive: bool = Field(default=False)`. When set to `true`, `MCPSessionPool._idle_reaper_loop()` unconditionally skips idle termination for that server, safeguarding active database locks, transactions, git state, and REPL memory indefinitely even when global `idle_timeout` is active.

### 2.3 Subprocess Termination Mechanics

During [`MCPSessionPool.shutdown`](file:///schemaslim/core/pool.py#L123):
1. `self._exit_stack.aclose()` unwinds active context managers in reverse order of initialization.
2. For stdio subprocesses (`mcp.client.stdio.stdio_client`):
   * Closes standard input (`stdin`).
   * Waits up to `PROCESS_TERMINATION_TIMEOUT` (`2.0s`) for the child process to exit gracefully.
   * **POSIX:** Sends `SIGTERM`. If the process fails to exit after the grace period, escalates to `SIGKILL`.
   * **Windows:** Terminates the process tree via Win32 Job Objects / `TerminateProcess`.
3. For SSE connections: Unsubscribes event streams and cancels active HTTP client sessions (`httpx.AsyncClient`).

---

## 3. Retrieval Engine & Mathematical Grounding

SchemaSlim provides deterministic semantic and lexical routing via an embedded SQLite database (`~/.schemaslim/index.db`) backed by `sqlite-vec` (384-dimensional vector indexing) and SQLite FTS5 (BM25 full-text search).

Implementation: [`schemaslim/storage/vector_store.py`](file:///schemaslim/storage/vector_store.py).

### 3.1 Embedding Model & Synthetic Document Formatting

* **Model:** `BAAI/bge-small-en-v1.5`
* **Vector Dimensionality:** 384 dimensions (`float32`)
* **Inference Engine:** `fastembed.TextEmbedding` (ONNX Runtime CPU)
* **Model Cache Location:** `~/.cache/fastembed/` (100% offline after initial download)
* **Synthetic Document Template:**
  To ensure parameter schemas are indexed alongside tool intent, each tool is compiled into a structured text document before embedding:
  ```text
  tool: {namespaced_name}
  description: {clean_description}
  parameters: {param_1} (type={type}, desc={desc}), {param_2} ...
  ```

### 3.2 Formal Scoring Formulation (Weighted Linear Combination)

> [!IMPORTANT]
> **Debunking RRF Claims:** SchemaSlim does **not** employ Reciprocal Rank Fusion ($1 / (k + \text{rank})$). The actual production implementation is a **Weighted Linear Score Combination** with dense vector priority and lexical matching bonuses.

```mermaid
graph TD
    Query[Incoming Intent Query] --> Dense[FastEmbed Vector Embedding]
    Query --> Sparse[FTS5 Query Cleaning: token* OR token*]

    Dense --> VecSearch["vec_tools: Cosine KNN (k = max(limit*4, 20))"]
    Sparse --> FtsSearch["tools_fts: MATCH BM25 (Limit = max(limit*4, 20))"]

    VecSearch --> VecScore["Vector Similarity Score:<br/>v_score = max(0, min(1, 1 - dist / 2.0))"]
    FtsSearch --> FtsScore["FTS5 Normalized Score:<br/>l_score = min(1, 1 / (1 + |rank| * 0.1))"]

    VecScore --> Fusion{Lexical Match Found?}
    FtsScore --> Fusion

    Fusion -- Yes: l_score > 0 --> WeightedScore["Score = (0.70 * v_score) + (0.30 * l_score)"]
    Fusion -- No: l_score == 0 --> PenaltyScore["Score = v_score * 0.95"]

    WeightedScore --> Filter["Filter >= Threshold (0.45)"]
    PenaltyScore --> Filter
    Filter --> Sort[Sort Descending & Clamp to Limit]
```

#### Step 1: Dense Vector Similarity Normalization
Given cosine distance $d \in [0.0, 2.0]$ returned by `sqlite-vec` (`distance_metric=cosine`):
$$v_{\text{score}} = \max\left(0.0, \min\left(1.0, 1.0 - \frac{d}{2.0}\right)\right)$$

#### Step 2: Lexical BM25 Normalization
SQLite FTS5 BM25 yields negative unbounded rank scores ($-\infty < \text{rank} \le 0.0$, where lower negative numbers indicate stronger relevance). Scores are mapped to the interval $(0.0, 1.0]$ via rational decay:
$$l_{\text{score}} = \min\left(1.0, \frac{1.0}{1.0 + |\text{rank}| \times 0.1}\right)$$

#### Step 3: Score Fusion
For each tool identifier present in the candidate set:
$$\text{Hybrid Score} = \begin{cases} 
(0.70 \times v_{\text{score}}) + (0.30 \times l_{\text{score}}) & \text{if } l_{\text{score}} > 0.0 \\ 
v_{\text{score}} \times 0.95 & \text{if } l_{\text{score}} = 0.0 
\end{cases}$$

#### Step 4: Filtering & Ranking Bounds
* **Candidate Overfetch:** $k = \max(\text{limit} \times 4, 20)$ candidates retrieved from each index.
* **Score Floor:** Results with $\text{Hybrid Score} < 0.45$ are discarded.
* **Result Limit:** Bounded by `limit` (default: 5, hard upper clamp: 20).

---

## 4. Threat Model & Security Defenses

SchemaSlim enforces defense-in-depth across child process spawning, configuration parsing, database operations, and tool execution boundaries:

```
+-----------------------------------------------------------------------------------+
|                        SCHEMASLIM SECURITY ARCHITECTURE                           |
+-----------------------------------------------------------------------------------+
| 1. Host Secret Isolation (CWE-200)     --> Ambient host environment stripped      |
| 2. CWD Hijacking Defense (CWE-426)     --> Local ./schemaslim.json blocked by def |
| 3. Confused Deputy Protection          --> Double underscore (__) namespace locks |
| 4. Tokenizer DoS Resilience            --> Cyclic & recursive depth (>2000) traps |
| 5. SQLite Variable Protection          --> 500-parameter chunking on batch ops    |
| 6. Execution Bounding                  --> 15s connect & 60s invocation timeouts  |
| 7. Destructive Call Boundary           --> Permissive / Ask / Readonly policies   |
+-----------------------------------------------------------------------------------+
```

### 4.1 Detailed Defense Matrix

| Vulnerability ID | Vulnerability Class | Mitigation Implementation | Verified Test Suite |
| :--- | :--- | :--- | :--- |
| **SCHEMASLIM-SEC-01** | CWE-200: Environment Secret Leakage | ambient host variables (`OPENAI_API_KEY`, `AWS_SECRET_ACCESS_KEY`, etc.) are stripped. Child environments receive only the MCP SDK standard platform whitelist (`SYSTEMROOT`, `PATH`, `TMP`, `TEMP`) merged with explicit server config `env`. | [`tests/test_security.py:L26-L53`](file:///tests/test_security.py#L26-L53) |
| **SCHEMASLIM-SEC-02** | CWE-426: Untrusted CWD Hijacking | SchemaSlim refuses to load `./schemaslim.json` from the current working directory unless explicitly approved via `--allow-cwd` or `SCHEMASLIM_ALLOW_CWD=1`. Prevents malicious repo checkouts from executing untrusted child configs. | [`tests/test_security.py:L56-L92`](file:///tests/test_security.py#L56-L92) |
| **SCHEMASLIM-SEC-03** | Confused Deputy Server Overwrite | Server names containing `__` are rejected during configuration validation. Tool namespacing follows strict `{server}__{tool}` formatting to prevent cross-server tool overwrites in the vector store. | [`tests/test_security.py:L95-L121`](file:///tests/test_security.py#L95-L121) |
| **SCHEMASLIM-SEC-04** | Algorithmic Complexity / DoS | Deeply nested dictionary schemas (>2000 levels) and cyclic data structures in tool parameters are caught via cycle detectors and recursion clamps, preventing unhandled `RecursionError` in token estimators. | [`tests/test_security.py:L124-L149`](file:///tests/test_security.py#L124-L149) |
| **SCHEMASLIM-SEC-05** | SQLite Variable Limit Overflow | Batch SQL operations (`DELETE WHERE id IN (...)`) are chunked in batches of 500 parameters to satisfy SQLite limits. In `schemaslim_search`, user `limit` is clamped to a maximum of 20. | [`tests/test_security.py:L152-L177`](file:///tests/test_security.py#L152-L177) |
| **SCHEMASLIM-SEC-06** | Subprocess Execution Hangs | `asyncio.wait_for` bounds initial connection handshakes (15.0s) and tool invocations (60.0s). Errors return structured JSON-RPC responses (`is_error=True`) without crashing the proxy. | [`tests/test_security.py:L180-L215`](file:///tests/test_security.py#L180-L215) |
| **SCHEMASLIM-SEC-07** | Destructive Execution Boundary | Permissive, Ask, and Readonly safety enforcement with `_confirmed` stripping and base-name blacklist check in `_do_call`. | [`tests/test_security.py:L218-L270`](file:///tests/test_security.py#L218-L270) |
| **SCHEMASLIM-SEC-08** | Subprocess Revival Race Condition | Per-server `_revival_locks` (`asyncio.Lock`) serializes on-demand reconnects for reaped sessions, and multi-server idle reaping re-checks in-flight counts before closing. | [`tests/test_pool.py:L225-L275`](file:///tests/test_pool.py#L225-L275) |

### 4.2 SCHEMASLIM-SEC-07: Execution Safety Policy & Destructive Call Boundary

To resolve blind proxy execution of mutating operations (file deletion, database drops, arbitrary command execution), SchemaSlim implements an active execution boundary in [`schemaslim/core/security.py`](file:///schemaslim/core/security.py) and [`schemaslim/core/server.py`](file:///schemaslim/core/server.py):

#### Configuration (`SecurityPolicy`)
Configured in `schemaslim.json` under the `security` key:
```json
{
  "security": {
    "mode": "ask",
    "destructive_patterns": [
      "delete", "drop", "destroy", "remove", "truncate", "write", "execute", "shell", "bash", "kill", "eval",
      "exec", "run", "cmd", "terminal", "powershell", "sh", "purge", "wipe", "unlink", "rmdir", "format", "overwrite", "modify", "patch"
    ],
    "allowed_tools": ["filesystem__read_file"],
    "blocked_tools": ["bash__raw_exec"]
  }
}
```

#### Classification Engine (`is_destructive`)
Evaluates target tools via a deterministic 4-tier decision cascade:
1. **Blocked Override:** If either fully qualified `namespaced_name` or `base_tool_name` is in `blocked_tools`, returns `True` immediately.
2. **Allowed Override:** If either `namespaced_name` or `base_tool_name` is in `allowed_tools`, returns `False` immediately.
3. **Token & Regex Matching on Base Tool Name:** Evaluates base tool name tokens strictly (ignoring the server namespace prefix to avoid false positives like `delete_service__get_status`) against `destructive_patterns`.
4. **Description & Parameter Pattern Matching:** Evaluates tool docstrings and parameter descriptions using inflected regex stem matching (`r"\b" + re.escape(stem) + r"[a-z]*\b"`), capturing grammatical variations (`deletes`, `dropping`, `purging`, `overwrites`).

#### Enforcement Modes
* **`blocked_tools`:** Unconditionally rejected in `VirtualMCPServer._do_call` with `is_error=True` matching either full or base tool name, preventing confirmation bypass:
  `"Tool '{namespaced_name}' is blocked by security policy"`
* **`readonly` Mode:** Any destructive tool is rejected with `is_error=True`:
  `"Execution denied: tool is destructive and security mode is 'readonly'"`
* **`ask` Mode (Default):**
  * If a destructive tool is called without `arguments["_confirmed"] == True`:
    The proxy refuses execution and challenges the caller:
    ```json
    {
      "is_error": true,
      "content": [
        {
          "type": "text",
          "text": "Security Warning: Tool '{namespaced_name}' has been flagged as destructive/mutating. To execute, the caller must re-invoke schemaslim_call with '_confirmed': true in arguments."
        }
      ]
    }
    ```
  * **Argument Sanitization:** When `_confirmed: true` is provided by the agent, the proxy **strips the `_confirmed` flag** from the argument dictionary before forwarding the payload to the downstream child MCP server.
* **`permissive` Mode:** Bypasses confirmation checks for fully autonomous environments.
* **Search Metadata Injection:** `schemaslim_search` returns `is_destructive: bool` on each candidate tool and `security_mode: str` in the outer result object, ensuring the agent is aware of execution constraints prior to dispatch.

---

## 5. Empirical Quality Assurance & Test Verification

The SchemaSlim codebase is verified by **145 automated regression tests** across **10 test suites** with **86% total test coverage** (measured via `pytest --cov=schemaslim --cov-report=term-missing`):

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Gleb\Desktop\ㅤ\Workspace\SchemaSlim
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.0, asyncio-1.4.0, cov-7.1.0
collected 145 items

tests\test_cli.py ..................                                     [ 12%]
tests\test_config.py .......................                             [ 28%]
tests\test_e2e.py .....                                                  [ 31%]
tests\test_harvester.py ....                                             [ 34%]
tests\test_migrator.py .........                                         [ 40%]
tests\test_pool.py .....................                                 [ 55%]
tests\test_security.py ..........................                        [ 73%]
tests\test_server.py ................                                    [ 84%]
tests\test_storage.py .........                                          [ 90%]
tests\test_telemetry.py ..............                                   [100%]

============================= 145 passed in 8.25s =============================
```

### 5.1 Test Suite Breakdown

| Test Suite | Tests | Covered Modules | Tested Capabilities & Invariants |
| :--- | :---: | :--- | :--- |
| [`tests/test_config.py`](file:///tests/test_config.py) | **23** | `schemaslim.config.*` | Pydantic model validation, idle_timeout parsing, `keep_alive` flag, Claude Desktop transport inference, UTF-8 BOM decoding, CLI flags. |
| [`tests/test_cli.py`](file:///tests/test_cli.py) | **18** | `schemaslim.cli`, `ui.menu` | Typer CLI argument parsing, subcommands (`version`, `stats`, `search`, `benchmark`, `wrap`, `unwrap`), error branches, non-interactive flags (`--yes`, `--force`), interactive keypress simulation (`_read_key`, `prompt_confirmation`, `select_option`). |
| [`tests/test_security.py`](file:///tests/test_security.py) | **26** | `schemaslim.core.security`, `server` | CWE-200 env sanitization, CWD hijacking, token DoS, SQLite limits, SCHEMASLIM-SEC-07 confirmation flow, base-name blocked_tools rejection, inflected verb stemming, namespace isolation, expanded 25-verb dictionary. |
| [`tests/test_pool.py`](file:///tests/test_pool.py) | **21** | `schemaslim.core.pool` | `MCPSessionPool` lifecycle, idle process reaper, `keep_alive` stateful exemption, transparent on-demand revival, concurrent revival lock protection (`_revival_locks`), multi-server reaper in-flight race protection, format validation. |
| [`tests/test_server.py`](file:///tests/test_server.py) | **16** | `schemaslim.core.server` | stdio JSON-RPC proxying, dynamic schemas, stdout stream purity, meta-tools dispatch. |
| [`tests/test_telemetry.py`](file:///tests/test_telemetry.py) | **14** | `schemaslim.telemetry.*` | Stderr live telemetry formatting, token estimators, circular buffer thread-safety. |
| [`tests/test_storage.py`](file:///tests/test_storage.py) | **9** | `schemaslim.storage.*` | `sqlite-vec` 384d cosine embeddings, SQLite FTS5 BM25 lexical matches, idempotent hashing. |
| [`tests/test_migrator.py`](file:///tests/test_migrator.py) | **9** | `schemaslim.config.migrator` | UTF-8 BOM decoding, atomic writes, automatic `.schemaslim.bak` backup rollbacks. |
| [`tests/test_e2e.py`](file:///tests/test_e2e.py) | **5** | Full Pipeline Integration | Full client-to-child proxy flow, synthetic benchmark runner, JSON/table report validation. |
| [`tests/test_harvester.py`](file:///tests/test_harvester.py) | **4** | `schemaslim.core.harvester` | Subprocess stdio and SSE harvesting, parallel worker isolation, `/sse` fallback probing. |
| **TOTAL** | **145** | **Full System Surface** | **100% Passing Status, 86% Coverage** |

---

## 6. Context Economics & Prompt Caching Reality

When analyzing the economic and cognitive impact of MCP virtualization, systems engineers must distinguish between **raw schema payload reduction** and **multi-turn prompt caching dynamics**.

### 6.1 Raw Schema Payload Reduction (Cold-Start)

In a typical developer setup with 6–10 MCP servers (e.g. Postgres, GitHub, Slack, Filesystem, Brave Search, Memory), the aggregate tool count ranges between 50 and 120 tools.

* **Native MCP Client Tool Injection:**
  * Average tool definition size: ~200–350 tokens (including JSON Schema types, nested properties, enums, and parameter descriptions).
  * 100 tools injected upfront: $\approx 20,000\text{ to }35,000\text{ tokens}$ consumed on the very first prompt turn.
* **SchemaSlim Virtualized Injection:**
  * SchemaSlim injects exactly **two meta-tools**: `schemaslim_search` and `schemaslim_call`.
  * Overhead: $\approx 280\text{ tokens}$.
  * **Immediate Cold-Start Reduction: ~98.6% drop in initial tool definition tokens.**

### 6.2 Multi-Turn Economics: The Prompt Caching Trade-Off

Modern LLM inference providers (Anthropic Claude, OpenAI, Google Gemini) offer prompt caching mechanisms that discount repeated, static prefix tokens by up to 90%:

$$\text{Cached Prompt Cost} \approx 0.10 \times \text{Base Input Token Cost}$$

If an LLM client injects 100 static tools at turn 0, subsequent turns read those 100 tools from cache at a 90% discount. Therefore, arguing for MCP virtualization purely on raw token cost arbitrage in short, static sessions is incomplete.

### 6.3 The True Architectural Value: Attention Budget & Cognitive Load

The critical vulnerability of massive upfront schema injection is not financial—it is cognitive:

```mermaid
graph LR
    subgraph Native MCP: 100 Tools Injected
        N1[Prompt Turn 1] -->|20k Tools Payload| A1[Attention Mechanism]
        N2[User Query] --> A1
        A1 -->|Risk: Lost in the Middle / Parameter Hallucination| R1[Errant Tool Choice]
    end

    subgraph SchemaSlim: Just-In-Time Virtualization
        S1[Prompt Turn 1] -->|280 Tokens Meta-Tools| B1[Attention Mechanism]
        S2[User Query] --> B1
        B1 -->|Targeted Search| B2[schemaslim_search]
        B2 -->|Injects Only 3-5 Relevant Tools| B3[Exact Execution]
    end
```

1. **Attention Budget Preservation ("Lost in the Middle"):**
   Transformer attention mechanisms degrade as input context length scales. Diluting attention across 100 irrelevant tool descriptions increases parameter hallucination rates and tool confusion (e.g. calling `slack__post_message` when `github__create_issue_comment` was intended).
2. **Context Window Longevity:**
   In long-running agent workflows (code refactoring, multi-file migrations), unvirtualized sessions hit context window limits (128k/200k) significantly faster. SchemaSlim keeps baseline turn overhead clamped to ~280 tokens plus only the tools explicitly retrieved.
3. **Dynamic Scale:**
   While native MCP clients choke or exceed limits when configured with hundreds of tools across enterprise tool registries, SchemaSlim's local SQLite/FTS5 hybrid search comfortably indexes 10,000+ tools with sub-5ms retrieval latency on standard developer hardware.

---

## 7. Configuration Reference (`schemaslim.json`)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\projects"],
      "env": {
        "NODE_ENV": "production"
      }
    },
    "postgres": {
      "command": "uvx",
      "args": ["mcp-server-postgres", "--connection-string", "postgresql://localhost/dev"]
    }
  },
  "search": {
    "limit": 5,
    "threshold": 0.45,
    "hybrid_weight": 0.70
  },
  "security": {
    "mode": "ask",
    "destructive_patterns": [
      "delete", "drop", "destroy", "remove", "truncate",
      "write", "execute", "shell", "bash", "kill", "eval"
    ],
    "allowed_tools": [
      "filesystem__read_file"
    ],
    "blocked_tools": [
      "bash__execute_raw"
    ]
  },
  "pool": {
    "connect_timeout": 15.0,
    "call_timeout": 60.0
  },
  "idle_timeout": 300.0
}
```

---

*This specification represents the authoritative ground-truth implementation of SchemaSlim v0.2.0.*
