import React from 'react';
import { motion } from 'framer-motion';
import { Compass, Sparkles, Layers, Box } from 'lucide-react';

interface ProcessOrbProps {
  color: string;
  secondaryColor: string;
  shape?: 'octahedron' | 'icosahedron' | 'torus' | 'dodecahedron';
}

export const ProcessOrb: React.FC<ProcessOrbProps> = ({
  color,
  secondaryColor,
  shape = 'octahedron',
}) => {
  return (
    <div className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto flex items-center justify-center select-none py-2">
      {/* Background Soft Glow */}
      <div
        className="absolute inset-2 rounded-full blur-xl opacity-40 transition-opacity duration-300"
        style={{ background: color }}
      />

      {/* 3D Rotating Gyro Ring 1 */}
      <motion.div
        animate={{ rotateZ: 360, rotateX: [20, -20, 20] }}
        transition={{
          rotateZ: { duration: 8, repeat: Infinity, ease: 'linear' },
          rotateX: { duration: 4, repeat: Infinity, ease: 'easeInOut' },
        }}
        className="absolute inset-1 rounded-full border-2 border-dashed opacity-70"
        style={{
          transformStyle: 'preserve-3d',
          borderColor: color,
          boxShadow: `0 0 15px -3px ${color}`,
        }}
      />

      {/* 3D Rotating Gyro Ring 2 (Opposite direction) */}
      <motion.div
        animate={{ rotateZ: -360, rotateY: [30, -30, 30] }}
        transition={{
          rotateZ: { duration: 10, repeat: Infinity, ease: 'linear' },
          rotateY: { duration: 5, repeat: Infinity, ease: 'easeInOut' },
        }}
        className="absolute inset-3 rounded-full border border-solid opacity-60"
        style={{
          transformStyle: 'preserve-3d',
          borderColor: secondaryColor,
          boxShadow: `0 0 12px -2px ${secondaryColor}`,
        }}
      />

      {/* Core Glowing Floating Icon */}
      <motion.div
        animate={{
          scale: [0.95, 1.05, 0.95],
          rotate: [0, 10, -10, 0],
        }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        className="relative z-10 w-11 h-11 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center shadow-lg border border-white/20"
        style={{
          background: `linear-gradient(135deg, ${color} 0%, ${secondaryColor} 100%)`,
        }}
      >
        {shape === 'octahedron' && <Sparkles className="w-5 h-5 text-white" />}
        {shape === 'icosahedron' && <Layers className="w-5 h-5 text-white" />}
        {shape === 'torus' && <Compass className="w-5 h-5 text-white" />}
        {shape === 'dodecahedron' && <Box className="w-5 h-5 text-white" />}
      </motion.div>
    </div>
  );
};
