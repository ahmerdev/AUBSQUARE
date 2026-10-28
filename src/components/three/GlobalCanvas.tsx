import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { useDeviceProfile, useIdleReady } from '../../lib/device';
import { subscribeScroll } from '../../lib/scrollBus';
import { SceneBoundary } from '../../lib/SceneBoundary';

// The whole three.js stack is code-split: it is only downloaded after first paint, when the browser is idle.
const BackgroundScene = lazy(() => import('./BackgroundScene'));

/**
 * Fixed, non-interactive background layer shared by every page.
 *  - Layer 1: CSS ambient light blobs whose position/opacity follow scroll progress (--p).
 *    These are the graceful fallback when WebGL is unavailable / still loading / reduced motion.
 *  - Layer 2: the shared WebGL scene (lazy).
 *  - Layer 3: readability vignette so copy always stays dominant over 3D.
 */
export const GlobalCanvas: React.FC = () => {
  const device = useDeviceProfile();
  const idle = useIdleReady(1600);
  const [failed, setFailed] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let last = -1;
    return subscribeScroll((s) => {
      if (Math.abs(s.progress - last) < 0.0008) return;
      last = s.progress;
      rootRef.current?.style.setProperty('--p', s.progress.toFixed(4));
    });
  }, []);

  const showWebGL = idle && device.webgl && !failed;

  return (
    <div
      ref={rootRef}
      aria-hidden="true"
      className="fixed inset-0 z-0 pointer-events-none overflow-hidden"
      style={{ ['--p' as string]: 0 }}
    >
      {/* Scroll-linked ambient lights (cheap, GPU-composited transforms only) */}
      <div
        className="absolute -top-[8%] -left-[8%] w-[70vmax] h-[70vmax] max-w-[760px] max-h-[760px] rounded-full blur-[110px] md:blur-[150px] opacity-[0.20]"
        style={{
          background: 'radial-gradient(circle, #EC008C 0%, transparent 70%)',
          transform: 'translate3d(calc(var(--p) * 22vw), calc(var(--p) * 38vh), 0)',
        }}
      />
      <div
        className="absolute top-[30%] -right-[10%] w-[75vmax] h-[75vmax] max-w-[820px] max-h-[820px] rounded-full blur-[120px] md:blur-[160px] opacity-[0.20]"
        style={{
          background: 'radial-gradient(circle, #7B2FFF 0%, transparent 70%)',
          transform: 'translate3d(calc(var(--p) * -26vw), calc(var(--p) * -20vh), 0)',
        }}
      />
      <div
        className="absolute -bottom-[10%] left-[10%] w-[65vmax] h-[65vmax] max-w-[700px] max-h-[700px] rounded-full blur-[120px] md:blur-[150px] opacity-[0.18]"
        style={{
          background: 'radial-gradient(circle, #9333EA 0%, transparent 70%)',
          transform: 'translate3d(calc(var(--p) * 30vw), calc(var(--p) * -30vh), 0)',
        }}
      />

      {showWebGL && (
        <div className="absolute inset-0 opacity-[0.8] sm:opacity-[0.92] lg:opacity-100">
          <SceneBoundary onError={() => setFailed(true)}>
            <Suspense fallback={null}>
              <BackgroundScene device={device} />
            </Suspense>
          </SceneBoundary>
        </div>
      )}

      {/* Readability vignette: keeps foreground copy dominant */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(70% 55% at 50% 45%, rgba(11,11,18,0.55) 0%, rgba(11,11,18,0.2) 60%, transparent 100%)',
        }}
      />
    </div>
  );
};
