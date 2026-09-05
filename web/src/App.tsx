import React from 'react';
import { BrowserRouter, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { AmbientBackground } from './components/AmbientBackground';
import { OverviewPage } from './pages/OverviewPage';
import { ArchitecturePage } from './pages/ArchitecturePage';
import { BenchmarksPage } from './pages/BenchmarksPage';
import { SecurityPage } from './pages/SecurityPage';
import { DocsPage } from './pages/DocsPage';
import { ScrollToTop } from './components/ScrollToTop';

const AnimatedRoutes: React.FC = () => {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        className="flex-1 flex flex-col w-full max-w-full overflow-x-hidden"
      >
        <Routes location={location}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/architecture" element={<ArchitecturePage />} />
          <Route path="/benchmarks" element={<BenchmarksPage />} />
          <Route path="/security" element={<SecurityPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/install" element={<Navigate to="/docs#install" replace />} />
          <Route path="*" element={<OverviewPage />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-emerald-500/20 selection:text-emerald-300 w-full max-w-full overflow-x-hidden relative">
        <AmbientBackground />
        <Navbar />
        <main className="flex-1 flex flex-col relative z-10 w-full max-w-full overflow-x-hidden">
          <AnimatedRoutes />
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  );
};

export default App;
