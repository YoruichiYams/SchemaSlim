import React from 'react';
import { ShieldCheck, Lock, FileCode, GitFork, AlertCircle, Clock, Database } from 'lucide-react';

interface SecurityVector {
  code: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  vulnerability: string;
  mitigation: string;
  cwe: string;
  testedBy: string;
}

export const SecurityMatrix: React.FC = () => {
  const securityVectors: SecurityVector[] = [
    {
      code: 'SCHEMASLIM-SEC-01',
      title: 'Host Environment Secret Isolation',
      icon: Lock,
      vulnerability:
        'Child MCP stdio processes automatically inherit host environment variables, exposing ambient secrets like OPENAI_API_KEY, AWS_SECRET_ACCESS_KEY, and GitHub tokens to third-party MCP tools.',
      mitigation:
        'MCPSessionPool strictly sanitizes ambient environment variables prior to spawning. Only system basics (PATH, SYSTEMROOT) and explicitly configured server env keys are forwarded.',
      cwe: 'CWE-200: Exposure of Sensitive Information',
      testedBy: 'test_harvester_does_not_leak_host_environment',
    },
    {
      code: 'SCHEMASLIM-SEC-02',
      title: 'CWD Hijack & Config Injection Protection',
      icon: FileCode,
      vulnerability:
        'Cloning an untrusted repository containing a malicious ./schemaslim.json could trigger arbitrary process execution when running SchemaSlim in the repo folder.',
      mitigation:
        'Loading configs from the current working directory is blocked by default with a security error. Requires explicit --allow-cwd flag or SCHEMASLIM_ALLOW_CWD=1 with prominent stderr warnings.',
      cwe: 'CWE-426: Untrusted Search Path',
      testedBy: 'test_cwd_untrusted_config_blocked_by_default',
    },
    {
      code: 'SCHEMASLIM-SEC-03',
      title: 'Namespace Defense & Confused Deputy Prevention',
      icon: GitFork,
      vulnerability:
        'Malicious child servers could inject tool names colliding with trusted servers or use delimiter trickery (e.g. double underscores) to spoof admin actions.',
      mitigation:
        'Server IDs strictly validated against ^[a-zA-Z0-9_-]+$ (forbidding "__"). The VectorStore enforces immutable server boundaries, blocking cross-server tool overwrites.',
      cwe: 'CWE-441: Unintended Proxy or Intermediary',
      testedBy: 'test_vector_store_prevents_confused_deputy_overwrite',
    },
    {
      code: 'SCHEMASLIM-SEC-04',
      title: 'Recursion & Tokenizer DoS Protection',
      icon: AlertCircle,
      vulnerability:
        'Hostile or malformed JSON schemas containing circular dictionary references or deeply nested structures (e.g., 2,000+ levels) could trigger Python RecursionError crashes.',
      mitigation:
        'Bounded recursive schema traversal with cycle detection and depth ceiling. Malformed structures safely degrade to bounded fallback estimates without crashing the proxy.',
      cwe: 'CWE-674: Uncontrolled Recursion (DoS)',
      testedBy: 'test_estimate_tokens_deep_recursion_resilience',
    },
    {
      code: 'SCHEMASLIM-SEC-05',
      title: 'Search Clamping & SQLite Parameter Chunking',
      icon: Database,
      vulnerability:
        'Large queries or massive server uninstalls (>1,000 tools) can exceed SQLite variable limits (999 limit in older engines), causing unhandled OperationalErrors or memory exhaustion.',
      mitigation:
        'Client search limit is clamped to a safe maximum of 20 tools. Batch deletion queries in VectorStore are automatically split into 500-variable parameter chunks.',
      cwe: 'CWE-770: Allocation of Resources Without Limits',
      testedBy: 'test_remove_server_tools_large_volume_chunking',
    },
    {
      code: 'SCHEMASLIM-SEC-06',
      title: 'Subprocess Execution Timeouts',
      icon: Clock,
      vulnerability:
        'Hanging child MCP servers (e.g., stalled database queries or hung network connections) can permanently block LLM client turns, freezing agent workflows.',
      mitigation:
        'Strict asyncio timeouts enforced on all subprocess operations: 15s initialization handshake and 60s execution limit (configurable), gracefully returning standard MCP is_error=True.',
      cwe: 'CWE-400: Uncontrolled Resource Consumption',
      testedBy: 'test_virtual_mcp_server_handles_tool_timeout_cleanly',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Audit Header Info Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-zinc-800 text-xs font-mono text-zinc-500">
        <div>AUDIT STATUS: 6 OF 6 VECTORS HARDENED</div>
        <div className="text-emerald-400 flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4" />
          Zero Ambient Environment Leakage Enforced
        </div>
      </div>

      {/* Open Audit Ledger Format (Anti-Card Soup: Clean vertical rhythm with dividers) */}
      <div className="divide-y divide-zinc-850">
        {securityVectors.map((vec, idx) => {
          const Icon = vec.icon;
          return (
            <div key={idx} className="py-7 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: Identifier & CWE */}
              <div className="lg:col-span-4 space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <span className="font-mono text-xs font-bold text-white bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                    {vec.code}
                  </span>
                </div>
                <h3 className="text-base font-bold text-white">
                  {vec.title}
                </h3>
                <div className="text-xs font-mono text-zinc-500">
                  {vec.cwe}
                </div>
              </div>

              {/* Right Column: Threat & Hardening Mitigation */}
              <div className="lg:col-span-8 space-y-3">
                <div className="text-xs text-zinc-400 leading-relaxed">
                  <span className="text-zinc-500 font-mono uppercase text-[11px] block mb-0.5">Vulnerability Surface:</span>
                  {vec.vulnerability}
                </div>

                <div className="text-xs text-zinc-300 leading-relaxed pt-2 border-t border-zinc-900">
                  <span className="text-emerald-400 font-mono uppercase text-[11px] block mb-0.5 font-semibold">SchemaSlim Hardening:</span>
                  {vec.mitigation}
                </div>

                <div className="pt-2 text-[11px] font-mono text-zinc-500 flex flex-wrap items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>Regression Test: <code className="text-zinc-400 break-all">{vec.testedBy}()</code></span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
