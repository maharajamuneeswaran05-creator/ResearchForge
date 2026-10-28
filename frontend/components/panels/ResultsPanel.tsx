"use client";

import { useWorkflow } from "@/lib/session";
import { Panel } from "@/components/ui/Panel";
import { MetricChart } from "@/components/ui/MetricChart";
import { LogBlock } from "@/components/ui/CodeBlock";
import { EmptyState, LoadingState } from "@/components/ui/States";

export function ResultsPanel() {
  const { state } = useWorkflow();
  const stage = state.stages.results;
  const result = state.result;

  const metrics = result ? Object.entries(result.metrics) : [];

  return (
    <Panel
      step={6}
      title="Results & metrics"
      caption="Output collected from the experiment container"
      status={stage.status}
      error={stage.error}
    >
      {stage.status === "running" ? (
        <LoadingState label="Waiting for the experiment to finish…" />
      ) : !result ? (
        <EmptyState>Results appear once the experiment job completes.</EmptyState>
      ) : (
        <div className="stack">
          {metrics.length > 0 ? (
            <div className="card">
              <h3>Metric comparison</h3>
              <MetricChart metrics={result.metrics} />
              <table className="metric-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map(([name, value]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{String(value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="card">
              <h3>Metrics</h3>
              <p style={{ color: "var(--text-faint)" }}>
                The experiment did not report any metrics.
              </p>
            </div>
          )}

          {result.stdout ? (
            <div className="stack tight">
              <span className="field-label" style={{ marginBottom: 0 }}>
                stdout
              </span>
              <LogBlock text={result.stdout} />
            </div>
          ) : null}
        </div>
      )}
    </Panel>
  );
}
