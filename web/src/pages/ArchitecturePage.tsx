import React from 'react';
import { Network } from 'lucide-react';
import { Architecture } from '../components/Architecture';
import { InView } from '../components/ui/in-view';

export const ArchitecturePage: React.FC = () => {
  return (
    <div className="bg-transparent min-h-screen relative py-16 md:py-24 flex-1">
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="max-w-3xl mb-12">
          <InView transition={{ delay: 0.05 }}>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 text-xs font-mono mb-3">
              <Network className="w-3.5 h-3.5 text-zinc-300" />
              Technical Specification &amp; Internals
            </div>
          </InView>
          <InView transition={{ delay: 0.1 }}>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-3">
              JIT Virtualization Pipeline
            </h1>
          </InView>
          <InView transition={{ delay: 0.15 }}>
            <p className="text-sm text-zinc-400 leading-relaxed font-normal">
              Deep dive into SchemaSlim's local reverse-proxy architecture: replacing static tool schema loads with sub-60ms hybrid vector retrieval, lazy subprocess spawning, and host environment isolation.
            </p>
          </InView>
        </div>

        {/* Spec Sheet Component */}
        <InView transition={{ delay: 0.2 }}>
          <Architecture />
        </InView>
      </div>
    </div>
  );
};
