"use client";

import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type { StageId, StageStatus } from "@/lib/session";

interface ResearchNodeProps {
  id: StageId;
  label: string;
  caption: string;
  position: [number, number, number];
  status: StageStatus;
  isSelected: boolean;
  onSelect: (id: StageId) => void;
  accentColor: string;
}

export function ResearchNode({
  id,
  label,
  caption,
  position,
  status,
  isSelected,
  onSelect,
  accentColor,
}: ResearchNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  // Compute base color based on stage status
  const nodeColor = useMemo(() => {
    switch (status) {
      case "error":
        return "#f85149";
      case "running":
        return "#38bdf8";
      case "done":
        return accentColor;
      default:
        return "#475569";
    }
  }, [status, accentColor]);

  // Subtle pulsing animation on frame
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (meshRef.current) {
      if (status === "running") {
        const pulse = 1 + Math.sin(t * 4) * 0.12;
        meshRef.current.scale.set(pulse, pulse, pulse);
      } else if (hovered || isSelected) {
        meshRef.current.scale.set(1.15, 1.15, 1.15);
      } else {
        meshRef.current.scale.set(1, 1, 1);
      }
    }

    if (ringRef.current) {
      ringRef.current.rotation.z = t * 0.8;
      ringRef.current.rotation.x = Math.sin(t * 0.5) * 0.3;
    }
  });

  return (
    <group position={position}>
      {/* Selection / Active Ring */}
      {(isSelected || status === "running") && (
        <mesh ref={ringRef}>
          <ringGeometry args={[0.55, 0.62, 32]} />
          <meshBasicMaterial
            color={isSelected ? "#00f0ff" : nodeColor}
            side={THREE.DoubleSide}
            transparent
            opacity={isSelected ? 0.9 : 0.5}
          />
        </mesh>
      )}

      {/* Main Node Sphere */}
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(id);
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
        <sphereGeometry args={[0.36, 24, 24]} />
        <meshStandardMaterial
          color={nodeColor}
          emissive={nodeColor}
          emissiveIntensity={
            isSelected
              ? 1.2
              : status === "running"
              ? 1.5
              : status === "done"
              ? 0.7
              : hovered
              ? 0.5
              : 0.15
          }
          roughness={0.25}
          metalness={0.7}
          transparent
          opacity={status === "idle" && !hovered && !isSelected ? 0.65 : 1}
        />
      </mesh>

      {/* Outer Glow Halo for active/selected nodes */}
      {(status === "running" || isSelected || status === "done") && (
        <mesh scale={status === "running" ? [1.4, 1.4, 1.4] : [1.25, 1.25, 1.25]}>
          <sphereGeometry args={[0.36, 16, 16]} />
          <meshBasicMaterial
            color={nodeColor}
            transparent
            opacity={status === "running" ? 0.22 : isSelected ? 0.18 : 0.08}
            wireframe
          />
        </mesh>
      )}

      {/* 3D HTML Label */}
      <Html
        position={[0, -0.65, 0]}
        center
        distanceFactor={14}
        style={{ pointerEvents: "none" }}
      >
        <div
          className={`node-label-3d ${status} ${isSelected ? "selected" : ""} ${
            hovered ? "hovered" : ""
          }`}
        >
          <div className="node-label-header">
            <span className={`node-status-dot ${status}`} />
            <span className="node-title">{label}</span>
          </div>
          <div className="node-caption">{caption}</div>
        </div>
      </Html>
    </group>
  );
}
