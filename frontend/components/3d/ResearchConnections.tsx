"use client";

import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { StageId, StageStatus } from "@/lib/session";

interface NodePositionMap {
  id: StageId;
  position: [number, number, number];
  status: StageStatus;
}

interface ResearchConnectionsProps {
  nodes: NodePositionMap[];
  busy: boolean;
}

export function ResearchConnections({ nodes, busy }: ResearchConnectionsProps) {
  const particlesRef = useRef<THREE.Points>(null);

  // Generate line geometry connecting Core (0,0,0) to each stage node
  const radialLines = useMemo(() => {
    return nodes.map((node) => {
      const start = new THREE.Vector3(0, 0, 0);
      const end = new THREE.Vector3(...node.position);
      const points = [start, end];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);

      const isDone = node.status === "done";
      const isRunning = node.status === "running";
      const isError = node.status === "error";

      const color = isError
        ? "#f85149"
        : isRunning
        ? "#00f0ff"
        : isDone
        ? "#0284c7"
        : "#1e293b";

      const opacity = isRunning ? 0.9 : isDone ? 0.45 : 0.18;

      return { id: node.id, geometry, color, opacity };
    });
  }, [nodes]);

  // Generate sequence perimeter line (connecting 1 -> 2 -> 3 ... -> 8 -> 1)
  const perimeterGeometry = useMemo(() => {
    if (nodes.length < 2) return null;
    const points = nodes.map((n) => new THREE.Vector3(...n.position));
    points.push(new THREE.Vector3(...nodes[0].position)); // loop
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [nodes]);

  // Particle data-flow stream along connections
  const particleCount = 64;
  const particlePositions = useMemo(() => {
    const arr = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 6;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 3;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 6;
    }
    return arr;
  }, [particleCount]);

  // Animate particles moving along orbits / radial vectors
  useFrame(({ clock }) => {
    if (!particlesRef.current || nodes.length === 0) return;
    const t = clock.getElapsedTime();
    const pos = particlesRef.current.geometry.attributes.position as THREE.BufferAttribute;
    const array = pos.array as Float32Array;

    for (let i = 0; i < particleCount; i++) {
      const nodeIndex = i % nodes.length;
      const target = nodes[nodeIndex].position;
      const speed = busy ? 1.6 : 0.7;
      const progress = ((t * speed * 0.4 + (i / particleCount)) % 1);

      // Interpolate from center to target node
      array[i * 3] = target[0] * progress;
      array[i * 3 + 1] = target[1] * progress + Math.sin(t * 2 + i) * 0.08;
      array[i * 3 + 2] = target[2] * progress;
    }
    pos.needsUpdate = true;
  });

  return (
    <group>
      {/* Radial Spokes from Core */}
      {radialLines.map((line) => (
        <primitive
          key={`spoke-${line.id}`}
          object={
            new THREE.Line(
              line.geometry,
              new THREE.LineBasicMaterial({
                color: line.color,
                transparent: true,
                opacity: line.opacity,
              })
            )
          }
        />
      ))}

      {/* Orbit Perimeter Ring */}
      {perimeterGeometry && (
        <primitive
          object={
            new THREE.Line(
              perimeterGeometry,
              new THREE.LineBasicMaterial({
                color: busy ? "#8b5cf6" : "#334155",
                transparent: true,
                opacity: busy ? 0.4 : 0.2,
              })
            )
          }
        />
      )}

      {/* Flowing Data Particles */}
      <points ref={particlesRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[particlePositions, 3]}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.06}
          color={busy ? "#00f0ff" : "#38bdf8"}
          transparent
          opacity={busy ? 0.85 : 0.45}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}
