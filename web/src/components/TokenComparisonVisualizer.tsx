import React, { useState } from 'react';
import { motion } from 'motion/react';
import { DollarSign } from 'lucide-react';

type ToolScale = 10 | 50 | 100;

interface ScaleData {
  tools: ToolScale;
  label: string;
  directTokens: number;
  schemaslimTokens: number;
  schemaslimWidthPct: number;
  reductionPct: number;
  sessionSavingsTokens: number;
  sessionSavingsCost: string;
}

export const TokenComparisonVisualizer: React.FC = () => {
  const [activeScale, setActiveScale] = useState<ToolScale>(100);

  const scalesData: Record<ToolScale, ScaleData> = {
    10: {
      tools: 10,
      label: '10 tools (Small Devbox)',
      directTokens: 980,
      schemaslimTokens: 520,
      schemaslimWidthPct: 53.1,
      reductionPct: 46.9,
      sessionSavingsTokens: 9200,
      sessionSavingsCost: '$0.028',
    },
    50: {
      tools: 50,
      label: '50 tools (Mid-tier Setup)',
      directTokens: 4910,
      schemaslimTokens: 645,
      schemaslimWidthPct: 13.1,
      reductionPct: 86.9,
      sessionSavingsTokens: 85300,
      sessionSavingsCost: '$0.256',
    },
    100: {
      tools: 100,
      label: '100 tools (Enterprise MCP Multi-server)',
      directTokens: 9820,
      schemaslimTokens: 738,
      schemaslimWidthPct: 7.5,
      reductionPct: 92.5,
      sessionSavingsTokens: 181640,
      sessionSavingsCost: '$0.545',
    },
  };

  const current = scalesData[activeScale];

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-5 sm:p-6 mb-12 shadow-xl backdrop-blur-md">
      {/* Header with Catalog Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-zinc-850">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono uppercase tracking-wider text-zinc-400">
              Comparative Context Overhead Scale
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700">
              Live Scale
            </span>
          </div>
          <h3 className="text-sm sm:text-base font-semibold text-white">
            Direct Static MCP Ingestion vs. SchemaSlim JIT Proxy
          </h3>
        </div>

        {/* Catalog Selector Tabs */}
        <div className="flex items-center gap-1 bg-zinc-900/90 p-1 rounded-lg border border-zinc-850 self-start sm:self-auto overflow-x-auto no-scrollbar max-w-full">
          {([10, 50, 100] as const).map((scale) => {
            const isActive = activeScale === scale;
            return (
              <button
                key={scale}
                onClick={() => setActiveScale(scale)}
                className="relative px-3 py-2 min-h-[40px] text-xs font-mono transition-colors cursor-pointer select-none rounded-md shrink-0 flex items-center justify-center"
              >
                {isActive && (
                  <motion.div
                    layoutId="benchmark-tier-tab"
                    className="absolute inset-0 bg-zinc-800 rounded-md border border-zinc-700 shadow-sm"
                    transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                  />
                )}
                <span
                  className={`relative z-10 transition-colors ${
                    isActive ? 'text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {scale} tools
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Visual Bar Comparison Area */}
      <div className="py-6 space-y-6">
        {/* Bar 1: Direct Static Loading */}
        <div className="space-y-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rose-500/80 shrink-0" />
              <span className="text-zinc-300 font-medium">Direct MCP (Static Schema Injection)</span>
            </div>
            <span className="text-rose-400 font-bold">
              {current.directTokens.toLocaleString()} tokens / turn
            </span>
          </div>

          <div className="h-9 w-full bg-zinc-900/60 rounded-lg p-1 border border-zinc-850 relative overflow-hidden">
            <motion.div
              className="h-full rounded-md bg-gradient-to-r from-rose-500/30 to-amber-500/30 border border-rose-500/50 flex items-center justify-between px-3 text-xs font-mono text-rose-300"
              initial={{ width: '0%' }}
              animate={{ width: '100%' }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
            >
              <span className="truncate">Static Prompts Payload (100% Baseline)</span>
              <span className="font-bold whitespace-nowrap ml-2">{current.directTokens.toLocaleString()} tok</span>
            </motion.div>
          </div>
        </div>

        {/* Bar 2: SchemaSlim Virtualization */}
        <div className="space-y-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
              <span className="text-zinc-200 font-semibold">SchemaSlim Virtualized (2 Meta-Tools + JIT Top-3)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-emerald-400 font-bold">
                {current.schemaslimTokens.toLocaleString()} tokens / turn
              </span>
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[11px] font-bold animate-pulse">
                {current.reductionPct}% reduction
              </span>
            </div>
          </div>

          <div className="h-9 w-full bg-zinc-900/60 rounded-lg p-1 border border-zinc-850 relative overflow-hidden">
            <motion.div
              className="h-full rounded-md bg-gradient-to-r from-emerald-500/40 to-teal-500/40 border border-emerald-500/70 flex items-center justify-between px-3 text-xs font-mono text-emerald-300 relative overflow-hidden"
              initial={{ width: '15%' }}
              animate={{ width: `${Math.max(current.schemaslimWidthPct, 12)}%` }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
            >
              <span className="font-bold whitespace-nowrap">{current.schemaslimTokens} tok</span>
              <span className="text-[11px] text-emerald-400/80 font-medium whitespace-nowrap ml-2 hidden sm:inline">
                ({current.schemaslimWidthPct.toFixed(1)}% of direct)
              </span>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Difference & ROI Highlights */}
      <div className="pt-4 border-t border-zinc-850 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
        <div className="p-3 rounded-lg bg-zinc-900/40 border border-zinc-850">
          <div className="text-zinc-500 text-[11px] mb-1">SAVINGS PER TURN</div>
          <div className="text-emerald-400 font-bold text-sm">
            +{(current.directTokens - current.schemaslimTokens).toLocaleString()} tokens
          </div>
          <div className="text-zinc-500 text-[10px] mt-0.5">Prompt space preserved</div>
        </div>

        <div className="p-3 rounded-lg bg-zinc-900/40 border border-zinc-850">
          <div className="text-zinc-500 text-[11px] mb-1">SESSION SAVINGS (20 TURNS)</div>
          <div className="text-emerald-400 font-bold text-sm">
            +{current.sessionSavingsTokens.toLocaleString()} tokens
          </div>
          <div className="text-zinc-500 text-[10px] mt-0.5">Reduced context degradation</div>
        </div>

        <div className="p-3 rounded-lg bg-zinc-900/40 border border-zinc-850">
          <div className="text-zinc-500 text-[11px] mb-1">SESSION COST SAVED (SONNET)</div>
          <div className="text-white font-bold text-sm flex items-center gap-1">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            {current.sessionSavingsCost}
            <span className="text-zinc-500 text-[10px] font-normal">/ session</span>
          </div>
          <div className="text-zinc-500 text-[10px] mt-0.5">Based on $3.00/1M input tok</div>
        </div>
      </div>
    </div>
  );
};
