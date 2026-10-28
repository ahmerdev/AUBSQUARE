import React, { useRef } from 'react';
import { motion, useReducedMotion, useScroll, useSpring, useTransform } from 'framer-motion';

interface Scroll3DSectionProps {
  children: React.ReactNode;
  className?: string;
  intensity?: 'subtle' | 'medium' | 'dramatic';
}

/**
 * Entrance choreography for a section: it tilts up out of depth as it enters the viewport
 * and then settles to `transform: none`.
 *
 * Previous version kept sections permanently rotated/scaled/dimmed (blurry text, 60% opacity at the
 * viewport edge, transformed ancestors for everything inside). This one only animates on the way in and
 * hands back a clean, untransformed, fully opaque section — so sticky, fixed, backdrop-filter and text
 * rendering inside are never affected.
 */
export const Scroll3DSection: React.FC<Scroll3DSectionProps> = ({ children, className = '', intensity = 'medium' }) => {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start 96%', 'start 55%'],
  });
  const p = useSpring(scrollYProgress, { stiffness: 140, damping: 26, mass: 0.4 });

  const rot = intensity === 'subtle' ? 5 : intensity === 'medium' ? 8 : 12;
  const rise = intensity === 'subtle' ? 28 : intensity === 'medium' ? 44 : 64;

  const transform = useTransform(p, (v) =>
    v >= 0.995
      ? 'none'
      : `perspective(1200px) translate3d(0, ${(1 - v) * rise}px, ${(1 - v) * -60}px) rotateX(${(1 - v) * rot}deg) scale(${0.97 + 0.03 * v})`
  );
  const opacity = useTransform(p, [0, 0.55, 1], [0.15, 0.9, 1]);

  if (reduce) {
    return (
      <div ref={ref} className={`relative ${className}`}>
        {children}
      </div>
    );
  }

  return (
    <div ref={ref} className={`relative ${className}`}>
      <motion.div style={{ transform, opacity, transformOrigin: '50% 100%' }}>{children}</motion.div>
    </div>
  );
};
