import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Calculator, DollarSign, Layers, Wrench, AlertTriangle, Sparkles } from 'lucide-react';
import { InView } from './ui/in-view';

export const ContextSimulator: React.FC = () => {
  const [serverCount, setServerCount] = useState<number>(8);
  const [toolsPerServer, setToolsPerServer] = useState<number>(8);
  const avgTokensPerTool = 96; // Empirical benchmark (~96.25 tokens/tool)
  const [sessionTurns, setSessionTurns] = useState<number>(20);
  const [costPerMillion, setCostPerMillion] = useState<number>(3.0); // $3.00 per 1M tokens

  // Calculations
  const totalTools = serverCount * toolsPerServer;
  const baselineCatalogTokens = totalTools * avgTokensPerTool;
  
  // SchemaSlim footprint: 2 meta-tools (~450 tokens) + top-3 retrieved tools on demand
  const topKRetrieved = Math.min(3, totalTools);
  const schemaslimActualTokens = 450 + (topKRetrieved * avgTokensPerTool);

  const tokensSavedPerTurn = Math.max(0, baselineCatalogTokens - schemaslimActualTokens);
  const compressionPct = baselineCatalogTokens > 0 
    ? Math.min(96, Math.max(0, (tokensSavedPerTurn / baselineCatalogTokens) * 100))
    : 0;

  // Financial impact
  const sessionTokensSaved = tokensSavedPerTurn * sessionTurns;
  const sessionDollarsSaved = (sessionTokensSaved / 1_000_000) * costPerMillion;
  const monthlyWorkdaySavings = sessionDollarsSaved * 22 * 5;

  return (
    <section id="simulator" className="py-16 md:py-24 border-t border-zinc-800/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="max-w-3xl mb-12">
          <InView transition={{ delay: 0.05 }}>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 text-xs font-mono mb-3">
              <Calculator className="w-3.5 h-3.5 text-zinc-300" />
              Empirical Context Simulator
            </div>
          </InView>
          <InView transition={{ delay: 0.1 }}>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight mb-3">
              Calculate Real-Time Context Compression &amp; API Savings
            </h2>
          </InView>
          <InView transition={{ delay: 0.15 }}>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Adjust your environment size to model the prompt footprint difference between direct static tool loading and SchemaSlim JIT virtualization.
            </p>
          </InView>
        </div>

        {/* Interactive Layout (Anti-Card Soup: 1 interactive controls widget, metrics exposed on canvas) */}
        <InView transition={{ delay: 0.2 }}>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Controls Box (Interactive Widget) */}
          <div className="lg:col-span-5 widget-panel rounded-xl p-5 sm:p-6 border border-zinc-800 space-y-6">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <span className="text-sm font-semibold text-white">Environment Configuration</span>
              <span className="text-xs font-mono text-zinc-400">
                {totalTools} active tools
              </span>
            </div>

            {/* Slider 1: MCP Servers */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs sm:text-sm">
                <label className="text-zinc-300 font-medium flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-zinc-400" />
                  Active MCP Servers
                </label>
                <span className="font-mono text-white font-semibold bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800 text-xs">
                  {serverCount} {serverCount === 1 ? 'server' : 'servers'}
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={50}
                value={serverCount}
                onChange={(e) => setServerCount(Number(e.target.value))}
                className="w-full h-6 bg-transparent cursor-pointer accent-white focus:outline-none appearance-none [&::-webkit-slider-runnable-track]:h-2 [&::-webkit-slider-runnable-track]:bg-zinc-800 [&::-webkit-slider-runnable-track]:rounded-lg [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:-mt-1.5 [&::-webkit-slider-thumb]:shadow-md [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-none"
              />
              <div className="flex justify-between text-[10px] text-zinc-500 font-mono">
                <span>1</span>
                <span>25</span>
                <span>50 servers</span>
              </div>
            </div>

            {/* Slider 2: Tools Per Server */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs sm:text-sm">
                <label className="text-zinc-300 font-medium flex items-center gap-1.5">
                  <Wrench className="w-3.5 h-3.5 text-zinc-400" />
                  Average Tools per Server
                </label>
                <span className="font-mono text-white font-semibold bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800 text-xs">
                  {toolsPerServer} tools/srv
                </span>
              </div>
              <input
                type="range"
                min={3}
                max={20}
                value={toolsPerServer}
                onChange={(e) => setToolsPerServer(Number(e.target.value))}
                className="w-full h-6 bg-transparent cursor-pointer accent-white focus:outline-none appearance-none [&::-webkit-slider-runnable-track]:h-2 [&::-webkit-slider-runnable-track]:bg-zinc-800 [&::-webkit-slider-runnable-track]:rounded-lg [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:-mt-1.5 [&::-webkit-slider-thumb]:shadow-md [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-none"
              />
              <div className="flex justify-between text-[10px] text-zinc-500 font-mono">
                <span>3</span>
                <span>10</span>
                <span>20 tools</span>
              </div>
            </div>

            {/* Slider 3: Conversation Turns */}
            <div className="space-y-2 pt-3 border-t border-zinc-850">
              <div className="flex justify-between text-xs sm:text-sm">
                <label className="text-zinc-300 font-medium">
                  Conversation Turns
                </label>
                <span className="font-mono text-zinc-300 font-semibold bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800 text-xs">
                  {sessionTurns} turns
                </span>
              </div>
              <input
                type="range"
                min={5}
                max={100}
                step={5}
                value={sessionTurns}
                onChange={(e) => setSessionTurns(Number(e.target.value))}
                className="w-full h-6 bg-transparent cursor-pointer accent-white focus:outline-none appearance-none [&::-webkit-slider-runnable-track]:h-2 [&::-webkit-slider-runnable-track]:bg-zinc-800 [&::-webkit-slider-runnable-track]:rounded-lg [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:-mt-1.5 [&::-webkit-slider-thumb]:shadow-md [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-none"
              />
            </div>

            {/* Model Pricing Tier */}
            <div className="space-y-1.5 pt-3 border-t border-zinc-850">
              <label className="text-[11px] text-zinc-400 block font-medium">
                Model Pricing Tier (Input / 1M tokens)
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5 p-1 bg-zinc-900/60 rounded-xl border border-zinc-800/80 text-xs font-mono">
                {[
                  { price: 1.5, label: '$1.50 (Flash)' },
                  { price: 3.0, label: '$3.00 (Sonnet)' },
                  { price: 15.0, label: '$15.00 (Opus)' },
                ].map((tier) => {
                  const isActive = costPerMillion === tier.price;
                  return (
                    <button
                      key={tier.price}
                      onClick={() => setCostPerMillion(tier.price)}
                      className="relative px-2.5 py-2.5 rounded-lg text-center transition-colors cursor-pointer select-none min-h-[40px] flex items-center justify-center"
                    >
                      {isActive && (
                        <motion.div
                          layoutId="model-tier-tab"
                          className="absolute inset-0 bg-zinc-800 border border-zinc-700 rounded-lg shadow-sm"
                          transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                        />
                      )}
                      <span
                        className={`relative z-10 transition-colors ${
                          isActive ? 'text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'
                        }`}
                      >
                        {tier.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Results Display (Clean Canvas Presentation) */}
          <div className="lg:col-span-7 space-y-6">
            {/* Top Metric Header */}
            <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/40">
              <div className="flex flex-wrap items-baseline justify-between gap-4 mb-4">
                <div>
                  <div className="text-xs font-mono text-zinc-400 uppercase tracking-wider">
                    Context Compression Ratio
                  </div>
                  <div className="text-4xl sm:text-5xl font-extrabold text-white mt-1">
                    {compressionPct.toFixed(1)}%
                    <span className="text-sm font-normal text-emerald-400 font-mono ml-2">
                      reduction
                    </span>
                  </div>
                </div>

                <div className="text-right font-mono">
                  <div className="text-xs text-zinc-500 uppercase">Per-Turn Savings</div>
                  <div className="text-xl font-bold text-emerald-400">
                    +{tokensSavedPerTurn.toLocaleString()} tok
                  </div>
                </div>
              </div>

              {/* Linear Visual Comparison */}
              <div className="space-y-4 pt-3 border-t border-zinc-800/80">
                {/* Baseline Bar */}
                <div>
                  <div className="flex justify-between text-xs mb-1 text-zinc-400 font-mono">
                    <span className="flex items-center gap-1.5 text-zinc-300">
                      <AlertTriangle className="w-3.5 h-3.5 text-zinc-500" /> Direct MCP (Static)
                    </span>
                    <span className="text-zinc-300 font-bold">{baselineCatalogTokens.toLocaleString()} tokens</span>
                  </div>
                  <div className="w-full h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div className="h-full bg-zinc-500 rounded-full w-full" />
                  </div>
                </div>

                {/* SchemaSlim Bar */}
                <div>
                  <div className="flex justify-between text-xs mb-1 text-zinc-400 font-mono">
                    <span className="flex items-center gap-1.5 text-zinc-200 font-semibold">
                      <Sparkles className="w-3.5 h-3.5 text-emerald-400" /> SchemaSlim (JIT Proxy)
                    </span>
                    <span className="text-emerald-400 font-bold">~{schemaslimActualTokens.toLocaleString()} tokens</span>
                  </div>
                  <div className="w-full h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.max(4, Math.min(100, (schemaslimActualTokens / baselineCatalogTokens) * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Economic Impact Callouts */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-5 rounded-xl border border-zinc-850 bg-zinc-900/20">
                <div className="text-xs font-mono text-zinc-500 mb-1">
                  {sessionTurns}-TURN SESSION FOOTPRINT
                </div>
                <div className="text-2xl font-bold text-white font-mono">
                  +{sessionTokensSaved.toLocaleString()}
                  <span className="text-xs text-zinc-400 font-normal ml-1">tokens saved</span>
                </div>
                <div className="text-xs text-zinc-400 mt-1">
                  Reclaims context capacity for reasoning steps.
                </div>
              </div>

              <div className="p-5 rounded-xl border border-zinc-850 bg-zinc-900/20">
                <div className="text-xs font-mono text-zinc-500 mb-1 flex items-center gap-1">
                  <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
                  DEVELOPER MONTHLY ROI
                </div>
                <div className="text-2xl font-bold text-emerald-400 font-mono">
                  ${monthlyWorkdaySavings.toFixed(2)}
                  <span className="text-xs text-zinc-400 font-normal ml-1">/ dev / mo</span>
                </div>
                <div className="text-xs text-zinc-400 mt-1">
                  At 5 agent workflows/day with ${costPerMillion.toFixed(2)}/M input tokens.
                </div>
              </div>
            </div>
          </div>
        </div>
      </InView>
    </div>
  </section>
);
};
