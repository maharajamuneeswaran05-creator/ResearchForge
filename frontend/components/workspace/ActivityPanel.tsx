"use client";

import { useMemo, useState } from "react";
import { useWorkflow, type StageId } from "@/lib/session";

export function ActivityPanel() {
  const { logs, clearLogs, retryStage, busy } = useWorkflow();
  const [expanded, setExpanded] = useState(false);
  const [filter, setFilter] = useState<"all" | "error" | "info" | "success">("all");

  const filteredLogs = useMemo(() => {
    if (filter === "all") return logs;
    return logs.filter((l) => l.type === filter);
  }, [logs, filter]);

  const errorCount = useMemo(
    () => logs.filter((l) => l.type === "error").length,
    [logs]
  );

  return (
    <div
      className={`activity-panel ${expanded ? "expanded" : "collapsed"}`}
      aria-label="Workflow Activity & Execution Logs"
    >
      {/* Panel Header Bar */}
      <div
        className="activity-bar"
        onClick={() => setExpanded(!expanded)}
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setExpanded(!expanded);
        }}
      >
        <div className="activity-bar-left">
          <span className={`status-indicator ${busy ? "busy" : "idle"}`} />
          <span className="activity-title">Live Activity & Execution Stream</span>
          <span className="log-count-badge">{logs.length} events</span>
          {errorCount > 0 && (
            <span className="error-count-badge">{errorCount} errors</span>
          )}
        </div>

        <div className="activity-bar-right" onClick={(e) => e.stopPropagation()}>
          {expanded && (
            <div className="filter-group">
              <button
                type="button"
                className={`filter-btn ${filter === "all" ? "active" : ""}`}
                onClick={() => setFilter("all")}
              >
                All
              </button>
              <button
                type="button"
                className={`filter-btn ${filter === "error" ? "active" : ""}`}
                onClick={() => setFilter("error")}
              >
                Errors
              </button>
              <button
                type="button"
                className={`filter-btn ${filter === "success" ? "active" : ""}`}
                onClick={() => setFilter("success")}
              >
                Success
              </button>
              <button
                type="button"
                className="filter-btn clear-btn"
                onClick={clearLogs}
                title="Clear activity log"
              >
                Clear
              </button>
            </div>
          )}

          <button
            type="button"
            className="toggle-expand-btn"
            onClick={() => setExpanded(!expanded)}
            aria-label={expanded ? "Collapse activity panel" : "Expand activity panel"}
          >
            {expanded ? "▾ Minimize" : "▴ Expand Logs"}
          </button>
        </div>
      </div>

      {/* Expanded Content Area */}
      {expanded && (
        <div className="activity-drawer">
          {filteredLogs.length === 0 ? (
            <div className="activity-empty">
              <span>No logged events matching current filter.</span>
            </div>
          ) : (
            <div className="activity-log-list">
              {filteredLogs.map((entry) => (
                <div key={entry.id} className={`activity-row ${entry.type}`}>
                  <span className="row-time">{entry.timestamp}</span>
                  <span className={`row-badge ${entry.type}`}>{entry.type}</span>
                  {entry.stageId && (
                    <span className="row-stage">[{entry.stageId}]</span>
                  )}
                  <span className="row-message">{entry.message}</span>

                  {entry.type === "error" &&
                    entry.stageId &&
                    entry.stageId !== "system" && (
                      <button
                        type="button"
                        className="retry-inline-btn"
                        onClick={() => void retryStage(entry.stageId as StageId)}
                        title={`Retry ${entry.stageId}`}
                      >
                        Retry
                      </button>
                    )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
