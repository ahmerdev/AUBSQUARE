import React, { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

interface RevealImageProps {
  src: string;
  alt: string;
  /** Classes for the clipping frame (default fills the positioned parent). */
  className?: string;
  imgClassName?: string;
  /** Skip the lazy attribute for above-the-fold images. */
  eager?: boolean;
}

/**
 * Editorial image reveal: the frame wipes open (clip-path) while the photo settles from 1.12 → 1 scale.
 * A hover zoom lives on an inner wrapper so it never fights Framer's transforms.
 * If the image fails to load, a brand-gradient placeholder is shown instead of a broken-image icon.
 */
export const RevealImage: React.FC<RevealImageProps> = ({ src, alt, className = 'absolute inset-0', imgClassName = '', eager = false }) => {
  const [failed, setFailed] = useState(false);
  const reduce = useReducedMotion();

  return (
    <motion.div
      className={`overflow-hidden ${className}`}
      initial={reduce ? false : { clipPath: 'inset(0 0 100% 0)' }}
      whileInView={{ clipPath: 'inset(0 0 0% 0)' }}
      viewport={{ once: true, margin: '0px 0px -6% 0px' }}
      transition={{ duration: 0.95, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="w-full h-full transition-transform duration-700 ease-out [@media(hover:hover)]:group-hover:scale-105">
        {failed ? (
          <div className="w-full h-full bg-gradient-to-br from-[#2a1450] via-[#1a0f3a] to-[#4a0e3a]" aria-label={alt} role="img" />
        ) : (
          <motion.img
            src={src}
            alt={alt}
            loading={eager ? 'eager' : 'lazy'}
            decoding="async"
            onError={() => setFailed(true)}
            initial={reduce ? false : { scale: 1.14 }}
            whileInView={{ scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1.3, ease: [0.22, 1, 0.36, 1] }}
            className={`w-full h-full object-cover ${imgClassName}`}
          />
        )}
      </div>
    </motion.div>
  );
};
