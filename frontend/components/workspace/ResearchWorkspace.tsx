"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { STAGES, useWorkflow } from "@/lib/session";
import { LeftSidebar } from "./LeftSidebar";
import { ResearchInspector } from "./ResearchInspector";
import { ActivityPanel } from "./ActivityPanel";

// Dynamic import for WebGL 3D Scene to prevent SSR hydration issues
const DynamicResearchScene = dynamic(
  () =>
    import("@/components/3d/ResearchScene").then((mod) => mod.ResearchScene),
  {
    ssr: false,
    loading: () => (
      <div className="scene-loading-placeholder">
        <span className="spinner" />
        <span style={{ marginTop: 12, color: "var(--text-muted)" }}>
          Initializing 3D Research Canvas...
        </span>
      </div>
    ),
  }
);

export function ResearchWorkspace() {
  const router = useRouter();
  const {
    state,
    busy,
    selectedNodeId,
    setSelectedNodeId,
    beginResearch,
    reset,
  } = useWorkflow();

  const [inputQuestion, setInputQuestion] = useState("");
  const [mobileTab, setMobileTab] = useState<"scene" | "inspector" | "stages">("scene");

  function handleNewResearch() {
    reset();
    setInputQuestion("");
    setSelectedNodeId("core");
  }

  async function handleStartResearch(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const q = (inputQuestion.trim() || state.question).trim();
    if (!q || busy) return;
    await beginResearch(q);
  }

  return (
    <div className="hybrid-workspace-shell">
      {/* Mobile Tab Selector (shown only on small screens) */}
      <div className="mobile-view-tabs" role="tablist">
        <button
          type="button"
          className={`mobile-tab ${mobileTab === "scene" ? "active" : ""}`}
          onClick={() => setMobileTab("scene")}
        >
          3D Canvas
        </button>
        <button
          type="button"
          className={`mobile-tab ${mobileTab === "inspector" ? "active" : ""}`}
          onClick={() => setMobileTab("inspector")}
        >
          Inspector
        </button>
        <button
          type="button"
          className={`mobile-tab ${mobileTab === "stages" ? "active" : ""}`}
          onClick={() => setMobileTab("stages")}
        >
          Workflow
        </button>
      </div>

      <div className="hybrid-workspace-layout">
        {/* Left Column: Navigation, Recent, Providers */}
        <div className={`workspace-col-sidebar ${mobileTab === "stages" ? "mobile-visible" : ""}`}>
          <LeftSidebar
            onNewResearch={handleNewResearch}
            onSelectStage={(id) => {
              setSelectedNodeId(id);
              setMobileTab("inspector");
            }}
            activeStageId={selectedNodeId}
          />
        </div>

        {/* Center Column: Question Bar, Stage Meter, 3D Graph, Activity Stream */}
        <div className={`workspace-col-main ${mobileTab === "scene" ? "mobile-visible" : ""}`}>
          {/* Top Quick Question Bar */}
          <div className="workspace-question-bar">
            <form className="question-bar-form" onSubmit={handleStartResearch}>
              <div className="input-with-icon">
                <span className="search-glyph">✦</span>
                <input
                  type="text"
                  placeholder="Enter or refine research question (e.g. Does X improve Y under Z?)..."
                  value={inputQuestion || state.question}
                  onChange={(e) => setInputQuestion(e.target.value)}
                  disabled={busy}
                  className="quick-question-input"
                />
              </div>

              <div className="quick-actions-row">
                <button
                  type="submit"
                  className="btn primary sm"
                  disabled={busy || !(inputQuestion.trim() || state.question.trim())}
                >
                  {busy ? (
                    <>
                      <span className="spinner" />
                      Running
                    </>
                  ) : state.question ? (
                    "Re-Run Research"
                  ) : (
                    "Start Research"
                  )}
                </button>
              </div>
            </form>

            {/* Compact Stage Progress Strip */}
            <div className="compact-stage-strip" role="list">
              {STAGES.map((stage) => {
                const status = state.stages[stage.id].status;
                const isSelected = selectedNodeId === stage.id;
                return (
                  <button
                    key={stage.id}
                    type="button"
                    role="listitem"
                    className={`strip-stage-item ${status} ${
                      isSelected ? "selected" : ""
                    }`}
                    onClick={() => {
                      setSelectedNodeId(stage.id);
                      setMobileTab("inspector");
                    }}
                    title={`${stage.label}: ${stage.caption} (${status})`}
                  >
                    <span className={`strip-dot ${status}`} />
                    <span className="strip-label">{stage.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Interactive 3D Canvas Viewport */}
          <div className="workspace-canvas-viewport">
            <DynamicResearchScene />
          </div>

          {/* Activity Logs Stream */}
          <ActivityPanel />
        </div>

        {/* Right Column: Node Inspector */}
        <div className={`workspace-col-inspector ${mobileTab === "inspector" ? "mobile-visible" : ""}`}>
          <ResearchInspector />
        </div>
      </div>
    </div>
  );
}
