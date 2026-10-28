"use client";

import { useMemo, useState } from "react";
import { STAGES, useWorkflow, type StageId } from "@/lib/session";
import { StatusPill } from "@/components/ui/StatusPill";
import { ConfidenceMeter } from "@/components/ui/ConfidenceMeter";
import { CodeBlock } from "@/components/ui/CodeBlock";

export function ResearchInspector() {
  const {
    state,
    busy,
    selectedNodeId,
    setSelectedNodeId,
    runExperiment,
    runCritique,
    runReport,
    runRemaining,
    retryStage,
  } = useWorkflow();

  const [copied, setCopied] = useState(false);

  // Compute navigation tabs (Core + 8 stages)
  const navItems = useMemo(() => {
    return [
      { id: "core", label: "Core", status: busy ? "running" : "idle" },
      ...STAGES.map((s) => ({
        id: s.id,
        label: s.label,
        status: state.stages[s.id].status,
      })),
    ];
  }, [busy, state.stages]);

  function handleCopyMarkdown() {
    if (!state.report) return;
    const md =
      state.report.markdown ||
      `# ${state.report.title}\n\n` +
        state.report.sections
          .map((s) => `## ${s.title}\n\n${s.content}\n`)
          .join("\n");

    navigator.clipboard.writeText(md).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <aside className="research-inspector" aria-label="Research Node Inspector">
      {/* Inspector Header & Node Selector Tabs */}
      <div className="inspector-header">
        <div className="inspector-title-row">
          <div className="inspector-title">
            <span className="inspector-tag">INSPECTOR</span>
            <h2>
              {selectedNodeId === "core"
                ? "Research Question & Core"
                : STAGES.find((s) => s.id === selectedNodeId)?.label || "Node Details"}
            </h2>
          </div>
          {selectedNodeId !== "core" && (
            <StatusPill
              status={
                state.stages[selectedNodeId as StageId]?.status || "idle"
              }
            />
          )}
        </div>

        {/* Tab strip for swift navigation */}
        <div className="inspector-tabs" role="tablist">
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={selectedNodeId === item.id}
              className={`inspector-tab ${
                selectedNodeId === item.id ? "active" : ""
              } ${item.status}`}
              onClick={() => setSelectedNodeId(item.id)}
            >
              <span className={`tab-dot ${item.status}`} />
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Inspector Body Content */}
      <div className="inspector-body">
        {state.isDemo && (
          <div className="demo-banner">
            <span className="demo-pill">DEMONSTRATION DATA</span>
            <span>This is synthetic demonstration data to preview interface behavior.</span>
          </div>
        )}

        {/* ================================================================ */}
        {/* CORE NODE VIEW */}
        {/* ================================================================ */}
        {selectedNodeId === "core" && (
          <div className="inspector-section core-view">
            <div className="card highlight-card">
              <span className="card-label">ACTIVE RESEARCH QUESTION</span>
              <p className="card-question">
                {state.question || "No research question initiated yet."}
              </p>
            </div>

            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-num">
                  {Object.values(state.stages).filter((s) => s.status === "done").length}
                  /8
                </span>
                <span className="stat-title">Stages Completed</span>
              </div>
              <div className="stat-card">
                <span className="stat-num">{state.evidence.length}</span>
                <span className="stat-title">Literature Sources</span>
              </div>
              <div className="stat-card">
                <span className="stat-num">
                  {state.gap?.potential_research_gaps.length || 0}
                </span>
                <span className="stat-title">Identified Gaps</span>
              </div>
            </div>

            <div className="card">
              <h3>Pipeline Orchestration</h3>
              <p className="meta-text" style={{ marginBottom: 12 }}>
                Sequentially coordinates Tavily literature retrieval, Nemotron gap synthesis,
                controlled experimental design, code generation, Nebius serverless execution,
                adversarial critique, and structured reporting.
              </p>

              <div className="btn-row" style={{ flexWrap: "wrap", gap: 8 }}>
                <button
                  type="button"
                  className="btn primary"
                  disabled={busy || !state.question}
                  onClick={() => void runRemaining()}
                >
                  {busy ? "Pipeline Running..." : "Continue Remaining Stages"}
                </button>
              </div>
            </div>

            <div className="card provider-attributions">
              <h3>Autonomous Infrastructure</h3>
              <ul className="info-list">
                <li>
                  <strong>Literature Search:</strong> Tavily Search API
                </li>
                <li>
                  <strong>Inference Model:</strong> NVIDIA Nemotron (via Nebius Studio)
                </li>
                <li>
                  <strong>Compute Runner:</strong> Nebius Serverless Container
                </li>
              </ul>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* EVIDENCE STAGE VIEW */}
        {/* ================================================================ */}
        {selectedNodeId === "evidence" && (
          <div className="inspector-section">
            <div className="section-intro">
              <h3>Retrieved Scientific Literature ({state.evidence.length})</h3>
              <p>Grounded evidence retrieved from peer-reviewed scientific sources and preprints.</p>
            </div>

            {state.stages.evidence.error && (
              <div className="error-box">
                <strong>Evidence Collection Failed:</strong>
                <p>{state.stages.evidence.error}</p>
                <button
                  type="button"
                  className="btn sm danger"
                  style={{ marginTop: 8 }}
                  onClick={() => void retryStage("evidence")}
                >
                  Retry Evidence Collection
                </button>
              </div>
            )}

            {state.evidence.length === 0 && !state.stages.evidence.error ? (
              <div className="empty-state">
                <p>No evidence collected yet.</p>
                <span className="empty-hint">Start a research run to retrieve literature via Tavily.</span>
              </div>
            ) : (
              <div className="evidence-list">
                {state.evidence.map((item, idx) => (
                  <article key={idx} className="evidence-card">
                    <div className="evidence-top">
                      <span className="source-badge">{item.source || "Web"}</span>
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="external-link"
                        title="Open source in new tab"
                      >
                        Visit Source ↗
                      </a>
                    </div>
                    <h4>{item.title}</h4>
                    <p className="snippet">{item.snippet}</p>
                  </article>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ================================================================ */}
        {/* GAP STAGE VIEW */}
        {/* ================================================================ */}
        {selectedNodeId === "gap" && (
          <div className="inspector-section">
            <div className="section-intro">
              <h3>Research Gap Synthesis</h3>
              <p>Identified contradictions, limitations, and open frontiers in current literature.</p>
            </div>

            {state.stages.gap.error && (
              <div className="error-box">
                <strong>Gap Analysis Failed:</strong>
                <p>{state.stages.gap.error}</p>
                <button
                  type="button"
                  className="btn sm danger"
                  style={{ marginTop: 8 }}
                  onClick={() => void retryStage("gap")}
                >
                  Retry Gap Analysis
                </button>
              </div>
            )}

            {!state.gap && !state.stages.gap.error ? (
              <div className="empty-state">
                <p>Research gap analysis not yet conducted.</p>
              </div>
            ) : state.gap ? (
              <div className="gap-content stack">
                {state.gap.confidence_assessment && (
                  <div className="card">
                    <ConfidenceMeter
                      label={`Confidence Assessment (${state.gap.confidence_assessment.confidence_level})`}
                      value={state.gap.confidence_assessment.reliability_score}
                      caption={state.gap.confidence_assessment.reasoning}
                      tone="accent"
                    />
                  </div>
                )}

                <div className="card">
                  <h4>Potential Research Gaps</h4>
                  <ul className="bullet-list">
                    {state.gap.potential_research_gaps.map((gap, i) => (
                      <li key={i}>{gap}</li>
                    ))}
                  </ul>
                </div>

                <div className="card">
                  <h4>Established Findings</h4>
                  <div className="finding-items">
                    {state.gap.established_findings.map((f, i) => (
                      <div key={i} className="finding-item">
                        <p>{f.claim}</p>
                        {f.evidence_refs?.length > 0 && (
                          <div className="ref-tags">
                            {f.evidence_refs.map((ref, rIdx) => (
                              <a
                                key={rIdx}
                                href={ref}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="ref-link"
                              >
                                Source Ref [{rIdx + 1}]
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {state.gap.conflicting_findings?.length > 0 && (
                  <div className="card">
                    <h4>Conflicting Findings</h4>
                    <div className="finding-items">
                      {state.gap.conflicting_findings.map((f, i) => (
                        <div key={i} className="finding-item conflict">
                          <p>{f.claim}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {state.gap.missing_evidence?.length > 0 && (
                  <div className="card">
                    <h4>Missing Evidence</h4>
                    <ul className="bullet-list faint">
                      {state.gap.missing_evidence.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}

        {/* ================================================================ */}
        {/* HYPOTHESIS & EXPERIMENT DESIGN */}
        {/* ================================================================ */}
        {selectedNodeId === "hypothesis" && (
          <div className="inspector-section">
            <div className="section-intro">
              <h3>Hypothesis & Experimental Design</h3>
              <p>Formalized experimental setup with controlled variables and baseline comparison.</p>
            </div>

            {state.stages.hypothesis.error && (
              <div className="error-box">
                <strong>Experiment Planning Failed:</strong>
                <p>{state.stages.hypothesis.error}</p>
                <button
                  type="button"
                  className="btn sm danger"
                  style={{ marginTop: 8 }}
                  onClick={() => void retryStage("hypothesis")}
                >
                  Retry Hypothesis Design
                </button>
              </div>
            )}

            {!state.plan && !state.stages.hypothesis.error ? (
              <div className="empty-state">
                <p>Experiment plan not yet generated.</p>
              </div>
            ) : state.plan ? (
              <div className="hypothesis-content stack">
                <div className="card highlight-card">
                  <span className="card-label">CENTRAL HYPOTHESIS</span>
                  <p className="hypothesis-statement">{state.plan.hypothesis}</p>
                </div>

                <div className="card">
                  <h4>Research Objective</h4>
                  <p>{state.plan.research_objective}</p>
                </div>

                <div className="card">
                  <h4>Experimental Variables</h4>
                  <div className="variables-grid">
                    <div className="var-col">
                      <span className="var-label">Independent</span>
                      <ul>
                        {state.plan.variables.independent.map((v, i) => (
                          <li key={i}>{v}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="var-col">
                      <span className="var-label">Dependent</span>
                      <ul>
                        {state.plan.variables.dependent.map((v, i) => (
                          <li key={i}>{v}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="var-col">
                      <span className="var-label">Controls</span>
                      <ul>
                        {state.plan.variables.controls.map((v, i) => (
                          <li key={i}>{v}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <h4>Proposed Method vs. Baseline</h4>
                  <div className="comparison-grid">
                    <div>
                      <strong>Proposed:</strong>
                      <p>{state.plan.proposed_method}</p>
                    </div>
                    <div>
                      <strong>Baseline:</strong>
                      <p>{state.plan.baseline}</p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <h4>Evaluation Metrics</h4>
                  <div className="tag-cloud">
                    {state.plan.evaluation_metrics.map((m, i) => (
                      <span key={i} className="metric-tag">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* ================================================================ */}
        {/* EXPERIMENT CODE VIEW */}
        {/* ================================================================ */}
        {selectedNodeId === "experiment" && (
          <div className="inspector-section">
            <div className="section-intro">
              <h3>Generated Experiment Script</h3>
              <p>Self-contained, reproducible Python code designed for serverless execution.</p>
            </div>

            {state.stages.experiment.error && (
              <div className="error-box">
                <strong>Code Generation Failed:</strong>
                <p>{state.stages.experiment.error}</p>
                <button
                  type="button"
                  className="btn sm danger"
                  style={{ marginTop: 8 }}
                  onClick={() => void retryStage("experiment")}
                >
                  Retry Code Generation
                </button>
              </div>
            )}

            {!state.code && !state.stages.experiment.error ? (
              <div className="empty-state">
                <p>Experiment code not yet synthesized.</p>
              </div>
            ) : state.code ? (
              <div className="experiment-code-content stack">
                <div className="metadata-bar">
                  <span>
                    <strong>Language:</strong> {state.code.language}
                  </span>
                  <span>
                    <strong>Entrypoint:</strong> {state.code.entrypoint}
                  </span>
                  <span>
                    <strong>Seed:</strong> {state.code.random_seed}
                  </span>
                </div>

                {state.code.dependencies?.length > 0 && (
                  <div className="card">
                    <h4>Dependencies</h4>
                    <div className="tag-cloud">
                      {state.code.dependencies.map((dep, i) => (
                        <code key={i} className="dep-pill">
                          {dep}
                        </code>
                      ))}
                    </div>
                  </div>
                )}

                <div className="code-viewer-card">
                  <div className="code-viewer-head">
                    <span>experiment.py</span>
                    <button
                      type="button"
                      className="btn sm ghost"
                      onClick={() => {
                        navigator.clipboard.writeText(state.code?.code || "");
                      }}
                    >
                      Copy Code
                    </button>
                  </div>
                  <CodeBlock code={state.code.code} label={state.code.entrypoint} />
                </div>

                {!state.result && (
                  <button
                    type="button"
                    className="btn primary full-width"
                    disabled={busy}
                    onClick={() => void runExperiment()}
                  >
                    {busy ? "Running on Nebius..." : "Execute Script on Nebius AI"}
                  </button>
                )}
              </div>
            ) : null}
          </div>
        )}

        {/* ================================================================ */}
        {/* EXECUTION STAGE VIEW */}
        {/* ================================================================ */}
        {selectedNodeId === "execution" && (
          <div className="inspector-section">
            <div className="section-intro">
              <h3>Serverless Job Execution</h3>
              <p>Execution logs, process lifecycle, and exit status on Nebius AI.</p>
            </div>

            {state.stages.execution.error && (
              <div className="error-box">
                <strong>Execution Error:</strong>
                <p>{state.stages.execution.error}</p>
                {state.stages.execution.error.includes("NebiusExecutionNotConfigured") && (
                  <p className="hint">
                    Set `NEBIUS_EXECUTION_IMAGE` or Nebius container settings in backend `.env`
                    to enable real GPU serverless compute.
                  </p>
                )}
                <button
                  type="button"
                  className="btn sm danger"
                  style={{ marginTop: 8 }}
                  onClick={() => void retryStage("execution")}
                >
                  Retry Experiment Run
                </button>
              </div>
            )}

            {!state.job && !state.result && !state.stages.execution.error ? (
              <div className="empty-state">
                <p>Experiment has not been executed yet.</p>
                {state.code && (
                  <button
                    type="button"
                    className="btn primary sm"
                    style={{ marginTop: 12 }}
                    disabled={busy}
                    onClick={() => void runExperiment()}
                  >
                    Launch Experiment
                  </button>
                )}
              </div>
            ) : (
              <div className="execution-content stack">
                <div className="card">
                  <div className="job-meta-grid">
                    <div>
                      <span className="meta-label">Job ID</span>
                      <code>{state.job?.job_id || state.result?.job_id || "N/A"}</code>
                    </div>
                    <div>
                      <span className="meta-label">Status</span>
                      <StatusPill
                        status={
                          state.result?.status === "completed"
                            ? "done"
                            : state.result?.status === "failed"
                            ? "error"
                            : "running"
                        }
                      />
                    </div>
                    <div>
                      <span className="meta-label">Duration</span>
                      <span>{state.result?.execution_time_seconds ?? 0}s</span>
                    </div>
                    <div>
                      <span className="meta-label">Exit Code</span>
                      <code>{state.result?.exit_code ?? "—"}</code>
                    </div>
                  </div>
                </div>

                <div className="terminal-card">
                  <div className="terminal-head">
                    <span className="terminal-dot red" />
                    <span className="terminal-dot yellow" />
                    <span className="terminal-dot green" />
                    <span className="terminal-title">Runner stdout / stderr</span>
                  </div>
                  <pre className="terminal-output">
                    {state.result?.stdout || (busy ? "Running job in container..." : "No output")}
                    {state.result?.stderr && (
                      <span className="stderr-block">
                        {"\n--- STDERR ---\n"}
                        {state.result.stderr}
                      </span>
                    )}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================================================================ */}
        {/* RESULTS STAGE VIEW */}
        {/* ================================================================ */}
        {selectedNodeId === "results" && (
          <div className="inspector-section">
            <div className="section-intro">
              <h3>Experimental Results & Metrics</h3>
              <p>Extracted telemetry, metrics, and quantitative evaluation outcomes.</p>
            </div>

            {!state.result ? (
              <div className="empty-state">
                <p>No experiment results collected yet.</p>
              </div>
            ) : (
              <div className="results-content stack">
                <div className="card">
                  <h4>Extracted Quantitative Metrics</h4>
                  {Object.keys(state.result.metrics || {}).length === 0 ? (
                    <p className="meta-text">No structured metrics parsed from stdout.</p>
                  ) : (
                    <div className="metric-cards-grid">
                      {Object.entries(state.result.metrics).map(([key, val]) => (
                        <div key={key} className="metric-pill-card">
                          <span className="metric-k">{key.replace(/_/g, " ")}</span>
                          <span className="metric-v">
                            {typeof val === "number"
                              ? Number.isInteger(val)
                                ? val
                                : val.toFixed(4)
                              : String(val)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="card">
                  <h4>Raw Result Payload</h4>
                  <pre className="json-dump">
                    {JSON.stringify(state.result.metrics, null, 2)}
                  </pre>
                </div>

                {!state.critique && (
                  <button
                    type="button"
                    className="btn primary"
                    disabled={busy}
                    onClick={() => void runCritique()}
                  >
                    Proceed to Adversarial Critique
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* ================================================================ */}
        {/* CRITIC STAGE VIEW */}
        {/* ================================================================ */}
        {selectedNodeId === "critic" && (
          <div className="inspector-section">
            <div className="section-intro">
              <h3>Adversarial Scientific Critique</h3>
              <p>Skeptical peer review identifying methodological biases and threats to validity.</p>
            </div>

            {state.stages.critic.error && (
              <div className="error-box">
                <strong>Critique Failed:</strong>
                <p>{state.stages.critic.error}</p>
                <button
                  type="button"
                  className="btn sm danger"
                  style={{ marginTop: 8 }}
                  onClick={() => void retryStage("critic")}
                >
                  Retry Critique
                </button>
              </div>
            )}

            {!state.critique && !state.stages.critic.error ? (
              <div className="empty-state">
                <p>Adversarial critique has not been performed yet.</p>
                {state.gap && (
                  <button
                    type="button"
                    className="btn primary sm"
                    style={{ marginTop: 12 }}
                    disabled={busy}
                    onClick={() => void runCritique()}
                  >
                    Run Adversarial Review
                  </button>
                )}
              </div>
            ) : state.critique ? (
              <div className="critic-content stack">
                <div className="card verdict-card">
                  <div className="verdict-header">
                    <span className="card-label">REVIEWER VERDICT</span>
                    <span className="score-pill">
                      Confidence: {Math.round(state.critique.confidence_score * 100)}%
                    </span>
                  </div>
                  <p className="verdict-text">{state.critique.verdict}</p>
                  <div className="hypothesis-status">
                    Hypothesis Supported:{" "}
                    <strong>
                      {state.critique.hypothesis_supported === null
                        ? "Inconclusive"
                        : state.critique.hypothesis_supported
                        ? "Yes"
                        : "No"}
                    </strong>
                  </div>
                </div>

                {state.critique.strengths?.length > 0 && (
                  <div className="card">
                    <h4>Methodological Strengths</h4>
                    <div className="critique-items">
                      {state.critique.strengths.map((item, i) => (
                        <div key={i} className="critique-item strength">
                          <span className="critique-cat">{item.category}</span>
                          <p>{item.finding}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {state.critique.weaknesses?.length > 0 && (
                  <div className="card">
                    <h4>Weaknesses & Limitations</h4>
                    <div className="critique-items">
                      {state.critique.weaknesses.map((item, i) => (
                        <div key={i} className={`critique-item weakness ${item.severity}`}>
                          <div className="item-head">
                            <span className="critique-cat">{item.category}</span>
                            <span className={`severity-tag ${item.severity}`}>
                              {item.severity} severity
                            </span>
                          </div>
                          <p>{item.finding}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {state.critique.threats_to_validity?.length > 0 && (
                  <div className="card">
                    <h4>Threats to Validity</h4>
                    <div className="critique-items">
                      {state.critique.threats_to_validity.map((item, i) => (
                        <div key={i} className="critique-item threat">
                          <span className="critique-cat">{item.category}</span>
                          <p>{item.finding}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {state.critique.recommended_followup?.length > 0 && (
                  <div className="card">
                    <h4>Recommended Follow-up Steps</h4>
                    <ul className="bullet-list">
                      {state.critique.recommended_followup.map((rec, i) => (
                        <li key={i}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}

        {/* ================================================================ */}
        {/* REPORT STAGE VIEW */}
        {/* ================================================================ */}
        {selectedNodeId === "report" && (
          <div className="inspector-section">
            <div className="section-intro">
              <h3>Final Research Synthesis</h3>
              <p>Publication-ready report synthesizing evidence, methodology, and critique.</p>
            </div>

            {state.stages.report.error && (
              <div className="error-box">
                <strong>Report Generation Failed:</strong>
                <p>{state.stages.report.error}</p>
                <button
                  type="button"
                  className="btn sm danger"
                  style={{ marginTop: 8 }}
                  onClick={() => void retryStage("report")}
                >
                  Retry Report Synthesis
                </button>
              </div>
            )}

            {!state.report && !state.stages.report.error ? (
              <div className="empty-state">
                <p>Final report has not been compiled yet.</p>
                {state.question && (
                  <button
                    type="button"
                    className="btn primary sm"
                    style={{ marginTop: 12 }}
                    disabled={busy}
                    onClick={() => void runReport()}
                  >
                    Compile Final Report
                  </button>
                )}
              </div>
            ) : state.report ? (
              <div className="report-content stack">
                <div className="report-title-card">
                  <div className="report-meta">
                    <span className="report-date">
                      {new Date(state.report.generated_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "long",
                        day: "numeric",
                      })}
                    </span>
                    <button
                      type="button"
                      className="btn sm ghost"
                      onClick={handleCopyMarkdown}
                    >
                      {copied ? "Copied!" : "Copy Markdown"}
                    </button>
                  </div>
                  <h2>{state.report.title}</h2>
                </div>

                {state.report.confidence_assessment && (
                  <div className="card">
                    <ConfidenceMeter
                      label={`Confidence Assessment (${state.report.confidence_assessment.confidence_level})`}
                      value={state.report.confidence_assessment.reliability_score}
                      caption={state.report.confidence_assessment.reasoning}
                      tone="accent"
                    />
                  </div>
                )}

                {state.report.sections.map((section) => (
                  <article key={section.key} className="card report-section">
                    <h4>{section.title}</h4>
                    <p className="report-p">{section.content}</p>
                    {section.evidence_refs?.length > 0 && (
                      <div className="ref-tags" style={{ marginTop: 12 }}>
                        {section.evidence_refs.map((ref, idx) => (
                          <a
                            key={idx}
                            href={ref}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ref-link"
                          >
                            Citations [{idx + 1}]
                          </a>
                        ))}
                      </div>
                    )}
                  </article>
                ))}

                {state.report.sources?.length > 0 && (
                  <div className="card">
                    <h4>Bibliography & Primary Sources ({state.report.sources.length})</h4>
                    <ul className="sources-list">
                      {state.report.sources.map((s, i) => (
                        <li key={i}>
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="source-title-link"
                          >
                            {s.title}
                          </a>
                          <span className="source-domain">({s.source})</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}
      </div>
    </aside>
  );
}
