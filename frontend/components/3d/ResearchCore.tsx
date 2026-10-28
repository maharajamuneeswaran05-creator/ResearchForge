"use client";

import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";

interface ResearchCoreProps {
  question: string;
  busy: boolean;
  isSelected: boolean;
  onSelect: () => void;
  doneCount: number;
  totalStages: number;
}

export function ResearchCore({
  question,
  busy,
  isSelected,
  onSelect,
  doneCount,
  totalStages,
}: ResearchCoreProps) {
  const innerRef = useRef<THREE.Mesh>(null);
  const outerCageRef = useRef<THREE.Mesh>(null);
  const ringRef1 = useRef<THREE.Mesh>(null);
  const ringRef2 = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  // Core color shifts to violet when busy, emerald when all done, cyan otherwise
  const coreColor = useMemo(() => {
    if (busy) return "#a855f7"; // violet
    if (doneCount === totalStages && totalStages > 0) return "#10b981"; // emerald
    return "#00f0ff"; // bright cyan
  }, [busy, doneCount, totalStages]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();

    if (innerRef.current) {
      const pulseSpeed = busy ? 3.5 : 1.2;
      const scale = 1 + Math.sin(t * pulseSpeed) * (busy ? 0.08 : 0.03);
      innerRef.current.scale.set(scale, scale, scale);
    }

    if (outerCageRef.current) {
      outerCageRef.current.rotation.y = t * 0.25;
      outerCageRef.current.rotation.x = t * 0.15;
    }

    if (ringRef1.current) {
      ringRef1.current.rotation.z = -t * 0.4;
      ringRef1.current.rotation.y = Math.sin(t * 0.3) * 0.2;
    }

    if (ringRef2.current) {
      ringRef2.current.rotation.z = t * 0.35;
      ringRef2.current.rotation.x = Math.cos(t * 0.25) * 0.3;
    }
  });

  const labelText = question
    ? question.length > 55
      ? `${question.slice(0, 55)}\u2026`
      : question
    : "Idle \u2014 Enter Research Question";

  return (
    <group position={[0, 0, 0]}>
      {/* Outer Rotating Gyroscope Rings */}
      <mesh ref={ringRef1}>
        <ringGeometry args={[1.1, 1.15, 48]} />
        <meshBasicMaterial
          color={coreColor}
          side={THREE.DoubleSide}
          transparent
          opacity={0.35}
        />
      </mesh>

      <mesh ref={ringRef2}>
        <ringGeometry args={[1.35, 1.4, 48]} />
        <meshBasicMaterial
          color="#8b5cf6"
          side={THREE.DoubleSide}
          transparent
          opacity={0.25}
        />
      </mesh>

      {/* Outer Wireframe Geodesic Cage */}
      <mesh ref={outerCageRef}>
        <icosahedronGeometry args={[0.92, 1]} />
        <meshBasicMaterial
          color={coreColor}
          wireframe
          transparent
          opacity={hovered || isSelected ? 0.5 : 0.25}
        />
      </mesh>

      {/* Main Core Solid Sphere */}
      <mesh
        ref={innerRef}
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHovered(false);
          document.body.style.cursor = "auto";
        }}
      >
        <sphereGeometry args={[0.62, 32, 32]} />
        <meshStandardMaterial
          color={coreColor}
          emissive={coreColor}
          emissiveIntensity={busy ? 1.8 : hovered || isSelected ? 1.4 : 0.9}
          roughness={0.15}
          metalness={0.8}
        />
      </mesh>

      {/* Point Light emitted from core */}
      <pointLight color={coreColor} intensity={2.2} distance={8} />

      {/*
        3D Text Labels via troika-three-text (<Text> from drei).
        Unlike <Html>, <Text> renders entirely in WebGL — it does NOT create a
        separate React portal root, so it cannot trigger the React 19 race:
        "Attempted to synchronously unmount a root while React was already rendering."
      */}
      <Text
        position={[0, -1.28, 0]}
        fontSize={0.13}
        color={busy ? "#a855f7" : "#00f0ff"}
        anchorX="center"
        anchorY="middle"
        letterSpacing={0.1}
        outlineWidth={0.006}
        outlineColor="#080b12"
      >
        {"\u25CF RESEARCH CORE"}
      </Text>

      <Text
        position={[0, -1.55, 0]}
        fontSize={0.115}
        color="#e2e8f0"
        anchorX="center"
        anchorY="middle"
        maxWidth={4.2}
        textAlign="center"
        outlineWidth={0.005}
        outlineColor="#080b12"
      >
        {labelText}
      </Text>

      <Text
        position={[0, -1.83, 0]}
        fontSize={0.105}
        color="#64748b"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.003}
        outlineColor="#080b12"
      >
        {`${doneCount} / ${totalStages} Stages Complete`}
      </Text>
    </group>
  );
}
