"use client";

import Link from "next/link";
import { useState } from "react";
import { STAGES, useWorkflow, type StageId } from "@/lib/session";

interface LeftSidebarProps {
  onNewResearch: () => void;
  onSelectStage: (id: string) => void;
  activeStageId: string;
}

export function LeftSidebar({
  onNewResearch,
  onSelectStage,
  activeStageId,
}: LeftSidebarProps) {
  const {
    state,
    busy,
    runRemaining,
    providerStatus,
    checkProviders,
    recentSessions,
    loadDemoData,
    beginResearch,
  } = useWorkflow();

  const [showSettings, setShowSettings] = useState(false);

  const hasRun = Boolean(state.question || state.gap || state.code);
  const hasRemaining = Boolean(
    (state.code && !state.result) ||
      (state.gap && !state.critique) ||
      (state.question && !state.report)
  );

  return (
    <aside className="hybrid-sidebar" aria-label="Research Navigation Sidebar">
      {/* Branding */}
      <div className="sidebar-brand-box">
        <Link href="/" className="brand-link">
          <span className="brand-logo-gem">R</span>
          <div className="brand-titles">
            <span className="brand-name">ResearchForge</span>
            <span className="brand-version">v0.1.0 • 3D Hybrid</span>
          </div>
        </Link>
      </div>

      {/* Primary Actions */}
      <div className="sidebar-actions-cluster">
        <button
          type="button"
          className="btn primary full-width"
          onClick={onNewResearch}
        >
          + New Research
        </button>

        <button
          type="button"
          className="btn ghost full-width sm"
          onClick={loadDemoData}
          title="Load precomputed research workflow to test the interface"
        >
          Load Demo Dataset
        </button>
      </div>

      {/* Navigation Stage Progress Tracker */}
      <div className="sidebar-nav-section">
        <div className="sidebar-section-header">
          <span>WORKFLOW STAGES</span>
          <span className="count-tag">
            {Object.values(state.stages).filter((s) => s.status === "done").length}/8
          </span>
        </div>

        <nav className="stage-nav-list" role="navigation">
          {/* Core button */}
          <button
            type="button"
            className={`stage-nav-item core-item ${
              activeStageId === "core" ? "active" : ""
            }`}
            onClick={() => onSelectStage("core")}
          >
            <span className="stage-num-badge core">●</span>
            <span className="stage-name-wrap">
              <strong>Research Core</strong>
              <span className="stage-sub-text">Question & Hub</span>
            </span>
          </button>

          {STAGES.map((stage, idx) => {
            const status = state.stages[stage.id].status;
            const isSelected = activeStageId === stage.id;
            return (
              <button
                key={stage.id}
                type="button"
                className={`stage-nav-item ${status} ${isSelected ? "active" : ""}`}
                onClick={() => onSelectStage(stage.id)}
              >
                <span className={`stage-num-badge ${status}`}>
                  {status === "done" ? "✓" : status === "error" ? "✕" : idx + 1}
                </span>
                <span className="stage-name-wrap">
                  <strong>{stage.label}</strong>
                  <span className="stage-sub-text">{stage.caption}</span>
                </span>
                {status === "running" && <span className="nav-spinner" />}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Pipeline Status Action */}
      <div className="sidebar-pipeline-footer">
        <button
          type="button"
          className="btn primary full-width sm"
          disabled={!hasRun || !hasRemaining || busy}
          onClick={() => void runRemaining()}
        >
          {busy
            ? "Executing..."
            : hasRemaining
            ? "Continue Pipeline"
            : "Pipeline Complete"}
        </button>
      </div>

      {/* Recent Sessions */}
      {recentSessions.length > 0 && (
        <div className="sidebar-recent-section">
          <div className="sidebar-section-header">
            <span>RECENT QUESTIONS</span>
          </div>
          <ul className="recent-list">
            {recentSessions.slice(0, 4).map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className="recent-item-btn"
                  onClick={() => void beginResearch(s.question)}
                  title={s.question}
                >
                  <span className="recent-q">
                    {s.question.length > 42
                      ? `${s.question.slice(0, 42)}…`
                      : s.question}
                  </span>
                  <span className="recent-date">{s.timestamp}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Provider Status & Settings */}
      <div className="sidebar-provider-box">
        <div className="provider-header">
          <span>SYSTEM PROVIDERS</span>
          <button
            type="button"
            className="refresh-providers-btn"
            onClick={() => void checkProviders()}
            title="Refresh connectivity"
          >
            ↻
          </button>
        </div>

        <div className="provider-item">
          <span className={`dot-status ${providerStatus.backend}`} />
          <span className="provider-label">FastAPI Backend</span>
          <span className="provider-val">{providerStatus.backend}</span>
        </div>

        <div className="provider-item">
          <span className={`dot-status ${providerStatus.nebius}`} />
          <span className="provider-label">Nebius AI</span>
          <span className="provider-val">{providerStatus.nebius}</span>
        </div>

        <button
          type="button"
          className="settings-toggle-link"
          onClick={() => setShowSettings(!showSettings)}
        >
          {showSettings ? "Hide details" : "Connection details ▾"}
        </button>

        {showSettings && (
          <div className="settings-drawer-inline">
            <div className="setting-prop">
              <span className="k">Target Host:</span>
              <span className="v">/backend (Port 8000)</span>
            </div>
            <div className="setting-prop">
              <span className="k">Nebius Model:</span>
              <span className="v">
                {providerStatus.nebiusModel || "Nemotron-4-340B"}
              </span>
            </div>
            <div className="setting-prop">
              <span className="k">Search Engine:</span>
              <span className="v">Tavily API</span>
            </div>
            <div className="setting-prop">
              <span className="k">Backend Status:</span>
              <span className="v">{providerStatus.backendDetails || "OK"}</span>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
