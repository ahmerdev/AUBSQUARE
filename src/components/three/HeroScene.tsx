import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { Sparkles as SparklesIcon, Layers } from 'lucide-react';
import { ThreeFallback } from './ThreeFallback';
import { SceneBoundary } from '../../lib/SceneBoundary';
import { useDeviceProfile, useIdleReady } from '../../lib/device';
import { useProjects } from '../../context/CmsContext';

const HeroCanvas = lazy(() => import('./HeroCanvas'));

/**
 * Hero 3D installation.
 * - Text/CTAs are never blocked: the WebGL canvas loads lazily after idle behind a lightweight glow placeholder.
 * - Rendering pauses when scrolled out of view (IntersectionObserver).
 * - Desktop: pointer parallax on the floating DOM layers + orbit drag. Touch: autonomous motion + scroll choreography,
 *   and the canvas never intercepts vertical page scrolling.
 * - No WebGL / context failure: the original CSS 3D brand card fallback.
 */
export const HeroScene: React.FC = () => {
  const projectsData = useProjects();
  const device = useDeviceProfile();
  const idle = useIdleReady(900);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const [visible, setVisible] = useState(true);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = boxRef.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: '80px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // Pointer parallax for the floating DOM layers (fine pointers only)
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 90, damping: 18, mass: 0.6 });
  const sy = useSpring(my, { stiffness: 90, damping: 18, mass: 0.6 });
  const badgeA = { x: useTransform(sx, (v) => v * -14), y: useTransform(sy, (v) => v * -10) };
  const badgeB = { x: useTransform(sx, (v) => v * 18), y: useTransform(sy, (v) => v * 12) };
  const card = { x: useTransform(sx, (v) => v * 26), y: useTransform(sy, (v) => v * -18), rotateY: useTransform(sx, (v) => -10 + v * 8) };

  useEffect(() => {
    if (device.coarsePointer || device.reducedMotion) return;
    const el = boxRef.current;
    if (!el) return;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      mx.set(((e.clientX - r.left) / r.width - 0.5) * 2);
      my.set(((e.clientY - r.top) / r.height - 0.5) * 2);
    };
    const onLeave = () => {
      mx.set(0);
      my.set(0);
    };
    el.addEventListener('pointermove', onMove, { passive: true });
    el.addEventListener('pointerleave', onLeave);
    return () => {
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
    };
  }, [device.coarsePointer, device.reducedMotion, mx, my]);

  if (!device.webgl || failed) {
    return <ThreeFallback />;
  }

  const preview = projectsData[0];
  const dragHint = device.coarsePointer ? 'Interactive 3D · Scroll to Explore' : 'Interactive 3D · Drag & Rotate';

  return (
    <div
      ref={boxRef}
      className="relative w-full h-[360px] xs:h-[400px] sm:h-[500px] lg:h-[580px] select-none flex items-center justify-center"
      style={{ touchAction: 'pan-y' }}
    >
      {/* Volumetric-style glows behind the sculpture */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 sm:w-80 h-64 sm:h-80 bg-aub-magenta/25 blur-[90px] sm:blur-[110px] pointer-events-none rounded-full" />
      <div className="absolute top-[38%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-60 sm:w-72 h-60 sm:h-72 bg-aub-purple/30 blur-[100px] sm:blur-[120px] pointer-events-none rounded-full" />

      {/* Placeholder mark while the 3D chunk streams in (never blocks content) */}
      <div
        aria-hidden="true"
        className={`absolute inset-0 flex items-center justify-center transition-opacity duration-700 ${ready ? 'opacity-0' : 'opacity-100'}`}
      >
        <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-3xl border border-aub-magenta/40 bg-gradient-to-br from-[#1E173D] to-[#0B0B12] flex items-center justify-center shadow-glow-magenta/40 animate-pulse-slow">
          <span className="font-display font-black text-2xl text-white tracking-tight">
            <span className="text-gradient">A</span>UB
          </span>
        </div>
      </div>

      {idle && (
        <div className={`absolute inset-0 transition-opacity duration-1000 ${ready ? 'opacity-100' : 'opacity-0'}`}>
          <SceneBoundary onError={() => setFailed(true)}>
            <Suspense fallback={null}>
              <HeroCanvas device={device} active={visible} onReady={() => setReady(true)} />
            </Suspense>
          </SceneBoundary>
        </div>
      )}

      {/* Floating glass badges in spatial depth (decorative; never overlap CTAs — they live in the visual column) */}
      <motion.div
        style={{ x: badgeA.x, y: badgeA.y }}
        className="absolute top-3 left-0 sm:top-8 sm:left-2 z-20 pointer-events-none"
      >
        <motion.div
          animate={device.reducedMotion ? undefined : { y: [-8, 8, -8] }}
          transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
          className="px-3 py-2 rounded-2xl glass-panel border border-aub-magenta/40 flex items-center gap-2.5 shadow-glow-magenta/20"
        >
          <div className="w-7 h-7 rounded-lg bg-aub-gradient flex items-center justify-center text-white shrink-0">
            <SparklesIcon className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[11px] font-bold text-white block leading-tight">Identity Architecture</span>
            <span className="text-[9px] text-aub-accent-labels font-mono">Bespoke Vector DNA</span>
          </div>
        </motion.div>
      </motion.div>

      <motion.div
        style={{ x: badgeB.x, y: badgeB.y }}
        className="absolute bottom-14 right-0 sm:bottom-16 sm:right-2 z-20 pointer-events-none"
      >
        <motion.div
          animate={device.reducedMotion ? undefined : { y: [8, -8, 8] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
          className="px-3 py-2 rounded-2xl glass-panel border border-aub-purple/40 flex items-center gap-2.5 shadow-glow-purple/20"
        >
          <div className="w-7 h-7 rounded-lg bg-aub-card border border-aub-border flex items-center justify-center text-aub-purple shrink-0">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[11px] font-bold text-white block leading-tight">3D Web Experiences</span>
            <span className="text-[9px] text-aub-accent-labels font-mono">Real-time WebGL</span>
          </div>
        </motion.div>
      </motion.div>

      {/* Floating project preview (real portfolio thumbnail) */}
      {preview && (
        <motion.div
          style={{ x: card.x, y: card.y, rotateY: card.rotateY, rotateZ: 5, transformPerspective: 800 }}
          className="hidden sm:block absolute top-[14%] right-0 lg:-right-2 z-10 w-[132px] lg:w-[150px] pointer-events-none"
        >
          <div className="rounded-xl overflow-hidden border border-white/15 bg-aub-card/80 shadow-[0_18px_40px_-12px_rgba(236,0,140,0.45)] backdrop-blur-md">
            <img src={preview.thumbnail} alt="" loading="lazy" decoding="async" className="w-full h-[84px] lg:h-[92px] object-cover" />
            <div className="px-2.5 py-1.5">
              <span className="block text-[10px] font-bold text-white font-display truncate">{preview.title}</span>
              <span className="block text-[9px] text-aub-accent-labels font-mono truncate">{preview.category} · {preview.year}</span>
            </div>
          </div>
        </motion.div>
      )}

      <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 z-20 px-3.5 py-1.5 rounded-full bg-aub-card/90 border border-aub-border/90 flex items-center gap-2 shadow-lg backdrop-blur-md pointer-events-none whitespace-nowrap">
        <span className="w-2 h-2 rounded-full bg-aub-magenta animate-ping" />
        <span className="text-[11px] text-aub-accent-labels font-medium font-mono">{dragHint}</span>
      </div>
    </div>
  );
};
