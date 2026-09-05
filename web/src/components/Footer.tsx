import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ClaudeIcon,
  CursorIcon,
  AntigravityIcon,
  VSCodeIcon,
  WindsurfIcon,
  CodexIcon,
  CliIcon,
} from './icons/ClientIcons';

interface SupportedClient {
  id: string;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
}

const supportedClients: SupportedClient[] = [
  { id: 'claude', name: 'Claude Desktop', icon: ClaudeIcon },
  { id: 'cursor', name: 'Cursor', icon: CursorIcon },
  { id: 'antigravity', name: 'Antigravity', icon: AntigravityIcon },
  { id: 'cline', name: 'VS Code', icon: VSCodeIcon },
  { id: 'windsurf', name: 'Windsurf', icon: WindsurfIcon },
  { id: 'codex', name: 'Codex', icon: CodexIcon },
  { id: 'custom', name: 'Other CLI / Harness', icon: CliIcon },
];

export const Footer: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleClientClick = (clientId: string) => {
    if (location.pathname === '/docs') {
      navigate(`/docs?client=${clientId}#install`, { replace: true });

      // Dispatch event for ClientConfigurator sync
      window.dispatchEvent(
        new CustomEvent('schemaslim:select-client', { detail: { clientId } })
      );

      const el = document.getElementById('install');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
      }
    } else {
      navigate(`/docs?client=${clientId}#install`);
    }
  };

  return (
    <footer className="border-t border-zinc-850 bg-zinc-950 py-8 text-zinc-500 text-xs font-mono">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4 text-center md:text-left">
        {/* Left: License & Offline Guarantee */}
        <div className="text-zinc-500 select-none">
          MIT License © 2026 SchemaSlim Team. Offline &amp; Zero API Keys.
        </div>

        {/* Center: Ecosystem Matrix Icons */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono uppercase tracking-widest text-zinc-600 mr-1 select-none hidden sm:inline">
            Environments
          </span>
          <div className="flex items-center gap-3.5 px-3 py-1.5 rounded-full bg-zinc-900/50 border border-zinc-800/60 shadow-inner">
            {supportedClients.map((client) => {
              const Icon = client.icon;
              return (
                <motion.button
                  key={client.id}
                  type="button"
                  onClick={() => handleClientClick(client.id)}
                  whileHover={{ scale: 1.15, y: -1 }}
                  whileTap={{ scale: 0.95 }}
                  transition={{ type: 'spring', stiffness: 450, damping: 25 }}
                  className="text-zinc-500 hover:text-zinc-200 transition-colors p-0.5 cursor-pointer flex items-center justify-center focus:outline-none focus-visible:ring-1 focus-visible:ring-zinc-400 rounded"
                  title={client.name}
                  aria-label={client.name}
                >
                  <Icon className="w-4 h-4 sm:w-[17px] sm:h-[17px]" />
                </motion.button>
              );
            })}
          </div>
        </div>

        {/* Right: Technical Stack */}
        <div className="text-zinc-500 select-none">
          Built with React 19, Vite &amp; Motion.
        </div>
      </div>
    </footer>
  );
};
