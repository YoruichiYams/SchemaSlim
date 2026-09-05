import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { Cpu, Github, ShieldCheck, Menu, X, ArrowUpRight } from 'lucide-react';
import { TestReportModal } from './TestReportModal';

interface InstallButtonProps {
  onClick: (e: React.MouseEvent) => void;
}

// White accent capsule Install CTA with diffuse ambient glow and 45-deg arrow
const InstallButton: React.FC<InstallButtonProps> = ({ onClick }) => {
  return (
    <button
      onClick={onClick}
      className="group relative flex items-center gap-1.5 bg-white text-zinc-950 font-medium text-xs sm:text-sm px-4 py-2 rounded-full shadow-[0_0_20px_-3px_rgba(255,255,255,0.35)] hover:shadow-[0_0_30px_-2px_rgba(255,255,255,0.55)] hover:scale-[1.03] active:scale-[0.97] transition-all duration-300 select-none cursor-pointer"
    >
      <span>Install</span>
      <ArrowUpRight className="w-3.5 h-3.5 sm:w-4 sm:h-4 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
    </button>
  );
};

export const Navbar: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [testModalOpen, setTestModalOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const handleInstallClick = (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    if (location.pathname === '/docs') {
      const el = document.getElementById('install');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
      }
      navigate('/docs#install', { replace: true });
    } else {
      navigate('/docs#install');
    }
  };

  const navLinks = [
    { to: '/', label: 'Overview' },
    { to: '/architecture', label: 'Architecture' },
    { to: '/benchmarks', label: 'Benchmarks' },
    { to: '/security', label: 'Security' },
    { to: '/docs', label: 'Docs' },
  ];

  return (
    <nav className="sticky top-0 z-50 backdrop-blur-md bg-zinc-950/85 border-b border-zinc-800/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-white group-hover:border-zinc-700 transition-all">
            <Cpu className="w-4 h-4 text-white" />
          </div>
          <span className="font-mono font-bold text-xl text-white tracking-tight">
            Schema<span className="text-zinc-400">Slim</span>
          </span>
        </Link>

        {/* Desktop Navigation Links (Sliding Pill Animation) */}
        <div className="hidden md:flex items-center gap-1 bg-zinc-900/60 border border-zinc-800/80 rounded-full p-1 backdrop-blur-md">
          {navLinks.map((item) => {
            const isActive = location.pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className="relative px-4 py-1.5 text-xs sm:text-sm font-medium transition-colors select-none rounded-full"
              >
                {isActive && (
                  <motion.div
                    layoutId="active-nav-pill"
                    className="absolute inset-0 bg-zinc-800 rounded-full"
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
                <span
                  className={`relative z-10 transition-colors ${
                    isActive ? 'text-white font-medium' : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {item.label}
                </span>
              </Link>
            );
          })}
        </div>

        {/* Right Actions Desktop: Test Badge, White Capsule Install CTA, GitHub */}
        <div className="hidden md:flex items-center gap-3">
          {/* Interactive Test Suite Verification Trigger */}
          <button
            onClick={() => setTestModalOpen(true)}
            className="flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 bg-zinc-900/70 hover:bg-zinc-850 px-2.5 py-1.5 rounded-full border border-zinc-800 hover:border-zinc-700 transition-colors cursor-pointer select-none active:scale-95"
            title="Inspect Pytest Suite Verification"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>104 tests pass</span>
          </button>

          {/* White Accent Capsule Install CTA placed strictly to the LEFT of GitHub */}
          <InstallButton onClick={handleInstallClick} />

          <a
            href="https://github.com/YoruichiYams/schemaslim"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-900 hover:bg-zinc-800 text-xs font-mono text-zinc-300 hover:text-white transition-all border border-zinc-800 active:scale-95 min-h-[36px]"
          >
            <Github className="w-3.5 h-3.5" />
            <span>GitHub</span>
          </a>
        </div>

        {/* Mobile Right Controls: Compact Test Badge & 44px Hamburger Toggle */}
        <div className="flex md:hidden items-center gap-2">
          {/* Compact Mobile Test Badge */}
          <button
            onClick={() => setTestModalOpen(true)}
            className="flex items-center gap-1 text-[11px] font-mono text-zinc-400 hover:text-zinc-200 bg-zinc-900/80 px-2.5 py-2 rounded-full border border-zinc-800 transition-colors cursor-pointer select-none min-h-[44px]"
            title="104 tests pass"
            aria-label="Inspect 104 passed tests"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-semibold text-zinc-300">104</span>
          </button>

          {/* Mobile Hamburger Toggle with 44x44px Touch Target */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="w-11 h-11 flex items-center justify-center rounded-xl text-zinc-400 hover:text-white bg-zinc-900 border border-zinc-800 transition-colors cursor-pointer active:scale-95"
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5 text-zinc-200" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown with AnimatePresence */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="md:hidden border-t border-zinc-850 bg-zinc-950/98 backdrop-blur-xl overflow-hidden px-4 py-4 space-y-4 shadow-2xl"
          >
            <div className="space-y-1">
              {navLinks.map((link) => {
                const active = isActive(location.pathname, link.to);
                return (
                  <Link
                    key={link.to}
                    to={link.to}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center justify-between px-3.5 py-3 rounded-xl text-base font-medium transition-colors min-h-[48px] ${
                      active
                        ? 'text-white bg-zinc-900 font-semibold border border-zinc-800'
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-900/60'
                    }`}
                  >
                    <span>{link.label}</span>
                    {active && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />}
                  </Link>
                );
              })}
            </div>

            <div className="pt-3 border-t border-zinc-850/80 flex flex-col sm:flex-row gap-2.5">
              <button
                onClick={(e) => {
                  setMobileMenuOpen(false);
                  handleInstallClick(e);
                }}
                className="w-full text-center bg-white hover:bg-zinc-100 text-zinc-950 font-medium px-4 py-3 rounded-full text-sm inline-flex items-center justify-center gap-2 shadow-[0_0_20px_-3px_rgba(255,255,255,0.35)] transition-all select-none cursor-pointer min-h-[44px]"
              >
                <span>Install SchemaSlim</span>
                <ArrowUpRight className="w-4 h-4" />
              </button>
              <a
                href="https://github.com/YoruichiYams/schemaslim"
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center px-4 py-3 rounded-full bg-zinc-900 text-zinc-300 hover:text-white hover:bg-zinc-850 inline-flex items-center justify-center gap-2 border border-zinc-800 text-sm font-mono transition-colors min-h-[44px]"
              >
                <Github className="w-4 h-4" />
                <span>GitHub Repository</span>
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Test Suite Verification Modal */}
      <TestReportModal isOpen={testModalOpen} onClose={() => setTestModalOpen(false)} />
    </nav>
  );
};

function isActive(currentPath: string, targetPath: string) {
  return currentPath === targetPath;
}
