import React from 'react';
import { motion, useScroll, useSpring } from 'framer-motion';

/** Thin brand-gradient reading-progress bar pinned to the very top. */
export const ScrollProgress: React.FC = () => {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 28, mass: 0.3 });
  return (
    <motion.div
      aria-hidden="true"
      style={{ scaleX, transformOrigin: '0% 50%' }}
      className="fixed top-0 left-0 right-0 z-[60] h-[2px] bg-aub-gradient shadow-[0_0_12px_rgba(236,0,140,0.7)] pointer-events-none"
    />
  );
};
