import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Terminal, Database, Server, Shield, Zap, Check } from 'lucide-react';
import { ArchitectureFlow } from './ArchitectureFlow';

interface Step {
  id: number;
  title: string;
  badge: string;
  icon: React.ComponentType<{ className?: string }>;
  headline: string;
  description: string;
  metrics: string;
  codeSnippet: string;
}

export const Architecture: React.FC = () => {
  const [selectedStep, setSelectedStep] = useState<number>(3); // Default to Hybrid Search

  const steps: Step[] = [
    {
      id: 1,
      title: 'Minimal Meta-Tools',
      badge: 'Client Init',
      icon: Terminal,
      headline: 'Agent Client Initializes With Only 2 Meta-Tools',
      description:
        'Instead of injecting dozens or hundreds of static schemas directly into prompt tokens, the LLM agent client (Claude Desktop, Cursor, Antigravity) receives exactly 2 meta-tools: schemaslim_search and schemaslim_call (~450 tokens total).',
      metrics: '~450 tokens total overhead | 90% reduction',
      codeSnippet: `// Exposed directly in initial system prompt
tools = [
  {
    name: "schemaslim_search",
    description: "Search for available MCP tools matching intent query.",
    parameters: { query: string, limit?: number }
  },
  {
    name: "schemaslim_call",
    description: "Execute a specific tool on a target MCP server.",
    parameters: { namespaced_name: string, arguments: object }
  }
]`,
    },
    {
      id: 2,
      title: 'Intent Retrieval',
      badge: 'LLM Intent',
      icon: Zap,
      headline: 'Agent Dispatches Natural Language Tool Query',
      description:
        'When the agent needs capability, it invokes schemaslim_search with a natural language task description like "query database users" or "inspect git diff".',
      metrics: 'Standard MCP JSON-RPC call | Zero context bloat',
      codeSnippet: `// LLM calls meta-tool via JSON-RPC stdio
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "schemaslim_search",
    "arguments": {
      "query": "find active postgres users and table schemas",
      "limit": 2
    }
  }
}`,
    },
    {
      id: 3,
      title: 'Local Hybrid Index',
      badge: 'sqlite-vec + FTS5',
      icon: Database,
      headline: 'Sub-60ms Hybrid Dense + Lexical Lookup',
      description:
        'SchemaSlim embeds the query locally using FastEmbed (ONNX BGE-small-en-v1.5 384d) and merges dense vector similarity (sqlite-vec) with keyword ranking (SQLite FTS5 BM25). 100% offline, zero API keys.',
      metrics: 'p50: 53.1ms | 0 external network calls | ~115 MB RAM',
      codeSnippet: `// Executed in local C-extension sqlite-vec & SQLite FTS5
WITH vector_matches AS (
  SELECT tool_id, distance
  FROM vec_tools
  WHERE embedding MATCH :query_vector
  ORDER BY distance LIMIT 20
),
fts_matches AS (
  SELECT rowid AS tool_id, bm25(tools_fts) AS bm25_score
  FROM tools_fts
  WHERE tools_fts MATCH :bm25_query LIMIT 20
)
-- Reciprocal Rank Fusion (RRF) computes final relevance score`,
    },
    {
      id: 4,
      title: 'Subprocess Routing',
      badge: 'MCPSessionPool',
      icon: Server,
      headline: 'Lazy Process Spawning & Secret Dropping',
      description:
        'MCPSessionPool initializes the target child MCP server only when a tool is actually called. Ambient host environment variables (OPENAI_API_KEY, AWS keys) are stripped; only explicitly whitelisted variables are passed.',
      metrics: 'os.environ stripped | 15s handshake / 60s execution timeout',
      codeSnippet: `// schemaslim/core/pool.py: MCPSessionPool
# SEC-01 Hardening: Drops host secrets before spawning
clean_env = {
  "PATH": os.environ.get("PATH", ""),
  "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
  **server_config.env  # ONLY explicit user-configured variables
}

child_process = await asyncio.create_subprocess_exec(
  server_config.command, *server_config.args,
  env=clean_env, stdin=PIPE, stdout=PIPE, stderr=PIPE
)`,
    },
    {
      id: 5,
      title: 'Execution & Stdio Purity',
      badge: 'Pure Stdio',
      icon: Shield,
      headline: 'Direct Tool Execution via schemaslim_call',
      description:
        'The call is dispatched to the isolated child server. The child response is proxied back to the LLM client on stdout. Stderr is reserved for the live Rich telemetry dashboard, guaranteeing 100% JSON-RPC stream integrity.',
      metrics: 'Zero stdout stream corruption | Full MCP v1.3+ compliance',
      codeSnippet: `// Response delivered to LLM client on pure stdout
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\\"users\\": [{\\"id\\": 101, \\"email\\": \\"alice@example.com\\"}]}"
      }
    ],
    "isError": false
  }
}`,
    },
  ];

  const currentStep = steps.find((s) => s.id === selectedStep) || steps[2];

  return (
    <div className="space-y-10">
      {/* 1. Interactive Visual Flow Pipeline */}
      <ArchitectureFlow selectedStep={selectedStep} onSelectStep={setSelectedStep} />

      {/* 2. Spec Sheet Step Switcher Bar (Animated Sliding Tabs) */}
      <div className="border-b border-zinc-850">
        <div className="flex overflow-x-auto no-scrollbar gap-2 pb-3 -mx-4 px-4 sm:mx-0 sm:px-0">
          {steps.map((step) => {
            const isSelected = step.id === selectedStep;
            return (
              <button
                key={step.id}
                onClick={() => setSelectedStep(step.id)}
                className="relative flex items-center gap-2 px-3.5 py-2 min-h-[44px] rounded-lg text-xs font-mono transition-colors whitespace-nowrap cursor-pointer select-none shrink-0"
              >
                {isSelected && (
                  <motion.div
                    layoutId="architecture-step-tab"
                    className="absolute inset-0 bg-zinc-800 border border-zinc-700 rounded-lg shadow-sm"
                    transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                  />
                )}
                <span className={`relative z-10 ${isSelected ? 'text-zinc-300 font-semibold' : 'text-zinc-500'}`}>
                  0{step.id}
                </span>
                <span className={`relative z-10 transition-colors ${isSelected ? 'text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'}`}>
                  {step.title}
                </span>
                <span className="relative z-10 text-[10px] text-zinc-500 hidden sm:inline">
                  [{step.badge}]
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Technical Spec Sheet Layout (Exposed directly on canvas) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Technical Overview */}
        <div className="lg:col-span-5 space-y-6">
          <div>
            <div className="inline-flex items-center gap-2 text-xs font-mono text-emerald-400 mb-2">
              <Check className="w-3.5 h-3.5" />
              STAGE 0{currentStep.id} OF 05
            </div>
            <h3 className="text-xl sm:text-2xl font-bold text-white tracking-tight leading-snug">
              {currentStep.headline}
            </h3>
          </div>

          <p className="text-sm text-zinc-400 leading-relaxed font-normal">
            {currentStep.description}
          </p>

          <div className="pt-4 border-t border-zinc-850">
            <div className="text-xs font-mono text-zinc-500 uppercase mb-1">
              Performance &amp; Isolation Profile
            </div>
            <div className="text-sm font-mono text-zinc-200">
              {currentStep.metrics}
            </div>
          </div>
        </div>

        {/* Right Column: Code Specification */}
        <div className="lg:col-span-7">
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden terminal-frame">
            <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-850 bg-zinc-900/40 text-xs font-mono text-zinc-500">
              <span>{currentStep.badge} Specification</span>
              <span className="text-zinc-400">stdio JSON-RPC</span>
            </div>
            <pre className="p-4 sm:p-5 text-xs font-mono text-zinc-300 overflow-x-auto scrollbar-thin leading-relaxed max-h-[360px]">
              <code>{currentStep.codeSnippet}</code>
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
