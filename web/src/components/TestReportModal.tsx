import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ShieldCheck, X, CheckCircle2, Check, Terminal, FileCode } from 'lucide-react';

interface TestReportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface TestModule {
  filename: string;
  passedCount: number;
  duration: string;
  description: string;
}

export const TestReportModal: React.FC<TestReportModalProps> = ({ isOpen, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      // Calculate scrollbar width to prevent layout shift when locking body scroll
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
      document.body.style.overflow = 'hidden';
      if (scrollbarWidth > 0) {
        document.body.style.paddingRight = `${scrollbarWidth}px`;
      }
      window.addEventListener('keydown', handleKeyDown);
    } else {
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
    }

    return () => {
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  const testModules: TestModule[] = [
    {
      filename: 'tests/test_config.py',
      passedCount: 23,
      duration: '0.54s',
      description: 'Pydantic schema validation, idle_timeout parsing, keep_alive server config, Claude Desktop transport inference, UTF-8 BOM, CLI flags',
    },
    {
      filename: 'tests/test_cli.py',
      passedCount: 18,
      duration: '0.68s',
      description: 'CLI argument parsing, config validate/show/init, stats, search, benchmark, wrap/unwrap headless execution, and interactive menu primitives',
    },
    {
      filename: 'tests/test_server.py',
      passedCount: 16,
      duration: '0.94s',
      description: 'stdio JSON-RPC proxying, dynamic schemas, stdout stream purity, meta-tools dispatch',
    },
    {
      filename: 'tests/test_telemetry.py',
      passedCount: 14,
      duration: '0.62s',
      description: 'Rich stderr live telemetry formatting, token estimators, circular buffer thread-safety',
    },
    {
      filename: 'tests/test_security.py',
      passedCount: 22,
      duration: '0.72s',
      description: 'CWE-200 env sanitization, CWD hijacking defense, destructive call boundary, safety policies (permissive/ask/readonly), _confirmed stripping',
    },
    {
      filename: 'tests/test_pool.py',
      passedCount: 19,
      duration: '0.84s',
      description: 'MCPSessionPool lifecycle, idle process reaper, keep_alive stateful exemption, transparent on-demand revival, persistent connections, secret stripping',
    },
    {
      filename: 'tests/test_storage.py',
      passedCount: 9,
      duration: '0.81s',
      description: 'sqlite-vec 384d cosine embeddings, SQLite FTS5 BM25 lexical matches, idempotent hashing',
    },
    {
      filename: 'tests/test_migrator.py',
      passedCount: 9,
      duration: '0.42s',
      description: 'UTF-8 BOM decoding, atomic writes, automatic .schemaslim.bak rollbacks',
    },
    {
      filename: 'tests/test_e2e.py',
      passedCount: 5,
      duration: '0.48s',
      description: 'Full client-to-child proxy flow, synthetic benchmark runner, JSON/table report validation',
    },
    {
      filename: 'tests/test_harvester.py',
      passedCount: 4,
      duration: '0.35s',
      description: 'Subprocess stdio and SSE harvesting, parallel worker isolation, /sse fallback probing',
    },
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/75 backdrop-blur-sm cursor-pointer"
          />

          {/* Dialog Card */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-2xl bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden z-10 font-sans"
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-850 bg-zinc-900/40">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 id="modal-title" className="text-sm sm:text-base font-semibold text-white tracking-tight">
                      Pytest Suite Verification
                    </h3>
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                      v0.2.0
                    </span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  </div>
                  <p className="text-[11px] font-mono text-zinc-400">
                    Automated regression test runner execution
                  </p>
                </div>
              </div>

              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-400 hover:text-white hover:bg-zinc-800/80 transition-colors cursor-pointer"
                aria-label="Close dialog"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Summary Statistics Bar */}
            <div className="px-6 py-3.5 bg-zinc-900/60 border-b border-zinc-850 flex flex-wrap items-center justify-between text-xs font-mono text-zinc-300 gap-2">
              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <CheckCircle2 className="w-4 h-4" />
                <span>139 passed in 8.21s</span>
              </div>
              <div className="flex items-center gap-3 text-zinc-400 text-[11px]">
                <span className="text-zinc-500">•</span>
                <span className="text-zinc-300">85% code coverage</span>
                <span className="text-zinc-500">•</span>
                <span>Python 3.12.14</span>
              </div>
            </div>

            {/* Test Module List */}
            <div className="p-6 max-h-[60vh] overflow-y-auto space-y-3">
              {testModules.map((module) => (
                <div
                  key={module.filename}
                  className="p-3.5 rounded-xl border border-zinc-850 bg-zinc-900/30 hover:border-zinc-800 transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2 font-mono text-xs text-white font-medium">
                      <FileCode className="w-3.5 h-3.5 text-zinc-400" />
                      <span>{module.filename}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono text-zinc-500">
                        {module.duration}
                      </span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                        <Check className="w-3 h-3" />
                        {module.passedCount} passed
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-zinc-400 font-normal leading-relaxed pl-5">
                    {module.description}
                  </p>
                </div>
              ))}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-zinc-850 bg-zinc-900/30 flex items-center justify-between text-xs font-mono text-zinc-500">
              <span className="flex items-center gap-1.5">
                <Terminal className="w-3 h-3 text-zinc-400" />
                pytest -v --cov=schemaslim
              </span>
              <button
                onClick={onClose}
                className="px-3 py-1 rounded-md bg-zinc-800 hover:bg-zinc-750 text-zinc-200 text-xs font-sans transition-colors cursor-pointer"
              >
                Close (Esc)
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
