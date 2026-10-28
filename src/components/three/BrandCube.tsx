import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Box, Sparkles, Layers, ShieldCheck, Cpu } from 'lucide-react';

export const BrandCube: React.FC = () => {
  const cardRef = useRef<HTMLDivElement>(null);
  const [rotateX, setRotateX] = useState(0);
  const [rotateY, setRotateY] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    setRotateX(-((y - centerY) / centerY) * 12);
    setRotateY(((x - centerX) / centerX) * 12);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    setRotateX(0);
    setRotateY(0);
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      style={{
        perspective: '1200px',
      }}
      className="relative w-full h-[340px] sm:h-[400px] flex items-center justify-center select-none"
    >
      {/* Background Ambient Glow */}
      <div className="absolute w-64 h-64 bg-aub-magenta/20 blur-3xl rounded-full pointer-events-none animate-pulse-slow" />
      <div className="absolute w-64 h-64 bg-aub-purple/25 blur-3xl rounded-full pointer-events-none translate-x-8 translate-y-8" />

      {/* 3D Holographic Rotating Monolith */}
      <motion.div
        style={{
          transformStyle: 'preserve-3d',
          transform: `rotateX(${rotateX}deg) rotateY(${rotateY}deg) ${isHovered ? 'translateZ(20px)' : 'translateZ(0px)'}`,
          transition: 'transform 0.15s ease-out',
        }}
        className="relative z-10 w-72 sm:w-80 h-72 sm:h-80 rounded-3xl glass-panel border border-aub-border/90 p-6 flex flex-col items-center justify-between shadow-2xl overflow-hidden"
      >
        {/* Top Header Tag */}
        <div className="w-full flex items-center justify-between pb-3 border-b border-aub-border/60">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-aub-magenta animate-ping" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-aub-accent-labels font-semibold">
              3D Brand Architecture
            </span>
          </div>
          <span className="text-[10px] font-mono text-aub-text-secondary">EST. 2020</span>
        </div>

        {/* Central Rotating 3D Geometric Hologram */}
        <div className="relative my-auto flex items-center justify-center">
          {/* Outer Pulsing Ring */}
          <div className="absolute w-36 h-36 rounded-full border border-aub-magenta/30 animate-spin" style={{ animationDuration: '14s' }} />
          <div className="absolute w-28 h-28 rounded-full border border-aub-purple/40 animate-spin" style={{ animationDuration: '9s', animationDirection: 'reverse' }} />

          {/* Central Monogram Cube */}
          <motion.div
            animate={{
              rotateY: [0, 360],
              rotateX: [10, -10, 10],
            }}
            transition={{
              rotateY: { duration: 16, repeat: Infinity, ease: 'linear' },
              rotateX: { duration: 6, repeat: Infinity, ease: 'easeInOut' },
            }}
            style={{ transformStyle: 'preserve-3d' }}
            className="w-20 h-20 rounded-2xl bg-aub-gradient flex items-center justify-center shadow-glow-magenta/50 border border-white/20"
          >
            <span className="text-2xl font-black font-display text-white tracking-wider">
              AUB
            </span>
          </motion.div>
        </div>

        {/* Bottom Feature Badges */}
        <div className="w-full grid grid-cols-2 gap-2 pt-3 border-t border-aub-border/60 text-center">
          <div className="p-2 rounded-xl bg-aub-card/70 border border-aub-border text-[11px] font-semibold text-white">
            Vector Design DNA
          </div>
          <div className="p-2 rounded-xl bg-aub-card/70 border border-aub-border text-[11px] font-semibold text-aub-accent-labels">
            3D Web Experiences
          </div>
        </div>
      </motion.div>

      {/* Floating Spatial Badges */}
      <motion.div
        animate={{ y: [-8, 8, -8] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute top-4 right-2 sm:right-6 z-20 px-3 py-1.5 rounded-xl glass-panel border border-aub-purple/40 text-[11px] font-semibold text-white shadow-lg flex items-center gap-1.5"
      >
        <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
        <span>100% Bespoke</span>
      </motion.div>

      <motion.div
        animate={{ y: [8, -8, 8] }}
        transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
        className="absolute bottom-4 left-2 sm:left-6 z-20 px-3 py-1.5 rounded-xl glass-panel border border-aub-magenta/40 text-[11px] font-semibold text-white shadow-lg flex items-center gap-1.5"
      >
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
        <span>Global Clients</span>
      </motion.div>
    </div>
  );
};
