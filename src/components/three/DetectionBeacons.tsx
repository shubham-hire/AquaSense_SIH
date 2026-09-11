import React, { useRef, useLayoutEffect } from 'react';
import * as THREE from 'three';
import { Detection } from '../../types';
import { Html } from '@react-three/drei';

interface DetectionBeaconsProps {
  detections: Detection[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export const DetectionBeacons: React.FC<DetectionBeaconsProps> = ({
  detections,
  selectedId,
  onSelect,
}) => {
  const meshRef = useRef<THREE.InstancedMesh | null>(null);

  // Filter located vs unlocated
  const locatedDetections = detections.filter((d) => d.position.kind === 'located');
  const unlocatedDetections = detections.filter((d) => d.position.kind === 'unlocated');

  useLayoutEffect(() => {
    if (!meshRef.current) return;

    const dummy = new THREE.Object3D();
    const color = new THREE.Color();

    locatedDetections.forEach((detection, idx) => {
      // Map normalized coordinates into local 3D coordinate space (-15 to 15)
      const x = ((detection.boundingBox.x % 500) / 500) * 24 - 12;
      const z = ((detection.boundingBox.y % 400) / 400) * 24 - 12;
      const y = -1.5; // Seabed elevation height

      dummy.position.set(x, y + 1.2, z);
      dummy.scale.set(0.6, 2.4, 0.6);
      dummy.updateMatrix();

      meshRef.current?.setMatrixAt(idx, dummy.matrix);

      // Color mapping
      if (detection.threatLevel === 'CRITICAL') {
        color.set('#B23A2E');
      } else if (detection.threatLevel === 'HIGH') {
        color.set('#C97A1E');
      } else if (detection.threatLevel === 'MEDIUM') {
        color.set('#C9A227');
      } else {
        color.set('#4C8C5B');
      }

      meshRef.current?.setColorAt(idx, color);
    });

    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true;
    }
  }, [locatedDetections]);

  return (
    <group>
      {/* Instanced Beacons for Located Seafloor Detections */}
      {locatedDetections.length > 0 && (
        <instancedMesh
          ref={meshRef}
          args={[undefined, undefined, locatedDetections.length]}
          onClick={(e) => {
            e.stopPropagation();
            if (e.instanceId !== undefined && locatedDetections[e.instanceId]) {
              onSelect(locatedDetections[e.instanceId].id);
            }
          }}
        >
          <cylinderGeometry args={[0.3, 0.05, 2, 8]} />
          <meshStandardMaterial
            roughness={0.2}
            metalness={0.6}
            emissive="#1C7293"
            emissiveIntensity={0.4}
          />
        </instancedMesh>
      )}

      {/* Floating Refusal Markers on Sea Surface Plane for Unlocated Detections */}
      {unlocatedDetections.map((detection, idx) => (
        <group key={detection.id} position={[-8 + idx * 4, 3, 8]}>
          <mesh>
            <octahedronGeometry args={[0.6]} />
            <meshStandardMaterial
              color="#64748B"
              wireframe
              emissive="#94A3B8"
              emissiveIntensity={0.5}
            />
          </mesh>
          <Html distanceFactor={18}>
            <div className="bg-slate-950/90 border border-rose-500/60 rounded px-1.5 py-0.5 text-[9px] font-mono text-rose-300 whitespace-nowrap shadow-lg">
              UNLOCATED: REFUSED
            </div>
          </Html>
        </group>
      ))}
    </group>
  );
};
