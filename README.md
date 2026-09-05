<div align="center">

# SchemaSlim

**Universal MCP Virtualization & Local Hybrid Search Reverse-Proxy**

[![Live Demo](https://img.shields.io/badge/Live_Demo-schemaslim.pages.dev-10b981?style=flat-square&logo=cloudflarepages&logoColor=white)](https://schemaslim.pages.dev)
[![Tests](https://img.shields.io/badge/pytest-104_passed-emerald?style=flat-square&logo=pytest&logoColor=white)](https://schemaslim.pages.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-zinc?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-zinc?style=flat-square&logo=python&logoColor=white)](https://python.org)

Connecting dozens of MCP servers wastes 10,000–30,000 prompt tokens on static schemas before turn one.  
SchemaSlim virtualizes tool discovery into on-demand retrieval, presenting exactly **2 dynamic meta-tools** and resolving tools in **<60ms** via offline hybrid vector retrieval.

[Live Documentation & Client Matrix ↗](https://schemaslim.pages.dev/docs)

</div>

---

## Key Highlights

- **85%+ Prompt Footprint Reduction:** Shrinks multi-server tool schemas down to 2 meta-tools (`schemaslim_search` and `schemaslim_call`).
- **Sub-60ms JIT Retrieval:** 100% local FastEmbed (`BGE-small-en-v1.5`) + SQLite-vec cosine search + SQLite FTS5 BM25 with Reciprocal Rank Fusion. Zero external API calls.
- **Process & Secret Isolation (CWE-200 Safe):** Strips ambient host environment variables (`OPENAI_API_KEY`, AWS tokens) before spawning child MCP processes.
- **Path Traversal Defense (CWE-426 Safe):** Explicitly isolates execution directory and guards against local CWD hijacking.
- **Zero-Config Ecosystem Discovery:** One-command scanning, backup (`.schemaslim.bak`), and virtualization across Claude Desktop, Cursor, Antigravity, VS Code, Windsurf, Codex, and custom CLI harnesses.

---

## Quick Install

Run via `uvx` (zero installation footprint):

```bash
# Automated discovery and configuration wrapping
uvx schemaslim wrap

# Start virtualizing stdio reverse-proxy
uvx schemaslim serve
```

Or install persistently:

```bash
uv tool install schemaslim
```

---

## Supported Ecosystems

| Client / Environment | Config Target | Integration Command |
| :--- | :--- | :--- |
| **Claude Desktop** | `claude_desktop_config.json` | `uvx schemaslim wrap` |
| **Cursor IDE** | `.cursor/mcp.json` | `uvx schemaslim wrap` |
| **Google Antigravity** | `~/.gemini/antigravity-ide/mcp_config.json` | `uvx schemaslim wrap` |
| **VS Code (Cline / Roo)** | `cline_mcp_settings.json` | `uvx schemaslim wrap --target <path>` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` | `uvx schemaslim wrap` |
| **Codex CLI / Runner** | Stdio MCP Harness | `schemaslim serve --tui` |
| **Other CLI / Custom** | DeepSeek / Qwen / Kimi / LangChain | Custom subprocess bridge |

Full setup instructions and copyable snippets are available in the [Documentation Hub](https://schemaslim.pages.dev/docs).

---

## Architecture Flow

```
[ LLM Client: Claude / Cursor / Antigravity / CLI ]
                      │
                      ▼ (stdio JSON-RPC)
      ┌───────────────────────────────┐
      │     SchemaSlim Virtualizer    │
      │  (Exposes 2 dynamic schemas)  │
      └──────────────┬────────────────┘
                     │
         Hybrid JIT Resolution (<60ms)
                     ▼
      ┌───────────────────────────────┐
      │  Local SQLite-vec 384d Embed  │
      │   + SQLite FTS5 BM25 Lookup   │
      └──────────────┬────────────────┘
                     │
         Isolated Ephemeral Dispatch
                     ▼
      ┌───────────────────────────────┐
      │  Isolated MCP Child Processes │
      │   (CWE-200 Secret Stripping)  │
      └───────────────────────────────┘
```

---

## CLI Reference

- `schemaslim wrap`: Scan client configs, generate atomic backups, index tools, and inject proxy.
- `schemaslim serve`: Run runtime stdio reverse-proxy (`--tui` for live stderr telemetry, `--allow-cwd` for dev overrides).
- `schemaslim index`: Recompute offline FastEmbed ONNX vectors and FTS5 indices (`--force` to rebuild).
- `schemaslim stats`: Terminal report of prompt tokens preserved, active servers, and latency breakdown.
- `schemaslim unwrap`: Lossless rollback to original client configurations.

---

## Testing & Quality Assurance

SchemaSlim maintains a 100% passing test suite across migration atomicity, stream safety, secret stripping, and vector search:

```bash
uv run pytest
# 104 passed in ~4.3s
```

Interactive test reports and coverage breakdowns can be viewed live in the [Web Dashboard](https://schemaslim.pages.dev).

---

## License

Distributed under the [MIT License](LICENSE). Offline & Zero API Keys.
