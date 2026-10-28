import type Lenis from 'lenis';

/** Shared handle on the single Lenis instance so modals/menus can pause smooth scroll. */
let instance: Lenis | null = null;
export const setLenis = (l: Lenis | null) => {
  instance = l;
};
export const getLenis = () => instance;
