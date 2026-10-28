"use client";

import { useWorkflow } from "@/lib/session";
import { Panel } from "@/components/ui/Panel";
import { ConfidenceMeter } from "@/components/ui/ConfidenceMeter";
import { EmptyState, LoadingState } from "@/components/ui/States";
import type { CriticItem } from "@/lib/types";

const SEVERITY_CLASS: Record<string, string> = {
  high: "error",
  medium: "warning",
  low: "idle",
};

function CritiqueList({
  title,
  items,
  empty,
}: {
  title: string;
  items: CriticItem[];
  empty: string;
}) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p style={{ color: "var(--text-faint)" }}>{empty}</p>
      ) : (
        <ul className="bullets">
          {items.map((item, index) => (
            <li key={`${item.category}-${index}`}>
              <span
                className={`pill ${SEVERITY_CLASS[item.severity] ?? "idle"}`}
                style={{ marginRight: 8, padding: "1px 7px", fontSize: 10.5 }}
              >
                {item.severity}
              </span>
              <span style={{ color: "var(--text)" }}>{item.finding}</span>
              <div style={{ color: "var(--text-faint)", fontSize: 11.5 }}>
                {item.category}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function CriticPanel() {
  const { state, busy, runCritique } = useWorkflow();
  const stage = state.stages.critic;
  const critique = state.critique;

  return (
    <Panel
      step={7}
      title="Research critic"
      caption="Adversarial review of the hypothesis and evidence"
      status={stage.status}
      error={stage.error}
      action={
        <button
          className="btn sm"
          onClick={() => void runCritique()}
          disabled={!state.gap || busy}
        >
          {stage.status === "running" ? (
            <>
              <span className="spinner" />
              Reviewing
            </>
          ) : (
            "Run critique"
          )}
        </button>
      }
    >
      {stage.status === "running" ? (
        <LoadingState label="The critic is challenging the current results…" />
      ) : !critique ? (
        <EmptyState>
          The critique runs against the hypothesis, plan and experiment results.
        </EmptyState>
      ) : (
        <div className="stack">
          <div className="grid-2">
            <div className="card">
              <h3>Verdict</h3>
              <p style={{ color: "var(--text)", fontSize: 13.5 }}>
                {critique.verdict}
              </p>
              <div style={{ marginTop: 12 }}>
                <span
                  className={`pill ${
                    critique.hypothesis_supported === null
                      ? "idle"
                      : critique.hypothesis_supported
                        ? "done"
                        : "error"
                  }`}
                >
                  <span className="dot" />
                  {critique.hypothesis_supported === null
                    ? "Hypothesis undetermined"
                    : critique.hypothesis_supported
                      ? "Hypothesis supported"
                      : "Hypothesis not supported"}
                </span>
              </div>
            </div>
            <div className="card">
              <h3>Critic confidence</h3>
              <ConfidenceMeter
                label="Confidence in the critique"
                value={critique.confidence_score}
                tone="violet"
                caption={`Reviewed by ${critique.model}`}
              />
            </div>
          </div>

          <div className="grid-2">
            <CritiqueList
              title="Strengths"
              items={critique.strengths}
              empty="No strengths identified."
            />
            <CritiqueList
              title="Weaknesses"
              items={critique.weaknesses}
              empty="No weaknesses identified."
            />
          </div>

          <div className="grid-2">
            <CritiqueList
              title="Threats to validity"
              items={critique.threats_to_validity}
              empty="No threats identified."
            />
            <div className="card">
              <h3>Recommended follow-up</h3>
              {critique.recommended_followup.length === 0 ? (
                <p style={{ color: "var(--text-faint)" }}>
                  No follow-up work suggested.
                </p>
              ) : (
                <ul className="bullets">
                  {critique.recommended_followup.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
