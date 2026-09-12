import React, { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

interface SeabedMeshProps {
  size?: number;
  segments?: number;
}

export const SeabedMesh: React.FC<SeabedMeshProps> = ({
  size = 40,
  segments = 48,
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const { geometry, colors } = useMemo(() => {
    const geom = new THREE.PlaneGeometry(size, size, segments, segments);
    const pos = geom.attributes.position;
    const colorArray = new Float32Array(pos.count * 3);

    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);

      // Procedural bathymetric terrain: gentle sea mounts + sand ripples
      const mound = Math.sin(x * 0.15) * Math.cos(y * 0.15) * 1.8;
      const ripple = Math.sin(x * 0.6) * 0.25;
      const elevation = mound + ripple;

      pos.setZ(i, elevation);

      // Color mapping from deep ocean blue (#065A82) to teal (#1C7293)
      const normZ = (elevation + 2.5) / 5.0; // 0 to 1
      const r = 0.02 + normZ * 0.1;
      const g = 0.25 + normZ * 0.45;
      const b = 0.5 + normZ * 0.45;

      colorArray[i * 3] = r;
      colorArray[i * 3 + 1] = g;
      colorArray[i * 3 + 2] = b;
    }

    geom.setAttribute('color', new THREE.BufferAttribute(colorArray, 3));
    geom.computeVertexNormals();

    return { geometry: geom, colors: colorArray };
  }, [size, segments]);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    groupRef.current.position.y = -2 + Math.sin(clock.elapsedTime * 0.38) * 0.08;
    groupRef.current.rotation.z = Math.sin(clock.elapsedTime * 0.16) * 0.008;
  });

  return (
    <group ref={groupRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, -2, 0]}>
      {/* Solid Bathymetric Seabed */}
      <mesh geometry={geometry} receiveShadow>
        <meshStandardMaterial
          vertexColors
          roughness={0.8}
          metalness={0.15}
          emissive="#063C5A"
          emissiveIntensity={0.18}
          wireframe={false}
        />
      </mesh>

      {/* Bathymetric Depth Contour Wireframe Overlay */}
      <mesh geometry={geometry} position={[0, 0, 0.02]}>
        <meshBasicMaterial
          color="#22D3EE"
          wireframe
          opacity={0.18}
          transparent
        />
      </mesh>
    </group>
  );
};
