import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { getLenis } from '../../lib/lenisStore';

/** Resets scroll on route change (instant — the page transition provides the motion). */
export const ScrollToTop = () => {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (hash) return;
    const lenis = getLenis();
    if (lenis) lenis.scrollTo(0, { immediate: true, force: true });
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' as ScrollBehavior });
  }, [pathname, hash]);

  return null;
};
