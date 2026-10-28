import React, { useEffect } from 'react';
import Lenis from 'lenis';
import { setLenis } from '../../lib/lenisStore';
import { updateScrollState } from '../../lib/scrollBus';

interface SmoothScrollProps {
  children: React.ReactNode;
}

/**
 * Single smooth-scroll + scroll-state source of truth.
 * - Desktop: Lenis (wheel smoothing only; touch stays native for best mobile feel & battery).
 * - Reduced motion: no Lenis, native scrolling, but scroll state still published for 3D.
 */
export const SmoothScroll: React.FC<SmoothScrollProps> = ({ children }) => {
  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const onNativeScroll = () => updateScrollState(window.scrollY, 0);
    window.addEventListener('scroll', onNativeScroll, { passive: true });
    window.addEventListener('resize', onNativeScroll, { passive: true });
    onNativeScroll();

    if (reduced) {
      return () => {
        window.removeEventListener('scroll', onNativeScroll);
        window.removeEventListener('resize', onNativeScroll);
      };
    }

    const lenis = new Lenis({
      duration: 1.05,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
      wheelMultiplier: 1,
      syncTouch: false,
    });
    setLenis(lenis);

    lenis.on('scroll', (l: Lenis) => updateScrollState(l.scroll, l.velocity));

    let rafId = 0;
    const raf = (time: number) => {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    };
    rafId = requestAnimationFrame(raf);

    // Layout can change after images/fonts load: keep Lenis' limits fresh.
    const ro = new ResizeObserver(() => lenis.resize());
    ro.observe(document.body);

    return () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      lenis.destroy();
      setLenis(null);
      window.removeEventListener('scroll', onNativeScroll);
      window.removeEventListener('resize', onNativeScroll);
    };
  }, []);

  return <>{children}</>;
};
