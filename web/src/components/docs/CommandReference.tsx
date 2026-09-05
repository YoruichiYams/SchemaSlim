import React from 'react';
import { Terminal, Shield, Zap, RefreshCw, BarChart2 } from 'lucide-react';

interface FlagSpec {
  flag: string;
  type?: string;
  desc: string;
}

interface CommandSpec {
  name: string;
  signature: string;
  badge: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  flags: FlagSpec[];
}

export const CommandReference: React.FC = () => {
  const commands: CommandSpec[] = [
    {
      name: 'wrap',
      signature: 'schemaslim wrap [options]',
      badge: 'Setup',
      icon: Zap,
      description:
        'Scans installed LLM clients on the host system, creates safe .schemaslim.bak backups, migrates static MCP servers into SchemaSlim backend catalog, and configures proxying.',
      flags: [
        {
          flag: '--yes, -y',
          desc: 'Automatically proceed with discovered client migrations without interactive confirmation.',
        },
        {
          flag: '--dry-run',
          desc: 'Simulate configuration discovery and schema extraction without writing files to disk.',
        },
        {
          flag: '--target <path>',
          type: 'path',
          desc: 'Directly target an arbitrary MCP settings JSON file (e.g. Cline, Roo Code, custom harness).',
        },
      ],
    },
    {
      name: 'unwrap',
      signature: 'schemaslim unwrap [options]',
      badge: 'Rollback',
      icon: RefreshCw,
      description:
        'Performs an instant, zero-risk restoration of untouched original client configuration files from backup copies.',
      flags: [
        {
          flag: '--force',
          desc: 'Force immediate overwriting of active configuration files with backup versions without confirmation.',
        },
        {
          flag: '--target <path>',
          type: 'path',
          desc: 'Specify an explicit configuration file to restore.',
        },
      ],
    },
    {
      name: 'serve',
      signature: 'schemaslim serve [options]',
      badge: 'Core Runtime',
      icon: Terminal,
      description:
        'Runs the high-performance virtualizing stdio reverse-proxy. Delivers only 2 meta-tools to LLM clients and dispatches tool calls in sub-60ms via sqlite-vec.',
      flags: [
        {
          flag: '--tui',
          desc: 'Renders a live Rich telemetry monitor in the stderr stream while keeping stdout JSON-RPC 100% pure.',
        },
        {
          flag: '--allow-cwd',
          desc: 'Enables child servers to inherit current working directory. Disabled by default to prevent CWE-426 binary hijacking.',
        },
        {
          flag: '--timeout <sec>',
          type: 'integer',
          desc: 'Execution and handshake timeout threshold in seconds before terminating hung child processes (default: 60).',
        },
      ],
    },
    {
      name: 'index',
      signature: 'schemaslim index [options]',
      badge: 'Vector Index',
      icon: Shield,
      description:
        'Forces local embedding generation via ONNX FastEmbed (BGE-small-en-v1.5) and populates SQLite FTS5 lexical indexes.',
      flags: [
        {
          flag: '--force',
          desc: 'Re-embed and rebuild both sqlite-vec dense embeddings and FTS5 BM25 search tables from scratch.',
        },
      ],
    },
    {
      name: 'stats',
      signature: 'schemaslim stats [options]',
      badge: 'Telemetry',
      icon: BarChart2,
      description:
        'Outputs a terminal telemetry summary of total prompt tokens saved, active child servers, vector database disk footprint, and cache performance.',
      flags: [
        {
          flag: '--tui',
          desc: 'Format output with styled Rich terminal layout.',
        },
      ],
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-white tracking-tight">
            CLI Command &amp; Flags Reference
          </h3>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1 font-normal">
            SchemaSlim exposes a minimal, hardened command-line interface for wrapping, proxying, and telemetry.
          </p>
        </div>
        <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-400">
          <span>v0.1.3</span>
          <span className="text-zinc-600">•</span>
          <span>100% Local</span>
        </div>
      </div>

      {/* Minimalist Open Table (Anti-Card Soup) */}
      <div className="border-t border-zinc-800/80 divide-y divide-zinc-850">
        {commands.map((cmd) => (
          <div
            key={cmd.name}
            className="py-6 first:pt-4 last:pb-2 grid grid-cols-1 md:grid-cols-12 gap-6 items-start"
          >
            {/* Command Header Column */}
            <div className="md:col-span-4 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-900 text-zinc-400 border border-zinc-800 font-medium">
                  {cmd.badge}
                </span>
                <span className="font-mono text-sm font-bold text-white">
                  schemaslim {cmd.name}
                </span>
              </div>
              <div className="font-mono text-xs text-emerald-400 font-semibold bg-zinc-900/60 px-2 py-1 rounded border border-zinc-800/80 inline-block break-all max-w-full">
                $ {cmd.signature}
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed font-normal pt-1">
                {cmd.description}
              </p>
            </div>

            {/* Flags Column */}
            <div className="md:col-span-8 space-y-2.5 w-full overflow-hidden">
              <span className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider block">
                Available Flags
              </span>
              <div className="space-y-2">
                {cmd.flags.map((flag) => (
                  <div
                    key={flag.flag}
                    className="p-3 rounded-lg bg-zinc-900/30 border border-zinc-850/80 flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 break-words"
                  >
                    <div className="flex flex-wrap items-center gap-2 font-mono text-xs text-white">
                      <span className="font-semibold text-zinc-200 break-all">{flag.flag}</span>
                      {flag.type && (
                        <span className="text-[10px] text-zinc-500">[{flag.type}]</span>
                      )}
                    </div>
                    <div className="text-xs text-zinc-400 leading-snug sm:text-right max-w-md font-normal">
                      {flag.desc}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
