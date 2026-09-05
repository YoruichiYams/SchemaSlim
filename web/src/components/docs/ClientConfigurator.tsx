import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  Copy,
  Check,
  Folder,
  Sparkles,
} from 'lucide-react';
import {
  ClaudeIcon,
  CursorIcon,
  AntigravityIcon,
  VSCodeIcon,
  WindsurfIcon,
  CodexIcon,
  CliIcon,
} from '../icons/ClientIcons';
import { copyToClipboard } from '../../utils/clipboard';

interface ClientSpec {
  id: string;
  name: string;
  badge: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  autoSupported: boolean;
  autoCommand: string;
  autoNote: string;
  paths: {
    macos: string;
    windows: string;
    linux: string;
  };
  configFileName: string;
  configFormat: 'json' | 'python';
  configSnippet: string;
  extraTip?: string;
}

export const ClientConfigurator: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const clientParam = searchParams.get('client');
  const [activeClient, setActiveClient] = useState<string>(clientParam || 'claude');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const clients: ClientSpec[] = [
    {
      id: 'claude',
      name: 'Claude Desktop',
      badge: 'Native GUI',
      icon: ClaudeIcon,
      description:
        'Official Anthropic desktop client. SchemaSlim intercepts the standard stdio bridge and replaces tens of static schemas with 2 meta-tools.',
      autoSupported: true,
      autoCommand: 'uvx schemaslim wrap',
      autoNote:
        'Automatically detected by SchemaSlim wrap. Creates claude_desktop_config.json.schemaslim.bak before rewriting.',
      paths: {
        macos: '~/Library/Application Support/Claude/claude_desktop_config.json',
        windows: '%APPDATA%\\Claude\\claude_desktop_config.json',
        linux: '~/.config/Claude/claude_desktop_config.json',
      },
      configFileName: 'claude_desktop_config.json',
      configFormat: 'json',
      configSnippet: `{
  "mcpServers": {
    "schemaslim": {
      "command": "uvx",
      "args": ["schemaslim", "serve"]
    }
  }
}`,
    },
    {
      id: 'cursor',
      name: 'Cursor IDE',
      badge: 'Editor Agent',
      icon: CursorIcon,
      description:
        'AI-first code editor with integrated Composer and MCP support. Works at workspace root or global user level.',
      autoSupported: true,
      autoCommand: 'uvx schemaslim wrap',
      autoNote:
        'Discovers .cursor/mcp.json in current directory or user home. Configures isolated proxying for workspace tools.',
      paths: {
        macos: '~/.cursor/mcp.json (or <workspace>/.cursor/mcp.json)',
        windows: '%USERPROFILE%\\.cursor\\mcp.json',
        linux: '~/.cursor/mcp.json',
      },
      configFileName: '.cursor/mcp.json',
      configFormat: 'json',
      configSnippet: `{
  "mcpServers": {
    "schemaslim": {
      "command": "uvx",
      "args": ["schemaslim", "serve"]
    }
  }
}`,
    },
    {
      id: 'antigravity',
      name: 'Google Antigravity',
      badge: 'Agentic IDE',
      icon: AntigravityIcon,
      description:
        'Google DeepMind agentic coding workspace. SchemaSlim reduces prompt token consumption across long-running autonomous turns.',
      autoSupported: true,
      autoCommand: 'uvx schemaslim wrap',
      autoNote:
        'Automatically detected in ~/.gemini/antigravity-ide/mcp_config.json with zero manual path specification.',
      paths: {
        macos: '~/.gemini/antigravity-ide/mcp_config.json',
        windows: '%USERPROFILE%\\.gemini\\antigravity-ide\\mcp_config.json',
        linux: '~/.gemini/antigravity-ide/mcp_config.json',
      },
      configFileName: 'mcp_config.json',
      configFormat: 'json',
      configSnippet: `{
  "mcpServers": {
    "schemaslim": {
      "command": "uvx",
      "args": ["schemaslim", "serve"]
    }
  }
}`,
    },
    {
      id: 'cline',
      name: 'VS Code (Cline / Roo)',
      badge: 'VS Code Extension',
      icon: VSCodeIcon,
      description:
        'Autonomous coding extensions (Cline, Roo Code, Claude Dev) running within Microsoft Visual Studio Code.',
      autoSupported: true,
      autoCommand: 'uvx schemaslim wrap --target cline_mcp_settings.json',
      autoNote:
        'Wrap supports targeting extension configuration files directly, preserving your custom provider API keys.',
      paths: {
        macos: '~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json',
        windows: '%APPDATA%\\Code\\User\\globalStorage\\saoudrizwan.claude-dev\\settings\\cline_mcp_settings.json',
        linux: '~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json',
      },
      configFileName: 'cline_mcp_settings.json',
      configFormat: 'json',
      configSnippet: `{
  "mcpServers": {
    "schemaslim": {
      "command": "uvx",
      "args": ["schemaslim", "serve"]
    }
  }
}`,
    },
    {
      id: 'windsurf',
      name: 'Windsurf',
      badge: 'Codeium Agent',
      icon: WindsurfIcon,
      description:
        'Codeium Windsurf IDE Cascade flows. SchemaSlim handles dynamic routing for cascade agent sessions without prompt saturation.',
      autoSupported: true,
      autoCommand: 'uvx schemaslim wrap',
      autoNote:
        'Auto-discovers ~/.codeium/windsurf/mcp_config.json and migrates static child servers into SchemaSlim backend catalog.',
      paths: {
        macos: '~/.codeium/windsurf/mcp_config.json',
        windows: '%USERPROFILE%\\.codeium\\windsurf\\mcp_config.json',
        linux: '~/.codeium/windsurf/mcp_config.json',
      },
      configFileName: 'mcp_config.json',
      configFormat: 'json',
      configSnippet: `{
  "mcpServers": {
    "schemaslim": {
      "command": "uvx",
      "args": ["schemaslim", "serve"]
    }
  }
}`,
    },
    {
      id: 'codex',
      name: 'Codex CLI / Runner',
      badge: 'CLI Runtime',
      icon: CodexIcon,
      description:
        'Command-line agent harness and OpenAI Codex terminal runtimes executing tools through MCP stdio transport.',
      autoSupported: true,
      autoCommand: 'uvx schemaslim wrap',
      autoNote:
        'Can be launched directly as a persistent proxy runner with rich terminal telemetry on stderr.',
      paths: {
        macos: '~/.codex/config.json',
        windows: '%USERPROFILE%\\.codex\\config.json',
        linux: '~/.codex/config.json',
      },
      configFileName: 'config.json',
      configFormat: 'json',
      configSnippet: `{
  "mcpServers": {
    "schemaslim": {
      "command": "uvx",
      "args": ["schemaslim", "serve", "--tui"]
    }
  }
}`,
    },
    {
      id: 'custom',
      name: 'Other CLI / Universal',
      badge: 'Custom Harness',
      icon: CliIcon,
      description:
        'Universal stdio integration for Kimi-K3, DeepSeek-harness, Qwen-agent, LangChain, LlamaIndex, or internal in-house LLM pipelines.',
      autoSupported: false,
      autoCommand: 'uvx schemaslim serve',
      autoNote:
        'Launch SchemaSlim as a standard subprocess over stdio. SchemaSlim handles indexing, hybrid search, and child isolation automatically.',
      paths: {
        macos: 'Arbitrary stdio subprocess transport',
        windows: 'Arbitrary stdio subprocess transport',
        linux: 'Arbitrary stdio subprocess transport',
      },
      configFileName: 'agent_harness.py',
      configFormat: 'python',
      configSnippet: `# Python agent harness integration (DeepSeek / Qwen / Kimi-K3 / LangChain)
import subprocess

# Spawn SchemaSlim as transparent JIT virtualizer
proxy = subprocess.Popen(
    ["uvx", "schemaslim", "serve"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Connect standard MCP JSON-RPC client over proxy.stdin / proxy.stdout.
# Initial prompt tokens: ~450 tokens total (schemaslim_search + schemaslim_call).
# Tools are resolved on-the-fly in <60ms via sqlite-vec + FTS5 BM25.`,
      extraTip:
        'Works with any programming language (Node.js, Go, Rust, Python) that supports spawning a child process with piped stdin/stdout.',
    },
  ];

  // Sync state with URL search param
  useEffect(() => {
    if (clientParam && clients.some((c) => c.id === clientParam)) {
      setActiveClient(clientParam);
    }
  }, [clientParam]);

  // Sync state with custom event from Footer or other navigation
  useEffect(() => {
    const handleCustomSelect = (e: Event) => {
      const customEvent = e as CustomEvent<{ clientId: string }>;
      if (customEvent.detail?.clientId && clients.some((c) => c.id === customEvent.detail.clientId)) {
        setActiveClient(customEvent.detail.clientId);
      }
    };
    window.addEventListener('schemaslim:select-client', handleCustomSelect);
    return () => window.removeEventListener('schemaslim:select-client', handleCustomSelect);
  }, []);

  const selectClient = (id: string) => {
    setActiveClient(id);
    const newParams = new URLSearchParams(searchParams);
    newParams.set('client', id);
    setSearchParams(newParams, { replace: true });
  };

  const current = clients.find((c) => c.id === activeClient) || clients[0];

  const handleCopy = async (key: string, text: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Client Selector Tabs (Sliding Pill) */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1 pb-2.5 border-b border-zinc-850 -mx-4 px-4 sm:mx-0 sm:px-1">
        {clients.map((client) => {
          const isActive = client.id === activeClient;
          return (
            <button
              key={client.id}
              onClick={() => selectClient(client.id)}
              className="relative px-3.5 py-2.5 min-h-[44px] text-xs font-mono transition-colors whitespace-nowrap cursor-pointer select-none rounded-lg flex items-center gap-2 shrink-0"
            >
              {isActive && (
                <motion.div
                  layoutId="client-config-tab"
                  className="absolute inset-0 bg-zinc-800 rounded-lg border border-zinc-700 shadow-sm"
                  transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                />
              )}
              <client.icon
                className={`w-4 h-4 relative z-10 transition-colors shrink-0 ${
                  isActive ? 'text-emerald-400' : 'text-zinc-500'
                }`}
              />
              <span
                className={`relative z-10 transition-colors ${
                  isActive ? 'text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {client.name}
              </span>
            </button>
          );
        })}
      </div>

      {/* Selected Client Details Container */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Client Overview & OS Paths */}
        <div className="lg:col-span-5 space-y-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                {current.badge}
              </span>
              <span className="text-zinc-500 text-xs font-mono">
                {current.configFileName}
              </span>
            </div>
            <h3 className="text-xl font-bold text-white tracking-tight">
              {current.name} Integration
            </h3>
            <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed font-normal">
              {current.description}
            </p>
          </div>

          {/* Recommended Auto Method */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-white font-semibold flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                Recommended Automated Setup
              </span>
              <span className="text-[10px] font-mono text-emerald-400">1-Step Wrap</span>
            </div>

            <div className="flex items-center justify-between bg-zinc-900/90 rounded-lg p-2.5 border border-zinc-800 font-mono text-xs text-zinc-200">
              <div className="flex items-center gap-2 overflow-x-auto">
                <span className="text-zinc-500 select-none">$</span>
                <span className="text-white">{current.autoCommand}</span>
              </div>
              <button
                onClick={() => handleCopy('auto', current.autoCommand)}
                className="ml-2 text-zinc-400 hover:text-white cursor-pointer transition-colors p-2 min-w-[36px] min-h-[36px] flex items-center justify-center rounded"
                title="Copy command"
              >
                {copiedKey === 'auto' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
            <p className="text-[11px] text-zinc-400 leading-snug">
              {current.autoNote}
            </p>
          </div>

          {/* Configuration File Paths */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-300 font-semibold">
              <Folder className="w-3.5 h-3.5 text-zinc-400" />
              <span>Standard Configuration File Paths</span>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-850">
                <div className="text-[10px] text-zinc-500 mb-0.5">macOS</div>
                <div className="text-zinc-300 text-[11px] break-all select-all leading-relaxed font-mono">
                  {current.paths.macos}
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-850">
                <div className="text-[10px] text-zinc-500 mb-0.5">Windows</div>
                <div className="text-zinc-300 text-[11px] break-all select-all leading-relaxed font-mono">
                  {current.paths.windows}
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-zinc-900/40 border border-zinc-850">
                <div className="text-[10px] text-zinc-500 mb-0.5">Linux</div>
                <div className="text-zinc-300 text-[11px] break-all select-all leading-relaxed font-mono">
                  {current.paths.linux}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Code Block / Manual Configuration */}
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-zinc-300 font-medium flex items-center gap-2">
              <span>Manual Configuration Snippet</span>
              <span className="text-[10px] text-zinc-500">
                ({current.configFileName})
              </span>
            </span>

            <button
              onClick={() => handleCopy('snippet', current.configSnippet)}
              className="inline-flex items-center gap-1.5 px-3 py-2 min-h-[36px] rounded-lg bg-zinc-800 hover:bg-zinc-750 text-xs font-mono text-zinc-200 transition-all cursor-pointer active:scale-95 border border-zinc-700/60"
            >
              {copiedKey === 'snippet' ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Copy Configuration</span>
                </>
              )}
            </button>
          </div>

          {/* Code Container */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800/80 bg-zinc-900/50 text-[11px] font-mono text-zinc-400">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <span className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <span className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <span className="ml-2 text-zinc-400">{current.configFileName}</span>
              </div>
              <span className="text-zinc-500 uppercase">{current.configFormat}</span>
            </div>

            <div className="p-4 sm:p-5 overflow-x-auto scrollbar-thin text-xs font-mono leading-relaxed text-zinc-300">
              <pre>
                <code>{current.configSnippet}</code>
              </pre>
            </div>
          </div>

          {/* Informational Guidance */}
          <div className="p-4 rounded-xl border border-zinc-850 bg-zinc-900/20 text-xs text-zinc-400 leading-relaxed space-y-1.5 font-normal">
            <div className="text-white font-medium text-[11px] font-mono uppercase tracking-wider">
              How It Resolves Under the Hood
            </div>
            <p>
              Your client launches <code className="text-white font-mono">schemaslim serve</code> as a single virtualized MCP server. When your agent dispatches a task intent, SchemaSlim queries its local <code className="text-zinc-300 font-mono">sqlite-vec</code> and <code className="text-zinc-300 font-mono">FTS5</code> index, injecting only relevant matching schemas on-the-fly.
            </p>
            {current.extraTip && (
              <p className="text-emerald-400/90 font-mono text-[11px]">
                Tip: {current.extraTip}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
