import React from 'react';
import { BarChart3 } from 'lucide-react';
import { TokenComparisonVisualizer } from '../components/TokenComparisonVisualizer';
import { BenchmarkGrid } from '../components/BenchmarkGrid';
import { InView } from '../components/ui/in-view';

export const BenchmarksPage: React.FC = () => {
  return (
    <div className="bg-transparent min-h-screen relative py-16 md:py-24 flex-1">
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="max-w-3xl mb-12">
          <InView transition={{ delay: 0.05 }}>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 text-xs font-mono mb-3">
              <BarChart3 className="w-3.5 h-3.5 text-zinc-300" />
              Empirical Test Suite
            </div>
          </InView>
          <InView transition={{ delay: 0.1 }}>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-3">
              Context Compression &amp; Latency Benchmarks
            </h1>
          </InView>
          <InView transition={{ delay: 0.15 }}>
            <p className="text-sm text-zinc-400 leading-relaxed font-normal">
              Measured against realistic multi-server MCP configurations (Git, SQLite, Filesystem, REST API). Benchmarks evaluated across 5 consecutive iterations via <code className="text-white font-mono">schemaslim benchmark</code>.
            </p>
          </InView>
        </div>

        {/* 1. Animated Token Comparison Visualizer */}
        <InView transition={{ delay: 0.2 }}>
          <TokenComparisonVisualizer />
        </InView>

        {/* 2. Empirical Benchmark Grid Component */}
        <InView transition={{ delay: 0.25 }}>
          <BenchmarkGrid />
        </InView>
      </div>
    </div>
  );
};
