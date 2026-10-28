"use client";

import { useWorkflow } from "@/lib/session";
import { Panel } from "@/components/ui/Panel";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { EmptyState, LoadingState } from "@/components/ui/States";

export function ExperimentPanel() {
  const { state } = useWorkflow();
  const stage = state.stages.experiment;
  const code = state.code;

  return (
    <Panel
      step={4}
      title="Experiment"
      caption="Runnable implementation for Nebius Serverless AI"
      status={stage.status}
      error={stage.error}
    >
      {stage.status === "running" ? (
        <LoadingState label="Writing the experiment code…" />
      ) : !code ? (
        <EmptyState>Experiment code is generated from the experiment plan.</EmptyState>
      ) : (
        <div className="stack">
          <dl className="kv">
            <dt>Language</dt>
            <dd>{code.language}</dd>
            <dt>Entrypoint</dt>
            <dd>{code.entrypoint}</dd>
            <dt>Random seed</dt>
            <dd>{code.random_seed}</dd>
            <dt>Dependencies</dt>
            <dd>
              {code.dependencies.length ? (
                <div className="tag-list">
                  {code.dependencies.map((dependency) => (
                    <span className="tag" key={dependency}>
                      {dependency}
                    </span>
                  ))}
                </div>
              ) : (
                "none"
              )}
            </dd>
            <dt>Inputs</dt>
            <dd>
              {code.inputs.length ? code.inputs.join(", ") : "none"}
            </dd>
            <dt>Outputs</dt>
            <dd>
              {code.outputs.length ? code.outputs.join(", ") : "none"}
            </dd>
            <dt>Model</dt>
            <dd>{code.model}</dd>
          </dl>

          {code.notes ? (
            <div className="card">
              <h3>Notes</h3>
              <p>{code.notes}</p>
            </div>
          ) : null}

          <CodeBlock code={code.code} label="Source" />
        </div>
      )}
    </Panel>
  );
}
