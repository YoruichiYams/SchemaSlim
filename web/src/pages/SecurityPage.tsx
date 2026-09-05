import React from 'react';
import { ShieldAlert } from 'lucide-react';
import { SecurityMatrix } from '../components/SecurityMatrix';
import { InView } from '../components/ui/in-view';

export const SecurityPage: React.FC = () => {
  return (
    <div className="bg-transparent min-h-screen relative py-16 md:py-24 flex-1">
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="max-w-3xl mb-12">
          <InView transition={{ delay: 0.05 }}>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 text-xs font-mono mb-3">
              <ShieldAlert className="w-3.5 h-3.5 text-zinc-300" />
              Security Advisory
            </div>
          </InView>
          <InView transition={{ delay: 0.1 }}>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-3">
              Hardened Architecture &amp; Closed Threat Vectors
            </h1>
          </InView>
          <InView transition={{ delay: 0.15 }}>
            <p className="text-sm text-zinc-400 leading-relaxed font-normal">
              MCP child servers run arbitrary code on developer machines. SchemaSlim enforces zero-trust process execution through 6 validated hardening vectors backed by 104 regression tests.
            </p>
          </InView>
        </div>

        {/* Security Matrix Component */}
        <InView transition={{ delay: 0.2 }}>
          <SecurityMatrix />
        </InView>
      </div>
    </div>
  );
};
