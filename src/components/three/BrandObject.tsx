import React, { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Float, MeshTransmissionMaterial, Sparkles } from '@react-three/drei';
import * as THREE from 'three';
import { scrollState } from '../../lib/scrollBus';
import { pointer, bindPointer } from '../../lib/pointer';
import type { DeviceProfile } from '../../lib/device';
import { BRAND, makeSquareFrame } from './sceneUtils';

/**
 * Hero brand sculpture — "the AUB SQUARE gyroscope".
 *
 * Two nested bevelled square frames (the brand's square) counter-rotate around a faceted
 * magenta gem with a white-hot core. The outer frame is polished magenta metal, the inner
 * frame is violet glass (true transmission on capable devices, glossy translucent
 * physical material elsewhere). Lighting comes from the parent's Lightformer environment.
 *
 * Motion: autonomous slow drift + desktop pointer parallax + scroll choreography
 * (the sculpture turns, rises and recedes as the hero scrolls away).
 */
interface Props {
  device: DeviceProfile;
}

export const BrandObject: React.FC<Props> = ({ device }) => {
  const root = useRef<THREE.Group>(null);
  const outer = useRef<THREE.Mesh>(null);
  const inner = useRef<THREE.Mesh>(null);
  const gem = useRef<THREE.Group>(null);
  const core = useRef<THREE.Mesh>(null);
  const orbit = useRef<THREE.Group>(null);
  const still = device.reducedMotion;
  const highQuality = device.tier === 'high';

  const outerGeo = useMemo(() => makeSquareFrame(3.5, 2.78, 0.4, 0.66, highQuality ? 16 : 8), [highQuality]);
  const innerGeo = useMemo(() => makeSquareFrame(2.5, 2.0, 0.28, 0.46, highQuality ? 16 : 8), [highQuality]);
  useEffect(
    () => () => {
      outerGeo.dispose();
      innerGeo.dispose();
    },
    [outerGeo, innerGeo]
  );
  useEffect(() => {
    bindPointer();
  }, []);

  useFrame((state, dt) => {
    const d = Math.min(dt, 0.05);
    const t = state.clock.elapsedTime;
    const h = Math.min(1, Math.max(0, scrollState.y / Math.max(1, scrollState.viewportH * 0.95)));
    const px = still || device.coarsePointer ? 0 : pointer.x;
    const py = still || device.coarsePointer ? 0 : pointer.y;

    if (root.current) {
      const g = root.current;
      g.rotation.y = THREE.MathUtils.damp(g.rotation.y, px * 0.5 + h * 1.5 + (still ? 0.35 : Math.sin(t * 0.25) * 0.18), 3.5, d);
      g.rotation.x = THREE.MathUtils.damp(g.rotation.x, -py * 0.32 + h * 0.35, 3.5, d);
      g.position.y = THREE.MathUtils.damp(g.position.y, h * 0.7, 4, d);
      const s = 1 - h * 0.14;
      g.scale.setScalar(THREE.MathUtils.damp(g.scale.x, s, 4, d));
    }
    if (still) return;
    if (outer.current) {
      outer.current.rotation.z = t * 0.12 + h * 1.2;
      outer.current.rotation.y = Math.sin(t * 0.32) * 0.35;
    }
    if (inner.current) {
      inner.current.rotation.z = -t * 0.2 - h * 1.6;
      inner.current.rotation.x = Math.sin(t * 0.4) * 0.45;
    }
    if (gem.current) {
      gem.current.rotation.y = t * 0.5 + h * 2.2;
      gem.current.rotation.z = Math.sin(t * 0.6) * 0.12;
    }
    if (core.current) {
      const pulse = 1 + Math.sin(t * 2.1) * 0.06;
      core.current.scale.setScalar(pulse);
    }
    if (orbit.current) orbit.current.rotation.y = t * 0.35 + h * 3;
  });

  return (
    <group ref={root}>
      <Float speed={still ? 0 : 1.6} rotationIntensity={0.25} floatIntensity={0.6}>
        {/* Outer frame — polished magenta metal */}
        <mesh ref={outer} geometry={outerGeo}>
          <meshPhysicalMaterial
            color="#C4107F"
            metalness={0.95}
            roughness={0.16}
            clearcoat={1}
            clearcoatRoughness={0.05}
            envMapIntensity={1.7}
            emissive={BRAND.magenta}
            emissiveIntensity={0.14}
          />
        </mesh>

        {/* Inner frame — violet glass */}
        <mesh ref={inner} geometry={innerGeo}>
          {highQuality ? (
            <MeshTransmissionMaterial
              color="#8F5CFF"
              transmission={1}
              thickness={0.6}
              roughness={0.06}
              ior={1.35}
              chromaticAberration={0.05}
              anisotropicBlur={0.1}
              samples={4}
              resolution={512}
              backside={false}
              envMapIntensity={1.4}
              attenuationColor="#7B2FFF"
              attenuationDistance={2.2}
            />
          ) : (
            <meshPhysicalMaterial
              color="#8F5CFF"
              metalness={0.1}
              roughness={0.08}
              transparent
              opacity={0.55}
              clearcoat={1}
              envMapIntensity={1.4}
              emissive={BRAND.purple}
              emissiveIntensity={0.25}
            />
          )}
        </mesh>

        {/* Faceted gem + hot core */}
        <group ref={gem}>
          <mesh scale={[0.78, 1.12, 0.78]}>
            <octahedronGeometry args={[0.9, 0]} />
            <meshPhysicalMaterial
              color="#C2007A"
              metalness={0.85}
              roughness={0.22}
              clearcoat={1}
              clearcoatRoughness={0.1}
              envMapIntensity={1.35}
              emissive="#4A12B8"
              emissiveIntensity={0.18}
              flatShading
            />
          </mesh>
          <mesh ref={core} scale={0.2}>
            <icosahedronGeometry args={[0.8, 1]} />
            <meshBasicMaterial color="#FF9AD9" toneMapped={false} />
          </mesh>
        </group>

        {/* Orbiting tokens of creativity */}
        <group ref={orbit}>
          <mesh position={[2.35, 0.55, 0]}>
            <boxGeometry args={[0.2, 0.2, 0.2]} />
            <meshStandardMaterial color="#ffffff" metalness={0.9} roughness={0.12} emissive={BRAND.magenta} emissiveIntensity={0.5} />
          </mesh>
          <mesh position={[-2.25, -0.65, 0.45]}>
            <octahedronGeometry args={[0.18, 0]} />
            <meshStandardMaterial color={BRAND.purple} metalness={0.9} roughness={0.12} emissive={BRAND.purple} emissiveIntensity={0.7} />
          </mesh>
          <mesh position={[0.4, -2.3, -0.3]}>
            <sphereGeometry args={[0.13, 16, 12]} />
            <meshBasicMaterial color={BRAND.magenta} toneMapped={false} />
          </mesh>
        </group>
      </Float>

      {!still && (
        <>
          <Sparkles count={highQuality ? 46 : 22} scale={[6.5, 6.5, 3]} size={highQuality ? 2.6 : 2.2} speed={0.35} opacity={0.75} color="#EC008C" />
          <Sparkles count={highQuality ? 34 : 14} scale={[7, 7, 3]} size={2.2} speed={0.3} opacity={0.6} color="#9F7BFF" />
        </>
      )}
    </group>
  );
};
