import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Copy, Check } from 'lucide-react';
import { copyToClipboard } from '../../utils/clipboard';

export const PackageManagerSwitcher: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'uv_tool' | 'uvx' | 'pipx' | 'pip'>('uv_tool');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showToast, setShowToast] = useState(false);

  const installSnippets = {
    uv_tool: {
      cmd: 'uv tool install schemaslim',
      desc: 'Recommended: Installs SchemaSlim CLI into an isolated virtual environment and adds it to your PATH.',
    },
    uvx: {
      cmd: 'uvx schemaslim wrap',
      desc: 'Zero-install ephemeral run: Executes client discovery and virtualization directly without permanent install.',
    },
    pipx: {
      cmd: 'pipx install schemaslim',
      desc: 'Standard isolated Python application execution for global CLI availability.',
    },
    pip: {
      cmd: 'pip install schemaslim',
      desc: 'Standard installation into an active Python virtualenv or system interpreter.',
    },
  };

  const currentSnippet = installSnippets[activeTab];

  const handleCopy = async (key: string, text: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopiedKey(key);
      setShowToast(true);
      setTimeout(() => setCopiedKey(null), 2000);
      setTimeout(() => setShowToast(false), 2400);
    }
  };

  // Keyboard shortcut: pressing 'c' copies current command (pure 'c'/'C' only, not Ctrl+C/Cmd+C)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) {
        return;
      }
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName) || target?.isContentEditable) {
        return;
      }
      if (e.key === 'c' || e.key === 'C') {
        e.preventDefault();
        handleCopy('main', currentSnippet.cmd);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentSnippet.cmd]);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-lg">
      {/* Animated Sliding Tabs */}
      <div className="flex items-center gap-1 border-b border-zinc-800 bg-zinc-900/40 p-1.5 overflow-x-auto">
        {(
          [
            ['uv_tool', 'uv tool (Recommended)'],
            ['uvx', 'uvx (Ephemeral)'],
            ['pipx', 'pipx'],
            ['pip', 'pip'],
          ] as const
        ).map(([key, label]) => {
          const isActive = activeTab === key;
          return (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className="relative px-3.5 py-1.5 text-xs font-mono transition-colors cursor-pointer whitespace-nowrap rounded-md select-none"
            >
              {isActive && (
                <motion.div
                  layoutId="install-package-tab"
                  className="absolute inset-0 bg-zinc-800 rounded-md"
                  transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                />
              )}
              <span
                className={`relative z-10 transition-colors ${
                  isActive ? 'text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>

      {/* Snippet & Copy Action */}
      <div className="p-4 sm:p-5">
        <div className="flex items-center justify-between bg-zinc-900/80 rounded-lg p-3 sm:p-3.5 border border-zinc-800 font-mono text-xs sm:text-sm text-zinc-200 mb-2.5">
          <div className="flex items-center gap-2 overflow-x-auto mr-2">
            <span className="text-zinc-500 select-none">$</span>
            <span className="text-white font-medium">{currentSnippet.cmd}</span>
          </div>
          <button
            onClick={() => handleCopy('main', currentSnippet.cmd)}
            className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-zinc-800 hover:bg-zinc-750 text-xs font-mono text-zinc-200 transition-all cursor-pointer active:scale-95 border border-zinc-700/50"
            title="Copy command (Press 'c')"
          >
            {copiedKey === 'main' ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400 font-medium">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-zinc-400" />
                <span>Copy</span>
                <span className="text-zinc-500 font-mono text-[10px] hidden sm:inline ml-0.5">[c]</span>
              </>
            )}
          </button>
        </div>
        <p className="text-xs text-zinc-400 font-normal leading-relaxed">
          {currentSnippet.desc}
        </p>
      </div>

      {/* Quick-copy Toast Notification */}
      <AnimatePresence>
        {showToast && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.96 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl bg-zinc-900/95 border border-zinc-700/80 text-white text-xs font-mono shadow-2xl backdrop-blur-md"
          >
            <div className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/40">
              <Check className="w-3 h-3" />
            </div>
            <div>
              <div className="font-semibold text-white">Copied to clipboard!</div>
              <div className="text-zinc-400 text-[11px] truncate max-w-[240px] sm:max-w-xs font-normal">
                {currentSnippet.cmd}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
