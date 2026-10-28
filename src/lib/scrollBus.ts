/**
 * Tiny framework-free scroll store. SmoothScroll (Lenis) writes to it once per frame;
 * 3D scenes read it inside useFrame — so scroll never triggers a React re-render.
 */
export interface ScrollState {
  y: number; // px
  max: number; // max scrollable px
  progress: number; // 0..1 of whole document
  velocity: number; // px/frame-ish (signed)
  direction: 1 | -1 | 0;
  viewportH: number;
}

export const scrollState: ScrollState = {
  y: 0,
  max: 1,
  progress: 0,
  velocity: 0,
  direction: 0,
  viewportH: typeof window !== 'undefined' ? window.innerHeight : 800,
};

type Listener = (s: ScrollState) => void;
const listeners = new Set<Listener>();
/** Subscribe to scroll updates without React. Returns an unsubscribe fn. */
export const subscribeScroll = (cb: Listener) => {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
};

export const updateScrollState = (y: number, velocity = 0) => {
  const doc = document.documentElement;
  const max = Math.max(1, doc.scrollHeight - window.innerHeight);
  scrollState.y = y;
  scrollState.max = max;
  scrollState.progress = Math.min(1, Math.max(0, y / max));
  scrollState.velocity = velocity;
  scrollState.direction = velocity > 0.1 ? 1 : velocity < -0.1 ? -1 : 0;
  scrollState.viewportH = window.innerHeight;
  listeners.forEach((l) => l(scrollState));
};
