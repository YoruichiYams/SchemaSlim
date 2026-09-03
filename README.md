# SchemaSlim

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol v1.3+](https://img.shields.io/badge/MCP-v1.3+-8A2BE2.svg)](https://modelcontextprotocol.io/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)](https://github.com/)
[![Tests](https://img.shields.io/badge/tests-93%20passed%20%7C%20100%25-brightgreen.svg)](https://github.com/)
[![Security Audit](https://img.shields.io/badge/security-audit%20PASS-brightgreen.svg)](https://github.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Local virtualizing reverse-proxy for the Model Context Protocol (MCP). Eliminates **Tool Explosion** and context window exhaustion by replacing static multi-server tool schemas with on-demand semantic retrieval (`schemaslim_search`) and lazy proxy dispatch (`schemaslim_call`).

---

## Architecture

```text
┌─────────────────────────┐
│       LLM Client        │  (Claude Desktop, Antigravity, Cursor)
└────────────┬────────────┘
             │ Exposes exactly 2 Meta-Tools:
             │  • schemaslim_search(query, limit)
             │  • schemaslim_call(namespaced_name, arguments)
┌────────────▼────────────┐
│       SchemaSlim        │  ◄── FastEmbed + sqlite-vec (Dense + FTS5 BM25)
└────────────┬────────────┘
             │ Lazy Persistent Sessions (MCPSessionPool)
    ┌────────┴───────────────────────────┐
    │                                    │
┌───▼──────────────────┐        ┌────────▼─────────────┐
│ Stdio MCP Subprocess │        │    SSE MCP Server    │
│  (GitHub, Git, ...)  │        │   (Postgres, APIs)   │
└──────────────────────┘        └──────────────────────┘
```

---

## Benchmark & Token Economy

Evaluated on 4 realistic MCP servers (`git_server`, `db_server`, `fs_server`, `api_server`) with **20 tools**:

| Metric | Direct MCP (Baseline) | SchemaSlim (Virtualized) | Impact |
| :--- | :---: | :---: | :---: |
| **Active Tools in Prompt** | 20 tools | **2 meta-tools** | **-90% prompt tools** |
| **Context Size / Turn** | 1,925 tokens | **~502 tokens** | **~74% token reduction** |
| **Tokens Saved (20-Turn Session)** | 0 tokens | **~28,460 tokens saved** | Significant cost reduction |
| **Search Routing Latency** | — | **~50–55 ms** (p50: 53ms) | Near-instant local search |
| **Transport Stream Purity** | JSON-RPC | JSON-RPC (100% pure stdout) | Logs & TUI isolated to stderr |

---

## Quickstart

### 1. Installation

Install via `uv` (recommended) or `pip`:

```bash
# Global tool via uv
uv tool install schemaslim

# Or inside a project virtualenv
pip install schemaslim
```

### 2. Configuration

Generate a configuration file:

```bash
schemaslim config init
```

Configure child servers in `schemaslim.json` (or `~/.schemaslim/config.json`):

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./workspace"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..." }
    }
  },
  "settings": {
    "db_path": "~/.schemaslim/index.db",
    "top_k": 3
  }
}
```

Harvest and index tool schemas into the local vector database:

```bash
schemaslim index
```

### 3. Client Integration

#### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "schemaslim": {
      "command": "schemaslim",
      "args": ["serve"]
    }
  }
}
```

#### Google Antigravity IDE (`antigravity.json`)
```json
{
  "mcpServers": {
    "schemaslim": {
      "command": "schemaslim",
      "args": ["serve"]
    }
  }
}
```

---

## CLI Reference

| Command | Options | Description |
| :--- | :--- | :--- |
| `schemaslim index` | `[-c CONFIG] [--allow-cwd] [-f] [-v]` | Harvest schemas from child servers and update vector index |
| `schemaslim search "<query>"` | `[-l LIMIT] [-t THRESHOLD] [-c CONFIG] [--allow-cwd]` | Test hybrid semantic search query matching |
| `schemaslim serve` | `[-c CONFIG] [--allow-cwd] [--tui/--no-tui]` | Run virtualizing proxy server over stdio |
| `schemaslim stats` | `[-c CONFIG] [--allow-cwd]` | Display catalog footprint and token economy metrics |
| `schemaslim benchmark` | `[-r RUNS] [-o table\|json]` | Run synthetic stress benchmark measuring savings and latency |
| `schemaslim config validate` | `[PATH] [--allow-cwd] [-v]` | Validate configuration against Pydantic schema |
| `schemaslim config show` | `[PATH] [--allow-cwd]` | Display active configuration in formatted JSON |
| `schemaslim config init` | `[PATH] [-f]` | Generate a starter configuration template |

---

## Security Architecture

SchemaSlim is hardened against common proxy and supply-chain vulnerabilities:

- **Host Secret Isolation**: Child subprocesses do not inherit `os.environ`. Only explicitly configured environment variables (`config.env`) are passed; otherwise, the MCP SDK default environment filter applies.
- **Untrusted CWD Protection**: Loading configurations from the current working directory (`./schemaslim.json`) is blocked by default. Requires `--allow-cwd` or `SCHEMASLIM_ALLOW_CWD=1`. Trusted global paths (`~/.schemaslim/config.json`) are prioritized.
- **Confused Deputy Prevention**: Server identifiers are restricted to `^[a-zA-Z0-9_-]+$` without `__`. Tool overwrites across server boundaries are strictly rejected by the storage layer.
- **DoS & Recursion Guards**: The token estimator safely handles deeply nested payloads and circular references without uncaught `RecursionError`.
- **SQLite Variable Safety**: Search `limit` is capped at 20, and all batch queries (`WHERE IN`) are chunked in batches of 500 parameters.
- **Process Timeouts**: Child server connections (`15.0s`) and tool invocations (`60.0s`) are bounded by timeouts, converting child hangs into structured `is_error=True` responses.

---

## Configuration Presets

Pre-configured production templates are available in [`examples/`](file:///examples/):
- **[`examples/full-stack-dev.json`](file:///examples/full-stack-dev.json)**: GitHub, Filesystem, PostgreSQL, and Memory servers.
- **[`examples/minimal.json`](file:///examples/minimal.json)**: Minimal Filesystem and Fetch setup.

---

## Testing

Run the automated test suite (93 unit, integration, and security tests):

```bash
uv run pytest -v
```

---

## License

MIT License © 2026 SchemaSlim Team.
