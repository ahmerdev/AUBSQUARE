import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useReducedMotion } from 'framer-motion';

interface SnapCarouselProps {
  /** Accessible name for the carousel region. */
  label: string;
  /** Left-hand header content (title block / counter). Arrows are rendered on the right. */
  header?: React.ReactNode;
  children: React.ReactNode;
  /** Tailwind classes controlling how wide each slide is. */
  itemClassName?: string;
  className?: string;
}

/**
 * Native CSS scroll-snap carousel: touch / trackpad swipe works for free, fully keyboard- and
 * screen-reader-accessible, no JS drag math. Arrow buttons + dots are 44px touch targets.
 */
export const SnapCarousel: React.FC<SnapCarouselProps> = ({
  label,
  header,
  children,
  itemClassName = 'basis-[86%] xs:basis-[74%] sm:basis-[60%] md:basis-[calc((100%-1.5rem)/2)] lg:basis-[calc((100%-3rem)/3)]',
  className = '',
}) => {
  const track = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const items = React.Children.toArray(children);
  const [state, setState] = useState({ start: true, end: false, index: 0 });
  const raf = useRef(0);

  const update = useCallback(() => {
    const el = track.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    const slides = Array.from(el.children) as HTMLElement[];
    let index = 0;
    let best = Infinity;
    slides.forEach((s, i) => {
      const d = Math.abs(s.offsetLeft - el.scrollLeft - (parseFloat(getComputedStyle(el).scrollPaddingLeft) || 0));
      if (d < best) {
        best = d;
        index = i;
      }
    });
    setState((p) => {
      const next = { start: el.scrollLeft < 4, end: max <= 4 || el.scrollLeft >= max - 4, index };
      return p.start === next.start && p.end === next.end && p.index === next.index ? p : next;
    });
  }, []);

  useEffect(() => {
    const el = track.current;
    if (!el) return;
    const onScroll = () => {
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(update);
    };
    update();
    el.addEventListener('scroll', onScroll, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf.current);
      el.removeEventListener('scroll', onScroll);
      ro.disconnect();
    };
  }, [update, items.length]);

  const page = (dir: 1 | -1) => {
    const el = track.current;
    if (!el) return;
    el.scrollBy({ left: dir * el.clientWidth * 0.88, behavior: reduce ? 'auto' : 'smooth' });
  };

  const goTo = (i: number) => {
    const el = track.current;
    const slide = el?.children[i] as HTMLElement | undefined;
    if (!el || !slide) return;
    el.scrollTo({ left: slide.offsetLeft - (parseFloat(getComputedStyle(el).scrollPaddingLeft) || 0), behavior: reduce ? 'auto' : 'smooth' });
  };

  return (
    <div className={`relative w-full ${className}`} role="region" aria-roledescription="carousel" aria-label={label}>
      <div className="flex items-end justify-between gap-4 mb-6 sm:mb-8">
        <div className="min-w-0">{header}</div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => page(-1)}
            disabled={state.start}
            className="w-11 h-11 rounded-full glass-panel flex items-center justify-center text-white hover:border-aub-magenta transition-colors disabled:opacity-35 disabled:pointer-events-none active:scale-95"
            aria-label={`Previous ${label.toLowerCase()}`}
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            type="button"
            onClick={() => page(1)}
            disabled={state.end}
            className="w-11 h-11 rounded-full glass-panel flex items-center justify-center text-white hover:border-aub-magenta transition-colors disabled:opacity-35 disabled:pointer-events-none active:scale-95"
            aria-label={`Next ${label.toLowerCase()}`}
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div
        ref={track}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') {
            e.preventDefault();
            page(1);
          } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            page(-1);
          }
        }}
        data-lenis-prevent-touch
        className="no-scrollbar flex gap-4 sm:gap-6 overflow-x-auto snap-x snap-mandatory overscroll-x-contain scroll-pl-4 sm:scroll-pl-0 -mx-4 px-4 sm:mx-0 sm:px-0 pb-2 touch-pan-x touch-pan-y outline-none focus-visible:ring-2 focus-visible:ring-aub-magenta rounded-2xl"
        style={{ WebkitOverflowScrolling: 'touch' }}
      >
        {items.map((child, i) => (
          <div
            key={(child as React.ReactElement).key ?? i}
            className={`snap-start shrink-0 min-w-0 ${itemClassName}`}
            role="group"
            aria-roledescription="slide"
            aria-label={`${i + 1} of ${items.length}`}
          >
            {child}
          </div>
        ))}
      </div>

      {items.length > 1 && (
        <div className="mt-5 flex items-center justify-center gap-1" role="tablist" aria-label={`${label} pagination`}>
          {items.map((_, i) => (
            <button
              key={i}
              type="button"
              role="tab"
              aria-selected={i === state.index}
              aria-label={`Go to slide ${i + 1}`}
              onClick={() => goTo(i)}
              className="h-6 w-6 flex items-center justify-center"
            >
              <span className={`block h-2 rounded-full transition-all duration-300 ${i === state.index ? 'w-7 bg-aub-magenta' : 'w-2 bg-aub-border'}`} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
