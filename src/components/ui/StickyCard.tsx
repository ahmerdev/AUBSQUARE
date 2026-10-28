import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { motion, MotionValue, useScroll, useTransform } from 'framer-motion';
import { useDeviceProfile } from '../../lib/device';

/**
 * Stacked-card scroller built on real CSS `position: sticky`.
 *
 * Why the previous version failed (root causes):
 *  1. Scroll progress was measured on the sticky element itself. Once stuck, its
 *     top never moves, so progress stayed at 0 and the depth animation never ran.
 *  2. The viewport-height limit used a dynamic Tailwind class (`max-h-[calc(100dvh-${n}px)]`)
 *     which Tailwind cannot generate, so tall cards were never constrained and
 *     their lower halves were buried under the next card (≈950px cards on 844px phones).
 *  3. Stick offsets were fixed pixels, unrelated to real card height / viewport height.
 *
 * This implementation measures real card heights, derives the stick offsets so the
 * whole stack always fits the viewport, computes depth from deterministic geometry
 * (no layout reads while scrolling) and falls back to natural flow when the stack
 * cannot fit (phones, short landscape screens) so nothing is ever clipped.
 */

type Mode = 'stack' | 'flow';

interface StackMetrics {
  mode: Mode;
  tops: number[]; // sticky `top` per card (px)
  nat: number[]; // natural document-Y of each card's top
  vh: number;
}

interface StackLayout {
  mode: Mode;
  tops: number[];
  gap: number;
}

interface StackApi {
  layout: StackLayout;
  register: (index: number, el: HTMLElement | null) => void;
  depthFor: (index: number, y: number) => number;
  scrollY: MotionValue<number>;
  count: number;
}

const StackContext = createContext<StackApi | null>(null);

const sameLayout = (a: StackLayout, b: StackLayout) =>
  a.mode === b.mode && a.gap === b.gap && a.tops.length === b.tops.length && a.tops.every((t, i) => t === b.tops[i]);

interface StickyStackProps {
  children: React.ReactNode;
  className?: string;
  /** Distance from viewport top where the first card sticks (header clearance). */
  headerOffset?: { mobile?: number; desktop?: number };
}

export const StickyStack: React.FC<StickyStackProps> = ({ children, className = '', headerOffset }) => {
  const trackRef = useRef<HTMLDivElement>(null);
  const els = useRef<(HTMLElement | null)[]>([]);
  const ro = useRef<ResizeObserver | null>(null);
  const raf = useRef(0);
  const metrics = useRef<StackMetrics>({ mode: 'stack', tops: [], nat: [], vh: 800 });
  const { scrollY } = useScroll();
  const count = React.Children.count(children);

  const [layout, setLayout] = useState<StackLayout>(() => ({
    mode: typeof window !== 'undefined' && window.innerWidth < 768 ? 'flow' : 'stack',
    tops: Array.from({ length: count }, (_, i) => 84 + i * 14),
    gap: 96,
  }));

  const measure = useCallback(() => {
    const track = trackRef.current;
    if (!track) return;
    const items = els.current.slice(0, count).filter(Boolean) as HTMLElement[];
    const n = items.length;
    if (!n) return;

    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const baseTop = vw < 768 ? headerOffset?.mobile ?? 72 : headerOffset?.desktop ?? 88;
    const heights = items.map((el) => el.offsetHeight);
    const maxH = Math.max(...heights);

    const MIN_STEP = 12;
    const MAX_STEP = 56;
    const fits = vw >= 768 && maxH + (n - 1) * MIN_STEP <= vh - baseTop - 16;
    const mode: Mode = fits ? 'stack' : 'flow';
    const step = n > 1 ? Math.max(MIN_STEP, Math.min(MAX_STEP, Math.floor((vh - 20 - baseTop - maxH) / (n - 1)))) : 0;
    const gap = mode === 'stack' ? Math.round(Math.max(56, vh * 0.16)) : 24;
    const tops = items.map((_, i) => baseTop + i * step);

    const trackTop = track.getBoundingClientRect().top + window.scrollY;
    let acc = trackTop;
    const nat = heights.map((h) => {
      const t = acc;
      acc += h + gap;
      return t;
    });

    metrics.current = { mode, tops, nat, vh };
    setLayout((prev) => {
      const next = { mode, tops, gap };
      return sameLayout(prev, next) ? prev : next;
    });
  }, [count, headerOffset?.mobile, headerOffset?.desktop]);

  const schedule = useCallback(() => {
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(measure);
  }, [measure]);

  useLayoutEffect(() => {
    measure();
  }, [measure]);

  useEffect(() => {
    const observer = new ResizeObserver(schedule);
    ro.current = observer;
    if (trackRef.current) observer.observe(trackRef.current);
    els.current.forEach((el) => el && observer.observe(el));
    window.addEventListener('resize', schedule, { passive: true });
    window.addEventListener('load', schedule);
    (document as Document & { fonts?: { ready: Promise<unknown> } }).fonts?.ready.then(schedule);
    return () => {
      cancelAnimationFrame(raf.current);
      observer.disconnect();
      ro.current = null;
      window.removeEventListener('resize', schedule);
      window.removeEventListener('load', schedule);
    };
  }, [schedule]);

  const register = useCallback(
    (index: number, el: HTMLElement | null) => {
      els.current[index] = el;
      if (el) {
        ro.current?.observe(el);
        schedule();
      }
    },
    [schedule]
  );

  /**
   * Σ progress of every LATER card that is travelling over / has landed on this one.
   * Each later card contributes 0→1 as it climbs from the lower viewport edge to its stick point.
   */
  const depthFor = useCallback((index: number, y: number) => {
    const m = metrics.current;
    if (m.mode !== 'stack') return 0;
    let sum = 0;
    const startTop = m.vh - 80;
    for (let k = index + 1; k < m.nat.length; k++) {
      const screenTop = m.nat[k] - y;
      const span = startTop - m.tops[k];
      const p = span > 0 ? (startTop - screenTop) / span : 1;
      sum += p < 0 ? 0 : p > 1 ? 1 : p;
    }
    return sum;
  }, []);

  const api = useMemo<StackApi>(
    () => ({ layout, register, depthFor, scrollY, count }),
    [layout, register, depthFor, scrollY, count]
  );

  return (
    <StackContext.Provider value={api}>
      {/* No overflow / transform / contain on the track or any ancestor — either would kill sticky. */}
      <div ref={trackRef} className={`relative ${className}`} data-stack-mode={layout.mode}>
        {children}
      </div>
    </StackContext.Provider>
  );
};

interface StickyCardProps {
  children: React.ReactNode;
  index: number;
  /** Kept for backwards compatibility with existing pages; the stack counts its own children. */
  totalCards?: number;
  topOffset?: number;
  className?: string;
}

const StackedCard: React.FC<StickyCardProps & { api: StackApi }> = ({ children, index, className = '', api }) => {
  const { layout, register, depthFor, scrollY, count } = api;
  const device = useDeviceProfile();
  const isLast = index === count - 1;
  const isStack = layout.mode === 'stack';
  const reduced = device.reducedMotion;

  const depth = useTransform(scrollY, (y) => (reduced ? 0 : depthFor(index, y)));
  const scale = useTransform(depth, (d) => 1 - 0.028 * Math.min(d, 4));
  const rotateX = useTransform(depth, (d) => Math.min(d, 2) * 0.7);
  const dim = useTransform(depth, (d) => Math.min(0.5, d * 0.13));
  const lift = useTransform(depth, (d) => -Math.min(d, 4) * 2);

  const setRef = useCallback((el: HTMLDivElement | null) => register(index, el), [register, index]);

  return (
    <div
      ref={setRef}
      data-sticky-card={index}
      style={{
        position: isStack ? 'sticky' : 'relative',
        top: isStack ? layout.tops[index] ?? 88 : undefined,
        zIndex: index + 1,
        marginBottom: isLast ? 0 : layout.gap,
      }}
    >
      <motion.div
        initial={isStack ? false : { opacity: 0, y: 36 }}
        whileInView={isStack ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '0px 0px -12% 0px' }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        style={
          isStack
            ? { scale, rotateX, y: lift, transformPerspective: 1400, transformOrigin: '50% 0%' }
            : undefined
        }
        className={`relative overflow-hidden ${className}`}
      >
        {children}
        {isStack && (
          <motion.div
            aria-hidden="true"
            style={{ opacity: dim }}
            className="pointer-events-none absolute inset-0 z-30 rounded-[inherit] bg-[#07060d]"
          />
        )}
      </motion.div>
    </div>
  );
};

export const StickyCard: React.FC<StickyCardProps> = (props) => {
  const api = useContext(StackContext);
  if (!api) {
    // Used outside a StickyStack: degrade to a plain, fully visible card.
    return <div className={`relative mb-6 overflow-hidden ${props.className ?? ''}`}>{props.children}</div>;
  }
  return <StackedCard {...props} api={api} />;
};
