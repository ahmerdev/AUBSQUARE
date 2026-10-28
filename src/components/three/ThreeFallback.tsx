import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Layers, Box, Cpu } from 'lucide-react';

export const ThreeFallback: React.FC = () => {
  return (
    <div className="relative w-full h-[380px] sm:h-[450px] lg:h-[500px] flex items-center justify-center">
      {/* Ambient background glows */}
      <div className="absolute w-72 h-72 rounded-full bg-aub-magenta/20 blur-3xl animate-pulse-slow"></div>
      <div className="absolute w-72 h-72 rounded-full bg-aub-purple/25 blur-3xl translate-x-12 translate-y-12"></div>

      {/* Central 3D Rotating Brand Card */}
      <motion.div
        animate={{
          rotateY: [0, 360],
          rotateX: [10, -10, 10],
          y: [-8, 8, -8],
        }}
        transition={{
          rotateY: { duration: 20, repeat: Infinity, ease: 'linear' },
          rotateX: { duration: 6, repeat: Infinity, ease: 'easeInOut' },
          y: { duration: 4, repeat: Infinity, ease: 'easeInOut' },
        }}
        style={{ transformStyle: 'preserve-3d' }}
        className="relative z-10 w-64 h-64 sm:w-72 sm:h-72 rounded-3xl glass-panel border border-aub-border flex flex-col items-center justify-center p-6 shadow-glow-magenta/30"
      >
        <div className="w-20 h-20 rounded-2xl bg-aub-gradient flex items-center justify-center shadow-lg mb-4 shadow-glow-magenta/50">
          <Box className="w-10 h-10 text-white animate-spin" style={{ animationDuration: '12s' }} />
        </div>
        <h4 className="text-xl font-bold text-white tracking-wide">AUB SQUARE</h4>
        <p className="text-xs text-aub-accent-labels mt-1 uppercase tracking-widest font-semibold">
          3D Creative Studio
        </p>

        {/* Ambient Ring */}
        <div className="absolute -inset-4 rounded-3xl border border-aub-magenta/20 animate-pulse pointer-events-none" />
      </motion.div>

      {/* Floating Brand Badges */}
      <motion.div
        animate={{ y: [-10, 10, -10], x: [0, 5, 0] }}
        transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute top-10 right-4 sm:right-12 z-20 px-4 py-2.5 rounded-xl glass-panel border border-aub-purple/40 flex items-center gap-2 shadow-lg"
      >
        <Sparkles className="w-4 h-4 text-aub-magenta" />
        <span className="text-xs font-semibold text-white">Brand Architecture</span>
      </motion.div>

      <motion.div
        animate={{ y: [10, -10, 10], x: [0, -5, 0] }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
        className="absolute bottom-12 left-4 sm:left-10 z-20 px-4 py-2.5 rounded-xl glass-panel border border-aub-magenta/40 flex items-center gap-2 shadow-lg"
      >
        <Layers className="w-4 h-4 text-aub-purple" />
        <span className="text-xs font-semibold text-white">UI/UX & 3D Web</span>
      </motion.div>

      <motion.div
        animate={{ scale: [0.95, 1.05, 0.95] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
        className="absolute -bottom-4 right-8 z-20 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border flex items-center gap-1.5"
      >
        <Cpu className="w-3.5 h-3.5 text-aub-accent-labels" />
        <span className="text-[11px] font-mono text-aub-text-secondary">60 FPS WebGL</span>
      </motion.div>
    </div>
  );
};
