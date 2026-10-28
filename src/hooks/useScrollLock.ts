import { useEffect } from 'react';
import { getLenis } from '../lib/lenisStore';

let locks = 0;

/**
 * Locks page scroll (body + Lenis) while `locked` is true. Reference-counted so
 * overlapping overlays (menu → quote modal) never unlock each other.
 */
export const useScrollLock = (locked: boolean) => {
  useEffect(() => {
    if (!locked) return;
    locks += 1;
    if (locks === 1) {
      const scrollbar = window.innerWidth - document.documentElement.clientWidth;
      document.documentElement.style.setProperty('--scrollbar-comp', `${scrollbar}px`);
      document.body.classList.add('scroll-locked');
      getLenis()?.stop();
    }
    return () => {
      locks = Math.max(0, locks - 1);
      if (locks === 0) {
        document.body.classList.remove('scroll-locked');
        document.documentElement.style.removeProperty('--scrollbar-comp');
        getLenis()?.start();
      }
    };
  }, [locked]);
};
