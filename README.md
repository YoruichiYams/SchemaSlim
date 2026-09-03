# SchemaSlim

*Local JIT virtualizing reverse-proxy for Model Context Protocol.*

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol v1.3+](https://img.shields.io/badge/MCP-v1.3+-8A2BE2.svg)](https://modelcontextprotocol.io/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)](https://github.com/)
[![Tests](https://img.shields.io/badge/tests-104%20passed%20%7C%20100%25-brightgreen.svg)](https://github.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Cost](https://img.shields.io/badge/zero%20cost-100%25%20local-success.svg)](https://github.com/)

Connecting dozens of MCP servers causes severe **Tool Explosion**: loading hundreds of static tool schemas consumes 15,000–30,000 prompt tokens before a conversation even begins, inflating LLM costs and degrading reasoning quality. **SchemaSlim** replaces static tool schemas with exactly **2 dynamic meta-tools** (`schemaslim_search` and `schemaslim_call`), reducing context overhead by **70–90%** through fast local hybrid retrieval (`sqlite-vec` + `FTS5` + `FastEmbed`) with zero external API calls.

---

## Architecture & Data Flow

```text
┌─────────────────────────────────────────────────────────────┐
│              LLM Client (Claude / Antigravity / Cursor)     │
└──────────────────────────────┬──────────────────────────────┘
                               │ Exposes only 2 Meta-Tools:
                               │  • schemaslim_search(query, limit)
                               │  • schemaslim_call(namespaced_name, arguments)
┌──────────────────────────────▼──────────────────────────────┐
│                  SchemaSlim Virtual Proxy                   │
│                                                             │
│   FastEmbed (BGE-small)  ◄── Hybrid Search ──►  sqlite-vec  │
│   Dense Embeddings 384d                         BM25 FTS5   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Lazy Persistent Sessions (MCPSessionPool)
          ┌────────────────────┴───────────────────┐
          │                                        │
┌─────────▼──────────────┐              ┌──────────▼──────────────┐
│  Stdio Subprocesses    │              │  Remote SSE Endpoints   │
│  (GitHub, FS, Git...)  │              │  (Postgres, Motion, API)│
└────────────────────────┘              └─────────────────────────┘
```

---

## One-Command Quickstart

### 1. Install via `uv tool`
```bash
uv tool install schemaslim
```
*(Or install in an active Python virtual environment via `pip install schemaslim`)*

### 2. Wrap Existing MCP Clients Instantly
Automatically discovers configurations for **Claude Desktop**, **Google Antigravity**, **Cursor**, and **VS Code**, creates safe `.schemaslim.bak` backups, migrates server definitions to the global registry, and routes client traffic through SchemaSlim:

```bash
schemaslim wrap
```

To roll back at any time:
```bash
schemaslim unwrap
```

---

## Key Features

- **Zero Configuration Overhead**: One command (`schemaslim wrap`) auto-detects client configurations and virtualizes all tools in seconds with interactive confirmation (`Space` / `Enter`).
- **100% Local Hybrid Semantic Indexing**: Combines vector similarity (`sqlite-vec` + ONNX `FastEmbed BGE-small-en-v1.5`) and lexical keyword ranking (`SQLite FTS5 BM25`). Runs entirely offline with 0 API keys and zero network latency.
- **Dual-Mode Operation**:
  - Pure stdio RPC transport (clean JSON-RPC channel on stdout).
  - Live TUI telemetry dashboard on stderr (`schemaslim serve --tui`) showing real-time token savings and tool call latency.
- **Resilient & Cross-Platform**:
  - Full Windows UTF-8 BOM (`utf-8-sig`) handling for flawless PowerShell compatibility.
  - Automatic `/sse` URL normalization and fallback for remote endpoints.
- **Hardened Security Perimeter**:
  - Untrusted current working directory (`CWD`) configs blocked by default.
  - Process environment isolation preventing host secrets from leaking to child MCP tools.
  - Strict server namespace boundaries preventing confused deputy attacks.

---

## Token Economy & Benchmark

Measured on 4 realistic MCP servers (`git_server`, `db_server`, `fs_server`, `api_server`) with **20 tools**:

| Metric | Direct MCP (Static) | SchemaSlim (Virtualized) | Economy Impact |
| :--- | :---: | :---: | :---: |
| **Tools in Prompt** | 20 tools | **2 meta-tools** | **-90% tools loaded** |
| **Context Overhead** | 1,925 tokens | **~502 tokens** | **~74% token reduction** |
| **Tokens Saved (20-Turn Session)** | 0 tokens | **+28,460 tokens** | Major API cost savings |
| **Search Routing Latency** | — | **~50–55 ms** (p50: 53ms) | Transparent & near-instant |
| **Stream Integrity** | JSON-RPC | JSON-RPC (100% pure stdout) | Diagnostics isolated to stderr |

---

## Commands Cheatsheet

| Command | Usage | Description |
| :--- | :--- | :--- |
| `wrap` | `schemaslim wrap [-y] [--no-index]` | Auto-discover client configs, backup, and virtualize servers |
| `unwrap` | `schemaslim unwrap [-y]` | Restore original client config from `.schemaslim.bak` |
| `index` | `schemaslim index [-f] [-v]` | Harvest schemas from active child servers and build vector index |
| `search` | `schemaslim search "<query>" [-l 3]` | Test hybrid semantic tool retrieval from command line |
| `stats` | `schemaslim stats` | Display catalog token footprint and per-turn savings |
| `benchmark` | `schemaslim benchmark [-r 5]` | Run synthetic benchmark measuring savings and latency |
| `serve` | `schemaslim serve [--tui]` | Launch the virtualizing MCP server over stdio |
| `config` | `schemaslim config [validate\|show\|init]` | Validate, inspect, or initialize configuration |

---

## Security Architecture

- **Host Secret Isolation**: Child subprocesses do not inherit `os.environ`. Only explicitly configured environment variables are forwarded.
- **Untrusted CWD Protection**: Loading configurations from the current working directory (`./schemaslim.json`) is blocked by default; requires explicit `--allow-cwd` or `SCHEMASLIM_ALLOW_CWD=1`.
- **Confused Deputy Prevention**: Tool overwrites across server boundaries are strictly blocked; server IDs must match `^[a-zA-Z0-9_-]+$`.
- **DoS & Recursion Guards**: The schema token estimator is bounded against circular structures and deeply nested schemas.
- **SQLite Parameter Chunking**: Batch queries are split into chunks of 500 parameters to maintain compatibility across all SQLite engine limits.
- **Process Timeouts**: Subprocess lifecycle and tool invocations are guarded by strict timeouts (15s connect, 60s execution).

---

## Testing & Verification

Run the full automated test suite (104 unit, integration, and security tests):

```bash
uv run pytest -v
```

---

## License

MIT License © 2026 SchemaSlim Team.
