import React from 'react';
import { motion } from 'framer-motion';

interface SwipeAreaProps {
  onPrev: () => void;
  onNext: () => void;
  label: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Horizontal swipe / drag + arrow-key support for "one slide at a time" sliders.
 * Vertical gestures are left to the browser (touch-action: pan-y) so page scrolling is never blocked.
 */
export const SwipeArea: React.FC<SwipeAreaProps> = ({ onPrev, onNext, label, children, className = '' }) => (
  <motion.div
    role="region"
    aria-roledescription="carousel"
    aria-label={label}
    tabIndex={0}
    onKeyDown={(e) => {
      if (e.key === 'ArrowLeft') onPrev();
      if (e.key === 'ArrowRight') onNext();
    }}
    drag="x"
    dragDirectionLock
    dragConstraints={{ left: 0, right: 0 }}
    dragElastic={0.16}
    dragSnapToOrigin
    onDragEnd={(_, info) => {
      if (info.offset.x < -70 || info.velocity.x < -520) onNext();
      else if (info.offset.x > 70 || info.velocity.x > 520) onPrev();
    }}
    style={{ touchAction: 'pan-y' }}
    className={`outline-none focus-visible:ring-2 focus-visible:ring-aub-magenta rounded-3xl cursor-grab active:cursor-grabbing ${className}`}
  >
    {children}
  </motion.div>
);
