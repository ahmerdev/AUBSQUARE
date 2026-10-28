import React from 'react';
import { Canvas } from '@react-three/fiber';
import { Environment, Lightformer, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import { BrandObject } from './BrandObject';
import type { DeviceProfile } from '../../lib/device';
import { BRAND } from './sceneUtils';

interface Props {
  device: DeviceProfile;
  active: boolean; // false ⇒ hero is off-screen ⇒ stop rendering
  onReady: () => void;
}

/** Lazy-loaded WebGL canvas for the hero (kept separate so three.js stays out of the first-paint bundle). */
const HeroCanvas: React.FC<Props> = ({ device, active, onReady }) => {
  const still = device.reducedMotion;
  const frameloop = !active ? 'never' : still ? 'demand' : 'always';
  // OrbitControls forces `touch-action: none`, which would trap page scroll on phones — mouse/trackpad only.
  const allowOrbit = !device.coarsePointer && !still;

  return (
    <Canvas
      camera={{ position: [0, 0, 11], fov: 38 }}
      dpr={[1, Math.min(device.dpr, 1.75)]}
      frameloop={frameloop}
      gl={{ antialias: device.tier !== 'low', alpha: true, powerPreference: 'high-performance', stencil: false }}
      style={{ touchAction: 'pan-y' }}
      className={allowOrbit ? 'cursor-grab active:cursor-grabbing' : ''}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.1;
        onReady();
      }}
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[5, 6, 5]} intensity={1.6} />
      <pointLight position={[-6, -3, 3]} intensity={70} distance={24} decay={2} color={BRAND.magenta} />
      <pointLight position={[6, 4, -2]} intensity={60} distance={24} decay={2} color={BRAND.purple} />

      <Environment resolution={128} frames={1}>
        <Lightformer form="rect" intensity={2.6} color={BRAND.magenta} position={[-5, 1, 2]} scale={[7, 2.2, 1]} />
        <Lightformer form="rect" intensity={2.2} color={BRAND.purple} position={[5, -1, 2]} scale={[6, 2.2, 1]} />
        <Lightformer form="rect" intensity={1.8} color="#ffffff" position={[0, 5, 3]} scale={[8, 1.6, 1]} />
        <Lightformer form="ring" intensity={1.2} color={BRAND.lavender} position={[0, 0, -5]} scale={7} />
      </Environment>

      <BrandObject device={device} />

      {allowOrbit && (
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          enableDamping
          dampingFactor={0.06}
          maxPolarAngle={Math.PI / 1.7}
          minPolarAngle={Math.PI / 2.6}
          rotateSpeed={0.55}
        />
      )}
    </Canvas>
  );
};

export default HeroCanvas;
