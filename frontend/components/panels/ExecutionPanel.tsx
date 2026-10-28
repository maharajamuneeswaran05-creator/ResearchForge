"use client";

import { useWorkflow } from "@/lib/session";
import { Panel } from "@/components/ui/Panel";
import { LogBlock } from "@/components/ui/CodeBlock";
import { EmptyState, LoadingState } from "@/components/ui/States";

const STATUS_LABEL: Record<string, string> = {
  pending: "Queued on Nebius Serverless AI",
  running: "Container is executing",
  completed: "Container finished successfully",
  failed: "Container exited with an error",
  timeout: "Container exceeded the time limit",
  cancelled: "Job was cancelled",
};

export function ExecutionPanel() {
  const { state, busy, runExperiment } = useWorkflow();
  const stage = state.stages.execution;
  const job = state.job;
  const result = state.result;

  const canRun = Boolean(state.code) && !busy;

  const isDemo = Boolean(job?.is_demo || result?.is_demo);
  const isUnconfigured = Boolean(
    stage.error &&
      (stage.error.includes("not configured") ||
        stage.error.includes("unconfigured") ||
        stage.error.includes("NebiusExecutionNotConfigured")),
  );

  return (
    <Panel
      step={5}
      title="Live execution"
      caption={isDemo ? "Simulated execution (Demo Mode)" : "Serverless run on Nebius AI Cloud"}
      status={stage.status}
      error={stage.error}
      action={
        <div className="btn-row">
          {isUnconfigured && (
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => void runExperiment(true)}
              disabled={!canRun}
              title="Execute safely in an isolated sandbox environment without Nebius Cloud infrastructure"
            >
              Run in Demo Mode
            </button>
          )}
          <button
            className="btn sm"
            onClick={() => void runExperiment()}
            disabled={!canRun}
          >
            {stage.status === "running" ? (
              <>
                <span className="spinner" />
                Running
              </>
            ) : (
              "Run experiment"
            )}
          </button>
        </div>
      }
    >
      {isDemo && (
        <div
          style={{
            background: "rgba(245, 158, 11, 0.12)",
            border: "1px solid rgba(245, 158, 11, 0.35)",
            borderRadius: "var(--radius, 8px)",
            padding: "8px 12px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: "#fbbf24",
            fontSize: 12.5,
            marginBottom: 12,
          }}
        >
          <span style={{ fontWeight: 700 }}>[DEMO MODE]</span>
          <span>Simulated local execution with isolated environment. No cloud compute was billed.</span>
        </div>
      )}

      {isUnconfigured && !job && stage.status !== "running" && (
        <div
          style={{
            background: "rgba(59, 130, 246, 0.08)",
            border: "1px solid rgba(59, 130, 246, 0.25)",
            borderRadius: "var(--radius, 8px)",
            padding: "12px",
            fontSize: 12.5,
            marginBottom: 12,
          }}
        >
          <strong style={{ color: "var(--accent, #00f0ff)" }}>Cloud Infrastructure Note:</strong>
          <p style={{ marginTop: 4, color: "var(--text-muted)" }}>
            Nebius Serverless credentials are not yet configured in <code>backend/.env</code>.
            You can still test and verify the execution and telemetry parsing pipeline by clicking{" "}
            <strong>Run in Demo Mode</strong> above.
          </p>
        </div>
      )}

      {!job && stage.status !== "running" ? (
        <EmptyState>
          {state.code
            ? "Run the experiment to execute it on Nebius Serverless AI."
            : "Experiment code is required before the run can start."}
        </EmptyState>
      ) : stage.status === "running" && !job ? (
        <LoadingState label="Submitting the job to Nebius Serverless AI…" />
      ) : job ? (
        <div className="stack">
          <div className="card">
            <div className="btn-row" style={{ justifyContent: "space-between" }}>
              <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
                {STATUS_LABEL[job.status] ?? job.status}
              </span>
              {stage.status === "running" ? (
                <span className="pill running">
                  <span className="dot" />
                  Polling
                </span>
              ) : null}
            </div>
          </div>

          <dl className="kv">
            <dt>Job id</dt>
            <dd style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{job.job_id}</dd>
            <dt>Execution type</dt>
            <dd>{isDemo ? "Simulated Sandbox (Demo)" : "Nebius Serverless AI"}</dd>
            <dt>Nebius job id</dt>
            <dd style={{ fontFamily: "var(--mono)", fontSize: 12 }}>
              {job.nebius_job_id ?? (isDemo ? "n/a (local demo)" : "pending")}
            </dd>
            <dt>Status</dt>
            <dd>{job.status}</dd>
            {job.submitted_at ? (
              <>
                <dt>Submitted at</dt>
                <dd>{new Date(job.submitted_at).toLocaleString()}</dd>
              </>
            ) : null}
            {result ? (
              <>
                <dt>Exit code</dt>
                <dd>{result.exit_code ?? "—"}</dd>
                <dt>Duration</dt>
                <dd>{result.execution_time_seconds.toFixed(2)} s</dd>
              </>
            ) : null}
          </dl>

          {job.error ? (
            <div className="error-box">
              <strong>Job error</strong>
              {job.error}
            </div>
          ) : null}

          {result?.stderr ? (
            <div className="stack tight">
              <span className="field-label" style={{ marginBottom: 0 }}>
                stderr
              </span>
              <LogBlock text={result.stderr} tone="stderr" />
            </div>
          ) : null}
        </div>
      ) : (
        <EmptyState>No execution has been started.</EmptyState>
      )}
    </Panel>
  );
}
