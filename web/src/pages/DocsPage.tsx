import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { BookOpen, ShieldCheck, Zap, Cpu, Download } from 'lucide-react';
import { ClientConfigurator } from '../components/docs/ClientConfigurator';
import { CommandReference } from '../components/docs/CommandReference';
import { PackageManagerSwitcher } from '../components/docs/PackageManagerSwitcher';
import { InView } from '../components/ui/in-view';

export const DocsPage: React.FC = () => {
  const location = useLocation();

  // Robust smooth scroll to #install on mount or hash change, accounting for AnimatePresence transition
  useEffect(() => {
    if (window.location.hash === '#install' || location.hash === '#install') {
      let attempts = 0;
      const maxAttempts = 30; // Polling limit (~500ms)
      let frameId: number;

      const checkAndScroll = () => {
        attempts++;
        const el = document.getElementById('install');
        if (el) {
          el.scrollIntoView({ behavior: 'smooth' });
        } else if (attempts < maxAttempts) {
          frameId = requestAnimationFrame(checkAndScroll);
        }
      };

      // Delay to ensure AnimatePresence mode="wait" (200ms) has mounted the new page DOM
      const timer = setTimeout(() => {
        frameId = requestAnimationFrame(checkAndScroll);
      }, 190);

      return () => {
        clearTimeout(timer);
        cancelAnimationFrame(frameId);
      };
    }
  }, [location.hash, location.pathname]);

  return (
    <div className="bg-transparent min-h-screen relative py-16 md:py-24 flex-1">
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-20 md:space-y-24">
        
        {/* ========================================================================= */}
        {/* LEVEL 1: Overview & Core Concepts                                         */}
        {/* ========================================================================= */}
        <div className="space-y-12">
          <div className="max-w-3xl">
            <InView transition={{ delay: 0.05 }}>
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 text-xs font-mono mb-4">
                <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
                Technical Reference &amp; Agent Matrix
              </div>
            </InView>

            <InView transition={{ delay: 0.1 }}>
              <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight mb-4 leading-[1.15]">
                Universal MCP Virtualization
              </h1>
            </InView>

            <InView transition={{ delay: 0.15 }}>
              <p className="text-sm sm:text-base text-zinc-400 leading-relaxed font-normal">
                SchemaSlim acts as an agent-agnostic, transparent <span className="text-zinc-200 font-medium">stdio reverse-proxy</span> interposed between any LLM client runtime and underlying Model Context Protocol (MCP) servers. By virtualizing tool discovery into on-demand retrieval, agents maintain razor-sharp prompt attention while retaining access to unlimited server capabilities.
              </p>
            </InView>
          </div>

          {/* 3 Open Architectural Columns (Clean Typography, Anti-Card Soup) */}
          <InView transition={{ delay: 0.2 }}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-8 border-t border-zinc-800/80 text-left">
              {/* Column 1 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-white font-mono text-sm font-bold">
                  <Zap className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <h4>Zero-Token Bootstrap</h4>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed font-normal">
                  Dozens of static tool schemas are never dumped into initial prompt tokens. Agents receive exactly 2 lean meta-tools (<code className="text-zinc-300 font-mono">schemaslim_search</code> and <code className="text-zinc-300 font-mono">schemaslim_call</code>), saving up to 85–92% prompt tokens from turn one.
                </p>
              </div>

              {/* Column 2 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-white font-mono text-sm font-bold">
                  <Cpu className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <h4>Sub-60ms Hybrid Vector Retrieval</h4>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed font-normal">
                  100% offline FastEmbed (ONNX BGE-small-en-v1.5 384d) dense vectors combined with SQLite FTS5 BM25 lexical ranking. Reciprocal Rank Fusion (RRF) evaluates tool relevance without external cloud API calls or network latency.
                </p>
              </div>

              {/* Column 3 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-white font-mono text-sm font-bold">
                  <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <h4>Process &amp; Secret Isolation (CWE-200)</h4>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed font-normal">
                  Prevents CWE-200 environment secret leakage by stripping ambient host variables (<code className="text-zinc-300 font-mono">OPENAI_API_KEY</code>, cloud credentials) before spawning untrusted child servers. Backed by 104 automated pytest regressions.
                </p>
              </div>
            </div>
          </InView>
        </div>

        {/* ========================================================================= */}
        {/* LEVEL 2: Full CLI Command & Flags Reference                               */}
        {/* ========================================================================= */}
        <InView transition={{ delay: 0.25 }}>
          <div className="pt-8 border-t border-zinc-800/80">
            <CommandReference />
          </div>
        </InView>

        {/* ========================================================================= */}
        {/* LEVEL 3 & 4: Installation & Interactive Client Integration Matrix          */}
        {/* ========================================================================= */}
        <section id="install" className="pt-16 scroll-mt-20 border-t border-zinc-800/80 space-y-12">
          <InView transition={{ delay: 0.1 }}>
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 text-xs font-mono mb-3">
                <Download className="w-3.5 h-3.5 text-emerald-400" />
                Quickstart &amp; Client Setup
              </div>
              <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight mb-2">
                Install &amp; Client Integration
              </h2>
              <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed font-normal">
                Zero external databases. 100% local ONNX &amp; SQLite-vec runtime.
              </p>
            </div>
          </InView>

          {/* Level 3: Compact Package Manager Switcher */}
          <InView transition={{ delay: 0.15 }}>
            <div className="max-w-3xl">
              <PackageManagerSwitcher />
            </div>
          </InView>

          {/* Level 4: Interactive Client Configurator Matrix (directly below package managers) */}
          <InView transition={{ delay: 0.2 }}>
            <ClientConfigurator />
          </InView>
        </section>

      </div>
    </div>
  );
};
