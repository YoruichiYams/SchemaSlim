import React from 'react';
import { motion } from 'motion/react';
import { Bot, Cpu, Database, Terminal, ArrowRight, ArrowDown } from 'lucide-react';

interface ArchitectureFlowProps {
  selectedStep: number;
  onSelectStep: (stepId: number) => void;
}

interface FlowNode {
  id: number;
  stepTarget: number;
  title: string;
  subtitle: string;
  protocol: string;
  icon: React.ComponentType<{ className?: string }>;
  associatedSteps: number[];
}

export const ArchitectureFlow: React.FC<ArchitectureFlowProps> = ({
  selectedStep,
  onSelectStep,
}) => {
  const nodes: FlowNode[] = [
    {
      id: 1,
      stepTarget: 1,
      title: 'LLM Client',
      subtitle: 'Claude / Antigravity / Cursor',
      protocol: 'stdio JSON-RPC',
      icon: Bot,
      associatedSteps: [1, 2],
    },
    {
      id: 2,
      stepTarget: 2,
      title: 'SchemaSlim Virtualizer',
      subtitle: 'Local JIT Stdio Reverse-Proxy',
      protocol: 'meta-tools: ~450 tok',
      icon: Cpu,
      associatedSteps: [2, 4],
    },
    {
      id: 3,
      stepTarget: 3,
      title: 'Local Hybrid Search',
      subtitle: 'sqlite-vec + SQLite FTS5',
      protocol: '<60ms dense+lexical',
      icon: Database,
      associatedSteps: [3],
    },
    {
      id: 4,
      stepTarget: 4,
      title: 'Isolated MCP Child',
      subtitle: 'Sandboxed Subprocess Pool',
      protocol: 'os.environ stripped',
      icon: Terminal,
      associatedSteps: [4, 5],
    },
  ];

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/70 p-4 sm:p-6 backdrop-blur-md">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-mono uppercase tracking-wider text-zinc-400">
            Interactive Dataflow Pipeline
          </span>
        </div>
        <span className="text-[11px] font-mono text-zinc-500">
          Click any node to inspect internals
        </span>
      </div>

      {/* Nodes Container (Responsive: vertical stack on mobile with ArrowDown, 4-col grid on desktop) */}
      <div className="flex flex-col md:grid md:grid-cols-4 gap-2 md:gap-4 items-stretch relative">
        {nodes.map((node, idx) => {
          const isActive = node.associatedSteps.includes(selectedStep);
          const isFlowActive =
            (idx === 0 && (selectedStep === 1 || selectedStep === 2)) ||
            (idx === 1 && (selectedStep === 2 || selectedStep === 3)) ||
            (idx === 2 && (selectedStep === 3 || selectedStep === 4 || selectedStep === 5));

          return (
            <React.Fragment key={node.id}>
              {/* Node Card */}
              <motion.button
                onClick={() => onSelectStep(node.stepTarget)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`text-left p-4 rounded-xl border transition-all duration-300 relative overflow-hidden cursor-pointer flex flex-col justify-between min-h-[110px] sm:min-h-[130px] ${
                  isActive
                    ? 'border-emerald-500/70 bg-zinc-900/90 shadow-[0_0_20px_rgba(16,185,129,0.2)]'
                    : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700 hover:bg-zinc-900/60'
                }`}
              >
                {/* Active Indicator Top Bar */}
                {isActive && (
                  <motion.div
                    layoutId="active-flow-bar"
                    className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-emerald-500 via-emerald-400 to-cyan-400"
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}

                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                        isActive
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          : 'bg-zinc-800/80 text-zinc-400 border border-zinc-700/50'
                      }`}
                    >
                      <node.icon className="w-4 h-4" />
                    </div>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                        isActive
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-semibold'
                          : 'bg-zinc-850 border-zinc-800 text-zinc-500'
                      }`}
                    >
                      {node.protocol}
                    </span>
                  </div>

                  <h4
                    className={`text-xs sm:text-sm font-semibold tracking-tight transition-colors ${
                      isActive ? 'text-white' : 'text-zinc-300'
                    }`}
                  >
                    {node.title}
                  </h4>
                  <p className="text-[11px] text-zinc-400 mt-1 leading-snug font-normal">
                    {node.subtitle}
                  </p>
                </div>

                <div className="mt-4 pt-2 border-t border-zinc-850 flex items-center justify-between text-[10px] font-mono text-zinc-500">
                  <span>Step 0{node.stepTarget}</span>
                  {isActive && (
                    <span className="text-emerald-400 flex items-center gap-1 font-medium">
                      Active
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    </span>
                  )}
                </div>
              </motion.button>

              {/* Mobile Downward Connector between steps */}
              {idx < nodes.length - 1 && (
                <div className="md:hidden flex items-center justify-center py-1">
                  <div className="flex flex-col items-center gap-0.5">
                    <div className={`w-[1px] h-3 ${isFlowActive ? 'bg-emerald-500' : 'bg-zinc-800'}`} />
                    <ArrowDown
                      className={`w-3.5 h-3.5 transition-colors ${
                        isFlowActive ? 'text-emerald-400 animate-bounce' : 'text-zinc-600'
                      }`}
                    />
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* SVG Connecting Pulse Lines for Desktop */}
      <div className="hidden md:grid grid-cols-3 gap-4 mt-3 px-8">
        {[1, 2, 3].map((connId) => {
          const isFlowActive =
            (connId === 1 && (selectedStep === 1 || selectedStep === 2)) ||
            (connId === 2 && (selectedStep === 2 || selectedStep === 3)) ||
            (connId === 3 && (selectedStep === 3 || selectedStep === 4 || selectedStep === 5));

          return (
            <div key={connId} className="flex items-center justify-center gap-2">
              <svg className="w-full h-3 overflow-visible" preserveAspectRatio="none">
                <line
                  x1="0%"
                  y1="50%"
                  x2="100%"
                  y2="50%"
                  stroke={isFlowActive ? '#10b981' : '#27272a'}
                  strokeWidth={isFlowActive ? '2' : '1.5'}
                  strokeDasharray="6 4"
                  className={isFlowActive ? 'animate-[dash_0.8s_linear_infinite]' : ''}
                />
              </svg>
              <ArrowRight
                className={`w-3.5 h-3.5 flex-shrink-0 transition-colors ${
                  isFlowActive ? 'text-emerald-400' : 'text-zinc-700'
                }`}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};
