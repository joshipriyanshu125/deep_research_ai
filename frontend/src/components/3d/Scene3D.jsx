import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Stars, Float, MeshDistortMaterial, Sphere } from '@react-three/drei';
import * as THREE from 'three';

/* ─── Neural Network Nodes ─── */
function NeuralNetwork() {
  const groupRef = useRef();
  const linesRef = useRef();

  const { nodes, connections } = useMemo(() => {
    const count = 60;
    const pts = Array.from({ length: count }, () => ({
      x: (Math.random() - 0.5) * 28,
      y: (Math.random() - 0.5) * 16,
      z: (Math.random() - 0.5) * 10,
    }));

    const conns = [];
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        const dx = pts[i].x - pts[j].x;
        const dy = pts[i].y - pts[j].y;
        const dz = pts[i].z - pts[j].z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < 6) conns.push([i, j, dist]);
      }
    }

    return { nodes: pts, connections: conns };
  }, []);

  // Build line segments geometry
  const lineGeometry = useMemo(() => {
    const positions = [];
    connections.forEach(([i, j]) => {
      positions.push(nodes[i].x, nodes[i].y, nodes[i].z);
      positions.push(nodes[j].x, nodes[j].y, nodes[j].z);
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    return geo;
  }, [nodes, connections]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.03;
      groupRef.current.rotation.x = Math.sin(t * 0.015) * 0.1;
    }
  });

  return (
    <group ref={groupRef}>
      {/* Connection lines */}
      <lineSegments ref={linesRef} geometry={lineGeometry}>
        <lineBasicMaterial
          color="#38BDF8"
          transparent
          opacity={0.12}
          fog={false}
        />
      </lineSegments>

      {/* Node spheres */}
      {nodes.map((n, i) => (
        <mesh key={i} position={[n.x, n.y, n.z]}>
          <sphereGeometry args={[0.06, 8, 8]} />
          <meshStandardMaterial
            color={i % 3 === 0 ? '#38BDF8' : i % 3 === 1 ? '#A855F7' : '#10B981'}
            emissive={i % 3 === 0 ? '#38BDF8' : i % 3 === 1 ? '#A855F7' : '#10B981'}
            emissiveIntensity={0.8}
            transparent
            opacity={0.7}
          />
        </mesh>
      ))}
    </group>
  );
}

/* ─── Floating Orb ─── */
function FloatingOrb({ position, color, speed = 1 }) {
  const meshRef = useRef();
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.elapsedTime * speed * 0.3;
      meshRef.current.rotation.z = state.clock.elapsedTime * speed * 0.2;
    }
  });

  return (
    <Float speed={speed} rotationIntensity={0.4} floatIntensity={0.6}>
      <mesh ref={meshRef} position={position}>
        <Sphere args={[1.2, 64, 64]}>
          <MeshDistortMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.25}
            distort={0.45}
            speed={2}
            roughness={0.1}
            metalness={0.8}
            transparent
            opacity={0.18}
            wireframe={false}
          />
        </Sphere>
      </mesh>
    </Float>
  );
}

/* ─── Rotating Ring ─── */
function Ring({ position, color }) {
  const ref = useRef();
  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.x = state.clock.elapsedTime * 0.4;
      ref.current.rotation.y = state.clock.elapsedTime * 0.2;
    }
  });

  return (
    <mesh ref={ref} position={position}>
      <torusGeometry args={[1.8, 0.025, 16, 100]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={1.5}
        transparent
        opacity={0.5}
      />
    </mesh>
  );
}

/* ─── Grid Floor ─── */
function GridPlane() {
  return (
    <gridHelper
      args={[80, 40, '#1E293B', '#0F172A']}
      position={[0, -8, 0]}
      rotation={[0, 0, 0]}
    />
  );
}

/* ─── Main Scene ─── */
export default function Scene3D() {
  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 0,
      pointerEvents: 'none',
    }}>
      <Canvas
        camera={{ position: [0, 0, 14], fov: 60 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        {/* Lighting */}
        <ambientLight intensity={0.3} />
        <pointLight position={[10, 10, 10]} color="#38BDF8" intensity={1.5} />
        <pointLight position={[-10, -10, -5]} color="#A855F7" intensity={1} />
        <pointLight position={[0, 5, -8]} color="#10B981" intensity={0.5} />

        {/* Stars background */}
        <Stars
          radius={120}
          depth={60}
          count={3000}
          factor={3}
          saturation={0.3}
          fade
          speed={0.4}
        />

        {/* Neural Network */}
        <NeuralNetwork />

        {/* Floating orbs */}
        <FloatingOrb position={[-7, 2, -3]} color="#38BDF8" speed={0.8} />
        <FloatingOrb position={[7, -2, -4]} color="#A855F7" speed={1.2} />
        <FloatingOrb position={[0, 4, -6]} color="#10B981" speed={0.6} />

        {/* Rings */}
        <Ring position={[-6, -1, -2]} color="#38BDF8" />
        <Ring position={[6, 2, -3]} color="#A855F7" />

        {/* Grid */}
        <GridPlane />
      </Canvas>
    </div>
  );
}
