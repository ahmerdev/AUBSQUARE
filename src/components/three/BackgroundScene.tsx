import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, Lightformer, PerformanceMonitor } from '@react-three/drei';
import * as THREE from 'three';
import { scrollState } from '../../lib/scrollBus';
import { pointer, bindPointer } from '../../lib/pointer';
import { DeviceProfile } from '../../lib/device';
import { BRAND, makeSoftDot, makeSquareFrame, sampleStops } from './sceneUtils';

/**
 * ONE shared, scroll-driven "fly-through" for the whole site.
 *
 * Scrolling pilots a camera forward through a winding tunnel of glowing AUB-SQUARE gates.
 * Glossy sculptures hang beside the flight path and swing past at close range, warp-streaks
 * stretch with your scroll SPEED (scroll fast = hyperspace, stop = they settle), the camera
 * banks into the curves, the FOV kicks on speed and the light re-tints magenta → violet → purple.
 * Scroll back up and you fly backwards through the same tunnel.
 *
 * Everything reads the shared scroll store inside useFrame — no React re-renders.
 */

const TRAVEL = 150; // world units flown across the full page
const FOV = 48;
const FAR = 90;

const pathX = (z: number) => Math.sin(z * 0.045) * 2.6 + Math.sin(z * 0.017 + 1) * 1.8;
const pathY = (z: number) => Math.cos(z * 0.038) * 1.5 + Math.sin(z * 0.011) * 0.8;

// Smoothed state shared between rig, gates, sculptures, streaks
const fly = { p: 0, z: 0, speed: 0, lastY: 0, kick: 0 };

interface Props {
  device: DeviceProfile;
}

/* ------------------------------------------------------------------ */
/* Camera rig                                                           */
/* ------------------------------------------------------------------ */
const CameraRig: React.FC<{ still: boolean }> = ({ still }) => {
  const roll = useRef(0);
  const target = useMemo(() => new THREE.Vector3(), []);
  useFrame((state, dt) => {
    const d = Math.min(dt, 0.05);
    const cam = state.camera as THREE.PerspectiveCamera;
    const vh = Math.max(1, scrollState.viewportH);

    // scroll speed in "screens per second" (works for touch + wheel because it is derived from y)
    const inst = (scrollState.y - fly.lastY) / Math.max(d, 1 / 120) / vh;
    fly.lastY = scrollState.y;
    fly.speed = still ? 0 : THREE.MathUtils.damp(fly.speed, THREE.MathUtils.clamp(inst, -9, 9), 7, d);

    fly.p = still ? scrollState.progress : THREE.MathUtils.damp(fly.p, scrollState.progress, 3.6, d);
    fly.z = -fly.p * TRAVEL;

    const px = still ? 0 : pointer.x;
    const py = still ? 0 : pointer.y;
    const cx = pathX(fly.z) + px * 0.9;
    const cy = pathY(fly.z) + py * 0.55;
    cam.position.set(cx, cy, fly.z);

    // look down the path
    target.set(pathX(fly.z - 12) + px * 1.6, pathY(fly.z - 12) + py * 1.0, fly.z - 12);
    cam.lookAt(target);

    // bank into curves + a little extra on speed
    const curve = pathX(fly.z - 8) - pathX(fly.z);
    const wantRoll = still ? 0 : -curve * 0.1 + px * -0.05 + THREE.MathUtils.clamp(fly.speed, -4, 4) * 0.0;
    roll.current = THREE.MathUtils.damp(roll.current, wantRoll, 3, d);
    cam.rotateZ(roll.current);

    // FOV kick: fast scrolling opens the lens
    const wantFov = FOV + (still ? 0 : Math.min(Math.abs(fly.speed), 6) * 2.4);
    if (Math.abs(cam.fov - wantFov) > 0.05) {
      cam.fov = THREE.MathUtils.damp(cam.fov, wantFov, 6, d);
      cam.updateProjectionMatrix();
    }
  });
  return null;
};

/* ------------------------------------------------------------------ */
/* Lights that travel with the camera and re-tint with scroll           */
/* ------------------------------------------------------------------ */
const Lights: React.FC = () => {
  const a = useRef<THREE.PointLight>(null);
  const b = useRef<THREE.PointLight>(null);
  const key = useRef<THREE.DirectionalLight>(null);
  useFrame((state) => {
    const c = state.camera.position;
    if (a.current) {
      sampleStops(fly.p, a.current.color);
      a.current.position.set(c.x + 6, c.y + 3, c.z - 6);
    }
    if (b.current) {
      sampleStops(fly.p, b.current.color, true);
      b.current.position.set(c.x - 6, c.y - 3, c.z - 10);
    }
    if (key.current) key.current.position.set(c.x + 3, c.y + 6, c.z + 4);
  });
  return (
    <>
      <ambientLight intensity={0.3} />
      <directionalLight ref={key} intensity={0.9} color="#ffffff" />
      <pointLight ref={a} intensity={90} distance={40} decay={2} color={BRAND.magenta} />
      <pointLight ref={b} intensity={80} distance={40} decay={2} color={BRAND.purple} />
    </>
  );
};

/* ------------------------------------------------------------------ */
/* Gates — the brand square, over and over, spinning against each other  */
/* ------------------------------------------------------------------ */
const Gates: React.FC<{ count: number; frame: THREE.BufferGeometry; still: boolean }> = ({ count, frame, still }) => {
  const refs = useRef<(THREE.Mesh | null)[]>([]);
  const spacing = TRAVEL / count;
  const mats = useMemo(
    () =>
      [BRAND.magenta, BRAND.violet, BRAND.purple].map(
        (c) =>
          new THREE.MeshPhysicalMaterial({
            color: c,
            emissive: c,
            emissiveIntensity: 0.65,
            metalness: 0.55,
            roughness: 0.3,
            clearcoat: 1,
            clearcoatRoughness: 0.15,
            envMapIntensity: 1.0,
            transparent: true,
            opacity: 0.62,
          })
      ),
    []
  );
  useEffect(() => () => mats.forEach((m) => m.dispose()), [mats]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    for (let i = 0; i < count; i++) {
      const m = refs.current[i];
      if (!m) continue;
      const z = -(i + 1) * spacing - 3;
      const dir = i % 2 ? 1 : -1;
      m.position.set(pathX(z), pathY(z), z);
      // spin is tied to scroll position so the gates "unscrew" as you travel
      m.rotation.z = i * 0.62 + (still ? 0 : t * 0.07 * dir) + fly.p * 7 * dir;
      m.rotation.x = still ? 0 : Math.sin(t * 0.3 + i) * 0.05;
      // a gate "pulses" as the camera flies through it
      const near = Math.max(0, 1 - Math.abs(fly.z - z) / 14);
      m.scale.setScalar(1 + near * 0.18 * (still ? 0 : 1));
    }
  });

  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <mesh
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          geometry={frame}
          material={mats[i % 3]}
        />
      ))}
    </>
  );
};

/* ------------------------------------------------------------------ */
/* Sculptures swinging past the flight path                              */
/* ------------------------------------------------------------------ */
type Kind = 'octa' | 'knot' | 'square' | 'ico' | 'pearl' | 'dodeca';
interface SculptureDef {
  kind: Kind;
  color: string;
  emissive: string;
  glass?: boolean;
  spin: number;
}

const DEFS: SculptureDef[] = [
  { kind: 'octa', color: BRAND.magenta, emissive: BRAND.purple, glass: true, spin: 0.5 },
  { kind: 'knot', color: BRAND.violet, emissive: BRAND.magenta, spin: 0.4 },
  { kind: 'square', color: '#B0107F', emissive: BRAND.magenta, spin: 0.35 },
  { kind: 'ico', color: BRAND.purple, emissive: BRAND.violet, glass: true, spin: 0.45 },
  { kind: 'pearl', color: '#E9D8FF', emissive: BRAND.violet, spin: 0.2 },
  { kind: 'dodeca', color: BRAND.magenta, emissive: BRAND.purple, glass: true, spin: 0.4 },
  { kind: 'knot', color: BRAND.magenta, emissive: BRAND.violet, spin: 0.5 },
  { kind: 'octa', color: BRAND.purple, emissive: BRAND.magenta, spin: 0.45 },
];

const Sculptures: React.FC<{ count: number; frame: THREE.BufferGeometry; compact: boolean; still: boolean }> = ({
  count,
  frame,
  compact,
  still,
}) => {
  const refs = useRef<(THREE.Mesh | null)[]>([]);
  const items = useMemo(
    () =>
      DEFS.slice(0, count).map((d, i) => {
        const z = -16 - (i * (TRAVEL - 24)) / count;
        const side = i % 2 ? -1 : 1;
        return {
          d,
          z,
          side,
          off: (compact ? 2.7 : 4.6) + (i % 3) * 0.7,
          dy: ((i * 37) % 7) / 7 * 3.2 - 1.6,
          scale: (compact ? 1.0 : 1.5) + (i % 3) * 0.2,
          phase: i * 1.7,
        };
      }),
    [count, compact]
  );

  const materials = useMemo(
    () =>
      items.map(
        ({ d }) =>
          new THREE.MeshPhysicalMaterial({
            color: d.color,
            emissive: d.emissive,
            emissiveIntensity: d.glass ? 0.3 : 0.38,
            metalness: d.glass ? 0.25 : 0.92,
            roughness: d.glass ? 0.08 : 0.2,
            clearcoat: 1,
            clearcoatRoughness: 0.08,
            transparent: !!d.glass,
            opacity: d.glass ? 0.7 : 1,
            envMapIntensity: 1.3,
          })
      ),
    [items]
  );
  useEffect(() => () => materials.forEach((m) => m.dispose()), [materials]);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    const boost = 1 + Math.min(Math.abs(fly.speed), 6) * 0.9;
    items.forEach((it, i) => {
      const m = refs.current[i];
      if (!m) return;
      const cx = pathX(it.z);
      const cy = pathY(it.z);
      const bob = still ? 0 : Math.sin(t * 0.7 + it.phase) * 0.3;
      m.position.set(cx + it.side * it.off, cy + it.dy + bob, it.z);
      if (!still) {
        m.rotation.x += dt * it.d.spin * boost;
        m.rotation.y += dt * it.d.spin * 1.35 * boost;
      }
      // swell as the camera swings past (big dramatic near-pass)
      const near = Math.max(0, 1 - Math.abs(fly.z - it.z) / 16);
      m.scale.setScalar(it.scale * (1 + near * near * 0.55));
    });
  });

  const geo = (k: Kind) => {
    switch (k) {
      case 'octa':
        return <octahedronGeometry args={[1, 0]} />;
      case 'knot':
        return <torusKnotGeometry args={[0.8, 0.22, 140, 16]} />;
      case 'ico':
        return <icosahedronGeometry args={[1, 0]} />;
      case 'pearl':
        return <sphereGeometry args={[0.9, 32, 24]} />;
      case 'dodeca':
        return <dodecahedronGeometry args={[1, 0]} />;
      default:
        return null;
    }
  };

  return (
    <>
      {items.map(({ d }, i) => (
        <mesh
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          geometry={d.kind === 'square' ? frame : undefined}
          material={materials[i]}
        >
          {geo(d.kind)}
        </mesh>
      ))}
    </>
  );
};

/* ------------------------------------------------------------------ */
/* Warp streaks — length is driven by scroll speed                       */
/* ------------------------------------------------------------------ */
const Streaks: React.FC<{ count: number; still: boolean }> = ({ count, still }) => {
  const { obj, heads, geo, mat } = useMemo(() => {
    const positions = new Float32Array(count * 6);
    const colors = new Float32Array(count * 6);
    const heads = new Float32Array(count * 3);
    const palette = [new THREE.Color(BRAND.magenta), new THREE.Color(BRAND.lavender), new THREE.Color('#ffffff'), new THREE.Color(BRAND.purple)];
    for (let i = 0; i < count; i++) {
      const z = 12 - Math.random() * (TRAVEL + 40);
      const ang = Math.random() * Math.PI * 2;
      const rad = 2.4 + Math.pow(Math.random(), 0.7) * 12;
      const x = pathX(z) + Math.cos(ang) * rad;
      const y = pathY(z) + Math.sin(ang) * rad * 0.7;
      heads.set([x, y, z], i * 3);
      const c = palette[(Math.random() * palette.length) | 0];
      // head bright, tail black ⇒ additive fade-out
      colors.set([c.r, c.g, c.b, 0, 0, 0], i * 6);
      positions.set([x, y, z, x, y, z - 0.6], i * 6);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const obj = new THREE.LineSegments(geo, mat);
    obj.frustumCulled = false;
    return { obj, heads, geo, mat };
  }, [count]);

  useEffect(
    () => () => {
      geo.dispose();
      mat.dispose();
    },
    [geo, mat]
  );

  useFrame(() => {
    const pos = geo.getAttribute('position') as THREE.BufferAttribute;
    const arr = pos.array as Float32Array;
    const sp = still ? 0 : fly.speed;
    const len = 0.35 + Math.min(Math.abs(sp), 7) * 1.7;
    const dir = sp >= 0 ? 1 : -1; // flying forward ⇒ tail trails behind (toward -z)
    for (let i = 0; i < count; i++) {
      const hz = heads[i * 3 + 2];
      arr[i * 6 + 5] = hz - len * dir;
    }
    pos.needsUpdate = true;
    mat.opacity = 0.45 + Math.min(Math.abs(sp), 5) * 0.1;
  });

  return <primitive object={obj} />;
};

/* ------------------------------------------------------------------ */
/* Dust + bokeh along the whole tunnel                                   */
/* ------------------------------------------------------------------ */
const Dust: React.FC<{ count: number; size: number; opacity: number; radius: [number, number]; tex: THREE.Texture }> = ({
  count,
  size,
  opacity,
  radius,
  tex,
}) => {
  const [pos, col] = useMemo(() => {
    const p = new Float32Array(count * 3);
    const c = new Float32Array(count * 3);
    const palette = [new THREE.Color(BRAND.magenta), new THREE.Color(BRAND.purple), new THREE.Color(BRAND.lavender), new THREE.Color('#ffffff')];
    const w = [0.38, 0.72, 0.94, 1];
    for (let i = 0; i < count; i++) {
      const z = 10 - Math.random() * (TRAVEL + 40);
      const ang = Math.random() * Math.PI * 2;
      const rad = radius[0] + Math.random() * (radius[1] - radius[0]);
      p[i * 3] = pathX(z) + Math.cos(ang) * rad;
      p[i * 3 + 1] = pathY(z) + Math.sin(ang) * rad * 0.75;
      p[i * 3 + 2] = z;
      const r = Math.random();
      const tint = palette[w.findIndex((x) => r <= x)];
      c.set([tint.r, tint.g, tint.b], i * 3);
    }
    return [p, c];
  }, [count, radius]);

  return (
    <points frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[pos, 3]} />
        <bufferAttribute attach="attributes-color" args={[col, 3]} />
      </bufferGeometry>
      <pointsMaterial
        map={tex}
        size={size}
        sizeAttenuation
        vertexColors
        transparent
        opacity={opacity}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
};

/* ------------------------------------------------------------------ */
/* Scene + canvas                                                        */
/* ------------------------------------------------------------------ */
const Scene: React.FC<{ device: DeviceProfile; level: number }> = ({ device, level }) => {
  const tier = device.tier;
  const still = device.reducedMotion;
  const compact = device.isMobile;
  const tex = useMemo(() => makeSoftDot(), []);
  const frame = useMemo(() => makeSquareFrame(17, 15.3, 0.4, 2.2, tier === 'high' ? 14 : 8), [tier]);
  useEffect(
    () => () => {
      tex.dispose();
      frame.dispose();
    },
    [tex, frame]
  );

  const eff = Math.min(2, (tier === 'high' ? 0 : tier === 'mid' ? 1 : 2) + level);
  const gates = eff === 0 ? 20 : eff === 1 ? 14 : 9;
  const objects = eff === 0 ? 8 : eff === 1 ? 6 : 4;
  const streaks = eff === 0 ? 420 : eff === 1 ? 230 : 90;
  const dust = eff === 0 ? 700 : eff === 1 ? 380 : 160;
  const bokeh = eff === 0 ? 22 : eff === 1 ? 12 : 0;

  useEffect(() => {
    bindPointer();
  }, []);

  return (
    <>
      <fog attach="fog" args={[BRAND.bg, 14, 58]} />
      <CameraRig still={still} />
      <Lights />
      <Environment resolution={64} frames={1}>
        <Lightformer form="rect" intensity={3.2} color={BRAND.magenta} position={[-5, 2, -4]} scale={[9, 3, 1]} />
        <Lightformer form="rect" intensity={2.6} color={BRAND.purple} position={[5, -2, -3]} scale={[7, 3, 1]} />
        <Lightformer form="ring" intensity={1.8} color="#ffffff" position={[0, 6, -6]} scale={6} />
      </Environment>

      <Gates count={gates} frame={frame} still={still} />
      <Sculptures count={objects} frame={frame} compact={compact} still={still} />
      <Streaks count={streaks} still={still} />
      <Dust count={dust} size={0.16} opacity={0.8} radius={[1.5, 15]} tex={tex} />
      {bokeh > 0 && <Dust count={bokeh} size={3} opacity={0.08} radius={[5, 15]} tex={tex} />}
    </>
  );
};

const BackgroundScene: React.FC<Props> = ({ device }) => {
  const [level, setLevel] = useState(0);
  const dpr = level > 0 ? 1 : device.dpr;

  return (
    <Canvas
      className="!absolute inset-0"
      camera={{ position: [0, 0, 0], fov: FOV, near: 0.4, far: FAR }}
      dpr={[1, Math.min(dpr, 1.75)]}
      frameloop={device.reducedMotion ? 'demand' : 'always'}
      gl={{
        antialias: device.tier === 'high',
        alpha: true,
        powerPreference: device.tier === 'high' ? 'high-performance' : 'low-power',
        stencil: false,
      }}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.1;
      }}
    >
      <PerformanceMonitor onDecline={() => setLevel((l) => Math.min(2, l + 1))} flipflops={2} />
      <Scene device={device} level={level} />
    </Canvas>
  );
};

export default BackgroundScene;
