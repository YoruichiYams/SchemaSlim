import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { Terminal, Zap, CheckCircle2, RefreshCw, Copy, Check } from 'lucide-react';
import { ConstellationGrid } from './ConstellationGrid';
import { InView } from './ui/in-view';
import { copyToClipboard } from '../utils/clipboard';

interface HeroProps {
  onExploreClick?: () => void;
}

export const Hero: React.FC<HeroProps> = ({ onExploreClick }) => {
  const [activeTab, setActiveTab] = useState<'wrap' | 'search' | 'stats'>('wrap');
  const [copied, setCopied] = useState(false);
  const [wrapStep, setWrapStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);

  // Animated step progression for wrap tab
  useEffect(() => {
    if (activeTab !== 'wrap' || !isPlaying) return;
    const interval = setInterval(() => {
      setWrapStep((prev) => (prev < 4 ? prev + 1 : 4));
    }, 1100);
    return () => clearInterval(interval);
  }, [activeTab, isPlaying]);

  // Keyboard navigation: 1 -> wrap, 2 -> search, 3 -> stats (isolated without modifier keys or open modals)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Prevent collision with browser tab switching (Ctrl+1, Cmd+2, etc.) or shortcut combinations
      if (e.ctrlKey || e.metaKey || e.altKey) {
        return;
      }
      // Block if modal is open (body overflow is hidden)
      if (typeof document !== 'undefined' && document.body.style.overflow === 'hidden') {
        return;
      }
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName) || target?.isContentEditable) {
        return;
      }
      if (e.key === '1') {
        setActiveTab('wrap');
        setWrapStep(4);
      } else if (e.key === '2') {
        setActiveTab('search');
      } else if (e.key === '3') {
        setActiveTab('stats');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const restartSimulation = () => {
    setWrapStep(0);
    setIsPlaying(true);
  };

  const handleCopy = async (text: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const terminalTabs = [
    { key: 'wrap', label: 'wrap', shortcut: '1' },
    { key: 'search', label: 'search', shortcut: '2' },
    { key: 'stats', label: 'stats', shortcut: '3' },
  ] as const;

  return (
    <section className="relative pt-12 pb-20 md:pt-20 md:pb-28 overflow-hidden">
      {/* Constellation Grid Dynamic Physics Canvas Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <ConstellationGrid />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header Badges & Headline */}
        <div className="text-center max-w-3xl mx-auto mb-10 select-none">
          {/* Top Status Badges */}
          <InView transition={{ delay: 0.05 }}>
            <div className="inline-flex flex-wrap items-center justify-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-400 mb-6">
              <span className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                v0.1.0 Ready
              </span>
              <span className="text-zinc-700">•</span>
              <span>100% Local</span>
              <span className="text-zinc-700">•</span>
              <span className="text-zinc-300">0 API Keys</span>
              <span className="text-zinc-700">•</span>
              <span className="text-zinc-500">Python 3.12+</span>
            </div>
          </InView>

          <InView transition={{ delay: 0.1 }}>
            <h1 className="select-none text-3xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white mb-5 leading-[1.15] text-balance">
              Compress MCP Context by 85% with a{' '}
              <span className="text-zinc-400 font-medium">Local Hybrid Proxy</span>
            </h1>
          </InView>

          <InView transition={{ delay: 0.15 }}>
            <p className="select-none text-sm sm:text-base text-zinc-400 leading-relaxed max-w-2xl mx-auto mb-8 font-normal text-balance">
              Connecting dozens of MCP servers wastes 15,000–30,000 prompt tokens on static schemas before turn one.{' '}
              <span className="text-zinc-200 font-medium">SchemaSlim</span> exposes only{' '}
              <span className="text-emerald-400 font-mono font-medium">2 dynamic meta-tools</span> and resolves tools in &lt;60ms via offline hybrid vector retrieval.
            </p>
          </InView>

          {/* Action Buttons */}
          <InView transition={{ delay: 0.2 }}>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3 w-full max-w-md sm:max-w-none mx-auto">
              <button
                onClick={() => handleCopy('uvx schemaslim wrap')}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-white hover:bg-zinc-200 text-zinc-950 font-mono font-semibold text-xs sm:text-sm transition-all duration-150 active:scale-[0.98] cursor-pointer shadow-sm min-h-[44px]"
              >
                <Terminal className="w-4 h-4 text-zinc-900" />
                <span>uvx schemaslim wrap</span>
                {copied ? (
                  <Check className="w-4 h-4 ml-1 text-emerald-600" />
                ) : (
                  <Copy className="w-3.5 h-3.5 ml-1 text-zinc-500" />
                )}
              </button>

              {onExploreClick && (
                <button
                  onClick={onExploreClick}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-zinc-900 hover:bg-zinc-850 text-zinc-300 hover:text-white font-medium text-xs sm:text-sm transition-all duration-150 border border-zinc-800 active:scale-[0.98] cursor-pointer min-h-[44px]"
                >
                  <Zap className="w-4 h-4 text-zinc-400" />
                  <span>Calculate Token Savings</span>
                </button>
              )}
            </div>
          </InView>
        </div>

        {/* Terminal Interactive Simulator (Container Discipline: Widget Panel) */}
        <InView transition={{ delay: 0.25 }}>
          <div className="w-full max-w-4xl mx-auto overflow-hidden">
            <div className="w-full rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-2xl terminal-frame">
              {/* Terminal Window Header Bar */}
              <div className="flex flex-wrap items-center justify-between px-3 sm:px-4 py-2.5 border-b border-zinc-800/80 bg-zinc-900/60 gap-2">
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-zinc-700 inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-zinc-700 inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-zinc-700 inline-block" />
                  </div>
                  <span className="ml-1 text-[11px] sm:text-xs font-mono text-zinc-400 flex items-center gap-1.5">
                    <Terminal className="w-3.5 h-3.5 text-zinc-400" />
                    schemaslim
                  </span>
                </div>

                {/* Animated Sliding Tabs with Keyboard Shortcuts (Mobile compact) */}
                <div className="flex items-center gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-800 overflow-x-auto max-w-full">
                  {terminalTabs.map((tab) => {
                    const isActive = activeTab === tab.key;
                    return (
                      <button
                        key={tab.key}
                        onClick={() => {
                          setActiveTab(tab.key);
                          if (tab.key === 'wrap') setWrapStep(4);
                        }}
                        className="relative px-2.5 py-1.5 text-[11px] sm:text-xs font-mono transition-colors cursor-pointer select-none rounded-md flex items-center gap-1 whitespace-nowrap min-h-[32px]"
                      >
                        {isActive && (
                          <motion.div
                            layoutId="terminal-tab"
                            className="absolute inset-0 bg-zinc-800 rounded-md"
                            transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                          />
                        )}
                        <span className="relative z-10 text-[10px] text-zinc-500 font-normal hidden sm:inline">
                          [{tab.shortcut}]
                        </span>
                        <span
                          className={`relative z-10 transition-colors ${
                            isActive ? 'text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'
                          }`}
                        >
                          $ {tab.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Terminal Screen Body with Rich Syntax Highlighting */}
              <div className="p-4 sm:p-5 font-mono text-xs sm:text-sm text-zinc-300 min-h-[330px] bg-zinc-950 overflow-x-auto scrollbar-thin leading-relaxed w-full">
              {/* TAB 1: WRAP */}
              {activeTab === 'wrap' && (
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between text-zinc-500 pb-1.5 border-b border-zinc-900 text-[11px]">
                    <span>DISCOVERY &amp; VIRTUALIZATION ENGINE</span>
                    <button
                      onClick={restartSimulation}
                      className="flex items-center gap-1 text-zinc-400 hover:text-white cursor-pointer"
                    >
                      <RefreshCw className="w-3 h-3" />
                      Replay
                    </button>
                  </div>

                  <div className="text-zinc-400">
                    <span className="text-zinc-100 font-semibold">devbox</span>:<span className="text-zinc-400">~</span>$ <span className="text-white font-semibold">uvx</span> <span className="text-white font-semibold">schemaslim</span> <span className="text-white font-semibold">wrap</span>
                  </div>

                  {wrapStep >= 1 && (
                    <div className="text-zinc-300">
                      <span className="text-zinc-600">›</span> Discovering client configurations on host...
                      <div className="mt-1 pl-3 space-y-1 text-xs text-zinc-400">
                        <div className="text-zinc-300 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Claude Desktop: <span className="text-zinc-400 font-mono">~/.config/Claude/claude_desktop_config.json</span> (<span className="text-emerald-400 font-mono font-medium">4 servers</span>)
                        </div>
                        <div className="text-zinc-300 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Google Antigravity: <span className="text-zinc-400 font-mono">~/.gemini/antigravity-ide/mcp_config.json</span> (<span className="text-emerald-400 font-mono font-medium">6 servers</span>)
                        </div>
                        <div className="text-zinc-300 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Cursor MCP: <span className="text-zinc-400 font-mono">~/.cursor/mcp.json</span> (<span className="text-emerald-400 font-mono font-medium">2 servers</span>)
                        </div>
                      </div>
                    </div>
                  )}

                  {wrapStep >= 2 && (
                    <div className="text-zinc-300">
                      <span className="text-zinc-600">›</span> Backups created: <span className="text-zinc-400 font-mono">claude_desktop_config.json.schemaslim.bak</span>
                    </div>
                  )}

                  {wrapStep >= 3 && (
                    <div className="text-zinc-300">
                      <span className="text-zinc-600">›</span> Harvesting schemas with FastEmbed (<span className="text-amber-300/90 font-mono">BGE-small-en-v1.5</span>)...
                      <div className="pl-3 text-xs text-zinc-400 font-mono">
                        Indexed <span className="text-white font-semibold">38 tools</span> into <span className="text-zinc-400">~/.schemaslim/index.db</span> (<span className="text-zinc-400">sqlite-vec</span> + <span className="text-zinc-400">FTS5</span>) in <span className="text-emerald-400 font-medium">412ms</span>
                      </div>
                    </div>
                  )}

                  {wrapStep >= 4 && (
                    <div className="pt-2 border-t border-zinc-900">
                      <div className="text-white font-bold mb-1">
                        ◆ SchemaSlim Virtualization ──────────────────────────────
                      </div>
                      <div className="pl-2 space-y-0.5 text-xs text-zinc-400 font-mono">
                        <div><span className="text-zinc-600">client  ›</span> <span className="text-zinc-200">Claude Desktop</span> (auto-detected)</div>
                        <div><span className="text-zinc-600">target  ›</span> <span className="text-zinc-400">claude_desktop_config.json</span></div>
                        <div><span className="text-zinc-600">mcp     ›</span> <span className="text-white font-medium">4 servers migrated</span> (<span className="text-zinc-300">git_server</span>, <span className="text-zinc-300">db_server</span>, <span className="text-zinc-300">fs_server</span>, <span className="text-zinc-300">api_server</span>)</div>
                        <div><span className="text-zinc-600">security›</span> <span className="text-emerald-400 font-mono">CWE-200 safe</span> • <span className="text-emerald-400 font-mono">CWD Hijack Blocked</span> (<span className="text-rose-400 font-mono">CWE-426</span>)</div>
                        <div><span className="text-zinc-600">status  ›</span> <span className="text-emerald-400 font-semibold">Virtualization Active (<span className="text-white font-semibold">schemaslim</span> <span className="text-white font-semibold">serve</span> <span className="text-zinc-400">--tui</span>)</span></div>
                      </div>
                      <div className="mt-2 text-emerald-400 text-xs font-semibold flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Virtualization complete. Restart client to reclaim <span className="text-white font-bold">85%+ prompt tokens</span> (<span className="text-emerald-300">104 passed</span>).
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: SEARCH */}
              {activeTab === 'search' && (
                <div className="space-y-3">
                  <div className="text-zinc-500 text-[11px] pb-1 border-b border-zinc-900 flex justify-between items-center">
                    <span>AGENT JSON-RPC RETRIEVAL</span>
                    <span className="text-emerald-400 text-xs font-mono font-medium">Hybrid Latency: 51.4ms</span>
                  </div>

                  <div className="text-zinc-400 font-mono">
                    <span className="text-zinc-100 font-semibold">agent</span>:<span className="text-zinc-400">~</span>$ <span className="text-white font-semibold">schemaslim_search</span>(<span className="text-amber-300/90 font-mono">query</span>=<span className="text-emerald-300">"query postgres database and fetch user records"</span>, <span className="text-amber-300/90 font-mono">limit</span>=<span className="text-emerald-400 font-semibold">2</span>)
                  </div>

                  <div className="bg-zinc-900/60 rounded-lg p-3 border border-zinc-850 text-xs font-mono">
                    <div className="text-zinc-500 mb-2">// JSON-RPC Payload: &#123;<span className="text-amber-300/90">"method"</span>: <span className="text-zinc-200">"tools/call"</span>, <span className="text-amber-300/90">"params"</span>: &#123;<span className="text-amber-300/90">"tool"</span>: <span className="text-emerald-300">"schemaslim_search"</span>&#125;&#125;</div>
                    <div className="space-y-2">
                      <div className="p-2.5 rounded bg-zinc-950 border border-zinc-800">
                        <div className="flex items-center justify-between">
                          <span className="text-white font-bold">#1 db_server__sql_query</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-emerald-400 font-mono border border-emerald-500/20">score: 0.892</span>
                        </div>
                        <p className="text-zinc-400 mt-1 text-xs font-sans">
                          Execute read-only SQL queries against Postgres/MySQL instances with parameterized inputs.
                        </p>
                      </div>

                      <div className="p-2.5 rounded bg-zinc-950 border border-zinc-800">
                        <div className="flex items-center justify-between">
                          <span className="text-white font-bold">#2 db_server__inspect_table_schema</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-emerald-400 font-mono border border-emerald-500/20">score: 0.741</span>
                        </div>
                        <p className="text-zinc-400 mt-1 text-xs font-sans">
                          Inspect columns, data types, primary keys, and foreign keys for target table.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="text-xs text-zinc-400 flex items-center justify-between pt-1">
                    <span>Prompt tokens injected: <span className="text-white font-bold">294 tokens</span> (vs 3,840 static)</span>
                    <span className="text-emerald-400 font-semibold">+3,546 tokens saved on turn (<span className="text-emerald-300">51.4ms</span>)</span>
                  </div>
                </div>
              )}

              {/* TAB 3: STATS */}
              {activeTab === 'stats' && (
                <div className="space-y-2 text-xs sm:text-sm font-mono leading-relaxed">
                  <div className="text-zinc-500 text-[11px] pb-1 border-b border-zinc-900">
                    CLI COMMAND: schemaslim stats (MONOCHROME RICH TUI)
                  </div>
                  <div className="text-zinc-400">
                    <span className="text-zinc-100 font-semibold">devbox</span>:<span className="text-zinc-400">~</span>$ <span className="text-white font-semibold">schemaslim</span> <span className="text-white font-semibold">stats</span> <span className="text-zinc-400">--tui</span>
                  </div>
                  <div className="text-white font-bold pt-1">
                    ◆ Workspace MCP Status ──────────────────────────────────────────
                  </div>
                  <div className="pl-3 space-y-1 text-zinc-300 font-mono">
                    <div>
                      <span className="text-zinc-500 inline-block w-20">mcp</span>
                      <span className="text-zinc-600 mr-2">›</span>
                      <span className="text-white font-medium">4 active</span> (<span className="text-zinc-400">git_server</span>, <span className="text-zinc-400">db_server</span>, <span className="text-zinc-400">fs_server</span>, <span className="text-zinc-400">api_server</span>) • <span className="text-emerald-400">0 errors</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 inline-block w-20">tools</span>
                      <span className="text-zinc-600 mr-2">›</span>
                      <span className="text-white font-medium">20</span> (Indexed Tools in DB) • <span className="text-emerald-400 font-bold">~74.0% context compression</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 inline-block w-20">security</span>
                      <span className="text-zinc-600 mr-2">›</span>
                      <span className="text-emerald-400 font-semibold">Protected</span> • <span className="text-rose-400 font-medium">CWD Blocked</span> (<span className="text-rose-300 font-mono">CWE-426</span>) • <span className="text-emerald-400 font-medium">104 passed</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 inline-block w-20">db</span>
                      <span className="text-zinc-600 mr-2">›</span>
                      <span className="text-zinc-400 font-mono">sqlite-vec (384d BGE-small) • ~/.schemaslim/index.db</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 inline-block w-20">catalog</span>
                      <span className="text-zinc-600 mr-2">›</span>
                      <span className="text-zinc-300">1,925 raw tokens</span> › <span className="text-emerald-400 font-semibold">~502 virtualized</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 inline-block w-20">savings</span>
                      <span className="text-zinc-600 mr-2">›</span>
                      <span className="text-emerald-400 font-bold">+1,423 tokens (85% prompt savings per turn)</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 inline-block w-20">session</span>
                      <span className="text-zinc-600 mr-2">›</span>
                      <span className="text-emerald-400">+28,460 tok / 20 turns</span> • <span className="text-emerald-400 font-semibold">+142,300 tok / 100 turns</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Terminal Status Bar */}
            <div className="px-3 sm:px-4 py-2 bg-zinc-900/70 border-t border-zinc-800 flex flex-wrap items-center justify-between text-[11px] font-mono text-zinc-500">
              <div className="flex items-center gap-2">
                <span>sqlite-vec 384d</span>
                <span>•</span>
                <span>BM25 FTS5</span>
                <span>•</span>
                <span>FastEmbed ONNX</span>
              </div>
              <div className="text-emerald-400/90 flex items-center gap-1">
                os.environ dropped
              </div>
            </div>
          </div>
        </div>
      </InView>
    </div>
  </section>
);
};
