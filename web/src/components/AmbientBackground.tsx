import React from 'react';
import { motion } from 'motion/react';

export const AmbientBackground: React.FC = () => {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {/* Sphere 1: Top-Left Corner (Emerald accent aura) */}
      <motion.div
        animate={{
          x: [0, 70, 30, -50, 0],
          y: [0, 50, 90, 40, 0],
          scale: [1, 1.1, 0.95, 1.06, 1],
        }}
        transition={{
          duration: 22,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        style={{ willChange: 'transform' }}
        className="absolute -top-16 sm:-top-24 -left-16 sm:-left-24 w-[300px] h-[300px] sm:w-[550px] sm:h-[550px] rounded-full bg-emerald-500/15 blur-[70px] sm:blur-[140px] pointer-events-none transform-gpu"
      />

      {/* Sphere 2: Center / Right (Cyan soft glow) */}
      <motion.div
        animate={{
          x: [0, -80, -30, 60, 0],
          y: [0, 70, -50, 30, 0],
          scale: [1, 0.94, 1.12, 0.98, 1],
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        style={{ willChange: 'transform' }}
        className="absolute top-1/4 -right-16 sm:-right-28 w-[320px] h-[320px] sm:w-[600px] sm:h-[600px] rounded-full bg-cyan-500/10 blur-[80px] sm:blur-[160px] pointer-events-none transform-gpu"
      />

      {/* Sphere 3: Lower Third (Slate ambient glow) */}
      <motion.div
        animate={{
          x: [0, 60, -50, 40, 0],
          y: [0, -60, 40, -30, 0],
          scale: [1, 1.12, 0.92, 1.05, 1],
        }}
        transition={{
          duration: 20,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        style={{ willChange: 'transform' }}
        className="absolute top-2/3 left-1/6 sm:left-1/4 w-[280px] h-[280px] sm:w-[500px] sm:h-[500px] rounded-full bg-slate-400/10 blur-[65px] sm:blur-[130px] pointer-events-none transform-gpu"
      />

      {/* Subtle Grid Texture Overlay */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />
    </div>
  );
};
