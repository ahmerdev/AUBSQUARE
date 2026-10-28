import React, { useRef, ReactNode } from 'react';
import { motion, useMotionValue, useReducedMotion, useSpring } from 'framer-motion';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  enableTilt?: boolean;
  onClick?: () => void;
}

/**
 * Glass surface with restrained 3D tilt + cursor-following specular sheen.
 * Pointer position drives motion values / CSS variables directly — zero React re-renders while moving.
 * Tilt only runs for a real mouse (never touch) and never when reduced motion is requested.
 */
export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = '',
  contentClassName = '',
  enableTilt = true,
  onClick,
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const rx = useMotionValue(0);
  const ry = useMotionValue(0);
  const srx = useSpring(rx, { stiffness: 220, damping: 22, mass: 0.5 });
  const sry = useSpring(ry, { stiffness: 220, damping: 22, mass: 0.5 });

  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el || e.pointerType !== 'mouse') return;
    const r = el.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    el.style.setProperty('--mx', `${x}px`);
    el.style.setProperty('--my', `${y}px`);
    if (enableTilt && !reduce) {
      rx.set(-(y / r.height - 0.5) * 9);
      ry.set((x / r.width - 0.5) * 9);
    }
  };
  const onLeave = () => {
    rx.set(0);
    ry.set(0);
  };

  return (
    <motion.div
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      onClick={onClick}
      style={enableTilt && !reduce ? { rotateX: srx, rotateY: sry, transformPerspective: 1000 } : undefined}
      className={`group/glass relative rounded-3xl glass-panel overflow-hidden border border-aub-border/80 shadow-lg shadow-black/50 transition-[border-color,box-shadow] duration-300 hover:border-aub-purple/50 hover:shadow-glow-purple/30 ${className}`}
    >
      {/* Specular sheen that follows the cursor (hover-capable devices only) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -inset-px rounded-[inherit] opacity-0 transition-opacity duration-300 [@media(hover:hover)]:group-hover/glass:opacity-100"
        style={{
          background:
            'radial-gradient(420px circle at var(--mx, 50%) var(--my, 50%), rgba(236,0,140,0.17), rgba(123,47,255,0.09) 40%, transparent 70%)',
        }}
      />
      <div className={`relative z-10 w-full h-full ${contentClassName}`}>{children}</div>
    </motion.div>
  );
};
