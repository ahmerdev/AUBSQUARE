import { useEffect, useState, useSyncExternalStore } from 'react';

/**
 * Device capability profile used to scale 3D / animation workloads.
 * Evaluated once (WebGL probe is not free) and re-read on resize for breakpoints.
 */
export type QualityTier = 'low' | 'mid' | 'high';

export interface DeviceProfile {
  reducedMotion: boolean;
  webgl: boolean;
  isMobile: boolean; // < 768px
  isTablet: boolean; // 768 – 1023px
  coarsePointer: boolean;
  tier: QualityTier;
  dpr: number; // max DPR the 3D scenes should use
}

let webglProbe: boolean | null = null;
export const hasWebGL = (): boolean => {
  if (webglProbe !== null) return webglProbe;
  if (typeof document === 'undefined') return false;
  try {
    const canvas = document.createElement('canvas');
    const gl = (canvas.getContext('webgl2') || canvas.getContext('webgl')) as WebGLRenderingContext | null;
    webglProbe = !!gl;
    // Release the probe context immediately so it does not count against the browser's context limit.
    gl?.getExtension('WEBGL_lose_context')?.loseContext();
  } catch {
    webglProbe = false;
  }
  return webglProbe;
};

const compute = (): DeviceProfile => {
  if (typeof window === 'undefined') {
    return { reducedMotion: false, webgl: false, isMobile: false, isTablet: false, coarsePointer: false, tier: 'mid', dpr: 1 };
  }
  const w = window.innerWidth;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const coarsePointer = window.matchMedia('(pointer: coarse)').matches;
  const isMobile = w < 768;
  const isTablet = w >= 768 && w < 1024;
  const cores = (navigator as Navigator & { hardwareConcurrency?: number }).hardwareConcurrency ?? 4;
  const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 4;
  const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData === true;

  let tier: QualityTier = 'high';
  if (isMobile || coarsePointer || cores <= 4 || mem <= 4) tier = 'mid';
  if ((isMobile && (cores <= 4 || mem <= 3)) || saveData || reducedMotion) tier = 'low';

  const dpr = tier === 'low' ? 1 : tier === 'mid' ? Math.min(window.devicePixelRatio || 1, 1.5) : Math.min(window.devicePixelRatio || 1, 2);
  return { reducedMotion, webgl: hasWebGL(), isMobile, isTablet, coarsePointer, tier, dpr };
};

let cached: DeviceProfile | null = null;
const listeners = new Set<() => void>();

const refresh = () => {
  const next = compute();
  if (!cached || JSON.stringify(next) !== JSON.stringify(cached)) {
    cached = next;
    listeners.forEach((l) => l());
  }
};

let bound = false;
const bind = () => {
  if (bound || typeof window === 'undefined') return;
  bound = true;
  let raf = 0;
  const onResize = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(refresh);
  };
  window.addEventListener('resize', onResize, { passive: true });
  window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener?.('change', refresh);
};

const subscribe = (cb: () => void) => {
  bind();
  listeners.add(cb);
  return () => listeners.delete(cb);
};
const getSnapshot = () => {
  if (!cached) cached = compute();
  return cached;
};

export const useDeviceProfile = (): DeviceProfile =>
  useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

/** True once the browser is idle — used to defer heavy WebGL work until after first paint. */
export const useIdleReady = (timeout = 1200): boolean => {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number; cancelIdleCallback?: (id: number) => void };
    let id: number;
    if (w.requestIdleCallback) {
      id = w.requestIdleCallback(() => setReady(true), { timeout });
      return () => w.cancelIdleCallback?.(id);
    }
    id = window.setTimeout(() => setReady(true), 250);
    return () => window.clearTimeout(id);
  }, [timeout]);
  return ready;
};
