import React, { useMemo } from 'react';
import { motion, useReducedMotion, Variants } from 'framer-motion';

export interface HeadlinePart {
  text: string;
  gradient?: boolean;
}

interface AnimatedHeadlineProps {
  parts: HeadlinePart[];
  as?: 'h1' | 'h2';
  className?: string;
  delay?: number;
}

const lerp = (a: number, b: number, t: number) => Math.round(a + (b - a) * t);
// AUB gradient stops: magenta #EC008C → purple #7B2FFF
const mix = (t: number) => `rgb(${lerp(0xec, 0x7b, t)}, ${lerp(0x00, 0x2f, t)}, ${lerp(0x8c, 0xff, t)})`;

const container: Variants = {
  hidden: {},
  show: (delay: number) => ({ transition: { staggerChildren: 0.05, delayChildren: delay } }),
};
const word: Variants = {
  hidden: { y: '108%' },
  show: { y: '0%', transition: { duration: 0.85, ease: [0.16, 1, 0.3, 1] } },
};

/**
 * Word-level masked reveal. Gradient words are coloured per-word along the brand
 * gradient (background-clip:text on a parent breaks once children are transformed).
 * The text is real DOM text, so it is readable instantly by crawlers/screen readers.
 */
export const AnimatedHeadline: React.FC<AnimatedHeadlineProps> = ({ parts, as: Tag = 'h1', className = '', delay = 0.05 }) => {
  const reduce = useReducedMotion();

  const words = useMemo(() => {
    const flat: { w: string; gradient: boolean; gi: number }[] = [];
    let gcount = 0;
    parts.forEach((p) => {
      p.text.split(/\s+/).filter(Boolean).forEach((w) => {
        flat.push({ w, gradient: !!p.gradient, gi: p.gradient ? gcount++ : -1 });
      });
    });
    return { flat, gcount };
  }, [parts]);

  const MotionTag = motion[Tag];

  return (
    <MotionTag
      className={className}
      variants={container}
      custom={delay}
      initial={reduce ? 'show' : 'hidden'}
      animate="show"
    >
      {words.flat.map((item, i) => {
        const style: React.CSSProperties | undefined = item.gradient
          ? {
              backgroundImage: `linear-gradient(92deg, ${mix(item.gi / words.gcount)}, ${mix((item.gi + 1) / words.gcount)})`,
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              color: 'transparent',
            }
          : undefined;
        return (
          <React.Fragment key={i}>
            <span className="word-mask">
              <motion.span variants={word} style={style}>
                {item.w}
              </motion.span>
            </span>
            {i < words.flat.length - 1 ? ' ' : null}
          </React.Fragment>
        );
      })}
    </MotionTag>
  );
};
