"use client";

import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";

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

  // Core color shifts from cyan to bright violet when busy, or rich cyan when done
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

      {/* 3D HTML Label */}
      <Html
        position={[0, -1.2, 0]}
        center
        distanceFactor={14}
        style={{ pointerEvents: "none" }}
      >
        <div
          className={`core-label-3d ${isSelected ? "selected" : ""} ${
            busy ? "busy" : ""
          }`}
        >
          <div className="core-badge">
            <span className="core-pulse-dot" />
            RESEARCH CORE
          </div>
          <div className="core-title">
            {question ? (
              question.length > 55 ? `${question.slice(0, 55)}…` : question
            ) : (
              "Idle — Enter Research Question"
            )}
          </div>
          <div className="core-sub">
            {doneCount} / {totalStages} Stages Complete
          </div>
        </div>
      </Html>
    </group>
  );
}
