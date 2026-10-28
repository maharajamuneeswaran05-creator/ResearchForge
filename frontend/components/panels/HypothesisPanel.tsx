"use client";

import { useWorkflow } from "@/lib/session";
import { Panel } from "@/components/ui/Panel";
import { EmptyState, LoadingState } from "@/components/ui/States";

function TagList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p style={{ color: "var(--text-faint)" }}>Not specified</p>
      ) : (
        <ul className="bullets">
          {items.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function HypothesisPanel() {
  const { state } = useWorkflow();
  const stage = state.stages.hypothesis;
  const plan = state.plan;

  return (
    <Panel
      step={3}
      title="Hypothesis & experiment design"
      caption="Plan derived from the identified gap"
      status={stage.status}
      error={stage.error}
    >
      {stage.status === "running" ? (
        <LoadingState label="Designing the experiment…" />
      ) : !plan ? (
        <EmptyState>The experiment plan is generated from the research gap.</EmptyState>
      ) : (
        <div className="stack">
          <div className="card">
            <h3>Hypothesis</h3>
            <p style={{ color: "var(--text)", fontSize: 14 }}>{plan.hypothesis}</p>
          </div>

          <div className="grid-2">
            <div className="card">
              <h3>Objective</h3>
              <p>{plan.research_objective}</p>
            </div>
            <div className="card">
              <h3>Baseline</h3>
              <p>{plan.baseline}</p>
            </div>
          </div>

          <div className="grid-2">
            <TagList title="Independent variables" items={plan.variables.independent} />
            <TagList title="Dependent variables" items={plan.variables.dependent} />
          </div>

          <div className="grid-2">
            <TagList title="Controls" items={plan.variables.controls} />
            <TagList title="Dataset requirements" items={plan.dataset_requirements} />
          </div>

          <div className="grid-2">
            <TagList title="Evaluation metrics" items={plan.evaluation_metrics} />
            <TagList title="Risks" items={plan.risks} />
          </div>

          <div className="card">
            <h3>Proposed method</h3>
            <p>{plan.proposed_method}</p>
          </div>

          <div className="card">
            <h3>Expected outcome</h3>
            <p>{plan.expected_outcome}</p>
          </div>
        </div>
      )}
    </Panel>
  );
}
