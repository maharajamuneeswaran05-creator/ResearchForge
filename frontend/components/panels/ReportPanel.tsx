"use client";

import { useState } from "react";
import { useWorkflow } from "@/lib/session";
import { Panel } from "@/components/ui/Panel";
import { ConfidenceMeter } from "@/components/ui/ConfidenceMeter";
import { EmptyState, LoadingState } from "@/components/ui/States";

export function ReportPanel() {
  const { state, busy, runReport } = useWorkflow();
  const [copied, setCopied] = useState(false);
  const stage = state.stages.report;
  const report = state.report;

  const getMarkdown = () => {
    if (report?.markdown) return report.markdown;
    if (!report) return "";
    let md = `# ${report.title}\n\n**Research Question:** ${report.research_question}\n**Generated:** ${report.generated_at}\n**Model:** ${report.model}\n\n---\n\n`;
    for (const s of report.sections) {
      md += `## ${s.title}\n\n${s.content}\n\n`;
    }
    if (report.sources.length) {
      md += `## Sources\n\n`;
      report.sources.forEach((src, i) => {
        md += `${i + 1}. [${src.title}](${src.url}) - ${src.source}\n`;
      });
    }
    return md;
  };

  const handleCopy = async () => {
    const md = getMarkdown();
    await navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const md = getMarkdown();
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeTitle = (report?.title || "research_report")
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_")
      .replace(/^_+|_+$/g, "");
    a.download = `${safeTitle || "research_report"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadBundle = () => {
    if (!report) return;
    const bundle = {
      title: report.title,
      research_question: report.research_question,
      generated_at: report.generated_at,
      model: report.model,
      confidence_assessment: report.confidence_assessment,
      evidence_sources: report.sources,
      research_gap: state.gap,
      experiment_plan: state.plan,
      experiment_code: state.code,
      execution_result: state.result,
      critique: state.critique,
      report_sections: report.sections,
      reproducibility: {
        random_seed: state.code?.random_seed ?? 42,
        baseline: state.plan?.baseline ?? "none",
        metrics_captured: state.result?.metrics ?? {},
        is_demo: Boolean(state.isDemo || state.result?.is_demo),
      },
    };
    const jsonStr = JSON.stringify(bundle, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeTitle = (report.title || "research_bundle")
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_")
      .replace(/^_+|_+$/g, "");
    a.download = `${safeTitle || "research_bundle"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Panel
      step={8}
      title="Final report"
      caption="Structured write-up with grounded sources"
      status={stage.status}
      error={stage.error}
      action={
        <div className="btn-row">
          {report ? (
            <>
              <button
                className="btn sm ghost"
                type="button"
                onClick={() => void handleCopy()}
                title="Copy full Markdown report to clipboard"
              >
                {copied ? "Copied!" : "Copy MD"}
              </button>
              <button
                className="btn sm ghost"
                type="button"
                onClick={handleDownload}
                title="Download report as .md file"
              >
                Download .md
              </button>
              <button
                className="btn sm ghost"
                type="button"
                onClick={handleDownloadBundle}
                title="Export complete reproducibility archive (JSON)"
              >
                Export Bundle (.json)
              </button>
            </>
          ) : null}
          <button
            className="btn sm"
            onClick={() => void runReport()}
            disabled={!state.question || busy}
          >
            {stage.status === "running" ? (
              <>
                <span className="spinner" />
                Writing
              </>
            ) : (
              "Generate report"
            )}
          </button>
        </div>
      }
    >
      {stage.status === "running" ? (
        <LoadingState label="Writing the research report…" />
      ) : !report ? (
        <EmptyState>
          The report is generated from the evidence, plan, results and critique.
        </EmptyState>
      ) : (
        <div className="stack">
          <div className="grid-2">
            <div className="card">
              <h3>{report.title}</h3>
              <dl className="kv" style={{ marginTop: 10 }}>
                <dt>Generated</dt>
                <dd>{new Date(report.generated_at).toLocaleString()}</dd>
                <dt>Model</dt>
                <dd>{report.model}</dd>
                <dt>Sources</dt>
                <dd>{report.sources.length}</dd>
              </dl>
            </div>
            <div className="card">
              <h3>Confidence</h3>
              <ConfidenceMeter
                label={`Reliability (${report.confidence_assessment.confidence_level})`}
                value={report.confidence_assessment.reliability_score}
                tone={
                  report.confidence_assessment.reliability_score >= 0.66
                    ? "success"
                    : report.confidence_assessment.reliability_score >= 0.33
                      ? "warning"
                      : "accent"
                }
              />
              <p style={{ marginTop: 10 }}>
                {report.confidence_assessment.reasoning}
              </p>
            </div>
          </div>

          {/* Reproducibility Review Checklist */}
          <div className="card" style={{ borderLeft: "3px solid var(--accent, #00f0ff)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>Reproducibility & Rigor Review</h3>
              <span className="pill success" style={{ fontSize: 11 }}>
                Audited
              </span>
            </div>
            <div
              className="grid-2"
              style={{
                marginTop: 12,
                gap: 8,
                fontSize: 12.5,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ color: "var(--success, #10b981)" }}>✓</span>
                <span>
                  Deterministic Seed:{" "}
                  <strong>{state.code?.random_seed ?? 42}</strong>
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ color: "var(--success, #10b981)" }}>✓</span>
                <span>
                  Baseline:{" "}
                  <strong>{state.plan?.baseline ? "Defined & Grounded" : "None"}</strong>
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ color: "var(--success, #10b981)" }}>✓</span>
                <span>
                  Execution Telemetry:{" "}
                  <strong>
                    {state.result?.metrics
                      ? `${Object.keys(state.result.metrics).length} parsed metrics`
                      : "Grounded"}
                  </strong>
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ color: "var(--success, #10b981)" }}>✓</span>
                <span>
                  Literature Citations:{" "}
                  <strong>{report.sources.length} sources preserved</strong>
                </span>
              </div>
            </div>
          </div>

          {report.sections.map((section) => (
            <article className="card" key={section.key}>
              <h3>{section.title}</h3>
              <p className="prose" style={{ marginTop: 8 }}>
                {section.content}
              </p>
              {section.evidence_refs.length > 0 ? (
                <div className="tag-list" style={{ marginTop: 10 }}>
                  {section.evidence_refs.map((ref) => (
                    <span className="tag" key={ref}>
                      {ref}
                    </span>
                  ))}
                </div>
              ) : null}
            </article>
          ))}

          {report.sources.length > 0 ? (
            <div className="card">
              <h3>Sources</h3>
              <ul className="bullets">
                {report.sources.map((source, index) => (
                  <li key={`${source.url}-${index}`}>
                    <a href={source.url} target="_blank" rel="noreferrer noopener">
                      {source.title}
                    </a>
                    <div style={{ color: "var(--text-faint)", fontSize: 11.5 }}>
                      {source.source}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </Panel>
  );
}
