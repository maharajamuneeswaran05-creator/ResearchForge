"use client";

import { useWorkflow } from "@/lib/session";
import { Panel } from "@/components/ui/Panel";
import { ConfidenceMeter } from "@/components/ui/ConfidenceMeter";
import { EmptyState, LoadingState } from "@/components/ui/States";
import type { FindingWithEvidence } from "@/lib/types";

function FindingList({
  title,
  findings,
  empty,
}: {
  title: string;
  findings: FindingWithEvidence[];
  empty: string;
}) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {findings.length === 0 ? (
        <p style={{ color: "var(--text-faint)" }}>{empty}</p>
      ) : (
        <ul className="bullets">
          {findings.map((finding, index) => (
            <li key={`${finding.claim}-${index}`}>
              {finding.claim}
              {finding.evidence_refs.length > 0 ? (
                <div
                  style={{
                    color: "var(--text-faint)",
                    fontSize: 11.5,
                    fontFamily: "var(--mono)",
                    marginTop: 2,
                  }}
                >
                  refs: {finding.evidence_refs.join(", ")}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function GapPanel() {
  const { state } = useWorkflow();
  const stage = state.stages.gap;
  const gap = state.gap;

  return (
    <Panel
      step={2}
      title="Research gap"
      caption="What is missing in the current literature"
      status={stage.status}
      error={stage.error}
    >
      {stage.status === "running" ? (
        <LoadingState label="Analysing the evidence for gaps…" />
      ) : !gap ? (
        <EmptyState>The gap analysis runs right after evidence collection.</EmptyState>
      ) : (
        <div className="stack">
          <div className="grid-2">
            <div className="card">
              <h3>Potential research gaps</h3>
              <ul className="bullets">
                {gap.potential_research_gaps.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="card">
              <h3>Missing evidence</h3>
              {gap.missing_evidence.length === 0 ? (
                <p style={{ color: "var(--text-faint)" }}>
                  No specific evidence gaps were flagged.
                </p>
              ) : (
                <ul className="bullets">
                  {gap.missing_evidence.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="grid-2">
            <FindingList
              title="Established findings"
              findings={gap.established_findings}
              empty="No established findings reported."
            />
            <FindingList
              title="Conflicting findings"
              findings={gap.conflicting_findings}
              empty="No conflicting findings reported."
            />
          </div>

          <div className="grid-2">
            <FindingList
              title="Limitations"
              findings={gap.limitations}
              empty="No limitations reported."
            />
            <div className="card">
              <h3>Confidence</h3>
              <ConfidenceMeter
                label={`Reliability (${gap.confidence_assessment.confidence_level})`}
                value={gap.confidence_assessment.reliability_score}
                tone={
                  gap.confidence_assessment.reliability_score >= 0.66
                    ? "success"
                    : gap.confidence_assessment.reliability_score >= 0.33
                      ? "warning"
                      : "accent"
                }
              />
              <p style={{ marginTop: 10 }}>
                {gap.confidence_assessment.reasoning}
              </p>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
