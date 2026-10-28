"use client";

import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

import { useWorkflow, STAGES, type StageId } from "@/lib/session";
import { ResearchCore } from "./ResearchCore";
import { ResearchNode } from "./ResearchNode";
import { ResearchConnections } from "./ResearchConnections";
import { ResearchFallback2D } from "./ResearchFallback2D";

// Stage 3D Coordinates
const STAGE_POSITIONS: Record<StageId, [number, number, number]> = {
  evidence: [-3.8, 0.6, 1.8],
  gap: [-2.6, -0.6, 3.5],
  hypothesis: [0.2, 1.0, 4.2],
  experiment: [3.2, 0.4, 2.8],
  execution: [4.2, -0.8, -0.6],
  results: [2.8, 0.9, -3.2],
  critic: [-0.8, -1.0, -4.0],
  report: [-3.5, 0.6, -2.2],
};

const STAGE_ACCENTS: Record<StageId, string> = {
  evidence: "#00f0ff", // cyan
  gap: "#14b8a6", // teal
  hypothesis: "#a855f7", // violet
  experiment: "#6366f1", // indigo
  execution: "#3b82f6", // blue
  results: "#10b981", // emerald
  critic: "#f59e0b", // amber
  report: "#ec4899", // pink/rose
};

interface WebGLErrorBoundaryProps {
  children: ReactNode;
  fallback: ReactNode;
}

interface WebGLErrorBoundaryState {
  hasError: boolean;
}

class WebGLErrorBoundary extends Component<
  WebGLErrorBoundaryProps,
  WebGLErrorBoundaryState
> {
  constructor(props: WebGLErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.warn("WebGL Scene encountered an error, falling back to 2D:", error);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

export function ResearchScene() {
  const { state, busy, selectedNodeId, setSelectedNodeId } = useWorkflow();
  const [autoRotate, setAutoRotate] = useState(true);
  const [viewMode, setViewMode] = useState<"3d" | "2d">("3d");
  const [webglSupported, setWebglSupported] = useState(true);
  const controlsRef = useRef<OrbitControlsImpl>(null);

  // Detect WebGL capability on mount
  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      const gl =
        canvas.getContext("webgl2") ||
        canvas.getContext("webgl") ||
        canvas.getContext("experimental-webgl");
      if (!gl) {
        setWebglSupported(false);
        setViewMode("2d");
      }
    } catch {
      setWebglSupported(false);
      setViewMode("2d");
    }

    // Respect reduced motion
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      setAutoRotate(false);
    }
  }, []);

  const doneCount = useMemo(() => {
    return Object.values(state.stages).filter((s) => s.status === "done").length;
  }, [state.stages]);

  const nodeMap = useMemo(() => {
    return STAGES.map((s) => ({
      id: s.id,
      position: STAGE_POSITIONS[s.id],
      status: state.stages[s.id].status,
    }));
  }, [state.stages]);

  function handleResetCamera() {
    if (controlsRef.current) {
      controlsRef.current.reset();
    }
  }

  function handleFocusActiveNode() {
    const activeStage = STAGES.find(
      (s) => state.stages[s.id].status === "running"
    );
    if (activeStage) {
      setSelectedNodeId(activeStage.id);
    } else {
      setSelectedNodeId("core");
    }
    handleResetCamera();
  }

  if (!webglSupported || viewMode === "2d") {
    return (
      <div className="research-scene-wrapper">
        <ResearchFallback2D
          selectedNodeId={selectedNodeId}
          onSelectNode={(id) => setSelectedNodeId(id)}
        />
        {webglSupported && (
          <div className="scene-floating-bar">
            <button
              type="button"
              className="scene-control-btn active"
              onClick={() => setViewMode("3d")}
              title="Switch to 3D View"
            >
              Switch to 3D Orbit
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="research-scene-wrapper">
      <WebGLErrorBoundary
        fallback={
          <ResearchFallback2D
            selectedNodeId={selectedNodeId}
            onSelectNode={(id) => setSelectedNodeId(id)}
          />
        }
      >
        <Canvas
          camera={{ position: [0, 4.5, 9.5], fov: 48 }}
          dpr={[1, 2]}
          gl={{
            antialias: true,
            alpha: true,
            powerPreference: "high-performance",
          }}
          className="webgl-canvas"
        >
          <color attach="background" args={["#080b12"]} />
          <fog attach="fog" args={["#080b12", 12, 30]} />

          <ambientLight intensity={0.65} />
          <directionalLight position={[10, 16, 12]} intensity={1.1} />
          <directionalLight position={[-10, -10, -10]} intensity={0.3} />

          <Suspense fallback={null}>
            {/* Center Core */}
            <ResearchCore
              question={state.question}
              busy={busy}
              isSelected={selectedNodeId === "core"}
              onSelect={() => setSelectedNodeId("core")}
              doneCount={doneCount}
              totalStages={STAGES.length}
            />

            {/* Stage Nodes */}
            {STAGES.map((stage) => (
              <ResearchNode
                key={stage.id}
                id={stage.id}
                label={stage.label}
                caption={stage.caption}
                position={STAGE_POSITIONS[stage.id]}
                status={state.stages[stage.id].status}
                isSelected={selectedNodeId === stage.id}
                onSelect={(id) => setSelectedNodeId(id)}
                accentColor={STAGE_ACCENTS[stage.id]}
              />
            ))}

            {/* Connections & Data Particles */}
            <ResearchConnections nodes={nodeMap} busy={busy} />

            {/* Camera Controls */}
            <OrbitControls
              ref={controlsRef}
              enableDamping
              dampingFactor={0.06}
              minDistance={4}
              maxDistance={22}
              maxPolarAngle={Math.PI / 1.7}
              autoRotate={autoRotate}
              autoRotateSpeed={0.5}
            />
          </Suspense>
        </Canvas>
      </WebGLErrorBoundary>

      {/* Floating Interactive HUD Controls */}
      <div className="scene-floating-bar" role="toolbar" aria-label="3D View Controls">
        <button
          type="button"
          className="scene-control-btn"
          onClick={handleResetCamera}
          title="Reset Camera Angle"
        >
          Reset Camera
        </button>

        <button
          type="button"
          className={`scene-control-btn ${autoRotate ? "active" : ""}`}
          onClick={() => setAutoRotate(!autoRotate)}
          title="Toggle Ambient Rotation"
        >
          {autoRotate ? "Rotate: On" : "Rotate: Paused"}
        </button>

        <button
          type="button"
          className="scene-control-btn"
          onClick={handleFocusActiveNode}
          title="Focus on Active / Core Stage"
        >
          Focus Active
        </button>

        <button
          type="button"
          className="scene-control-btn mode-switch"
          onClick={() => setViewMode("2d")}
          title="Toggle 2D Topology Diagram"
        >
          2D Topology
        </button>
      </div>

      {/* Interactive Helper Legend */}
      <div className="scene-hint-badge">
        <span className="dot pulse" />
        <span>Click any node to inspect artefacts • Drag to orbit • Scroll to zoom</span>
      </div>
    </div>
  );
}
