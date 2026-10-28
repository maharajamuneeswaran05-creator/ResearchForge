"use client";

import { useWorkflow } from "@/lib/session";
import { Panel } from "@/components/ui/Panel";
import { EmptyState, LoadingState } from "@/components/ui/States";

export function EvidencePanel() {
  const { state } = useWorkflow();
  const stage = state.stages.evidence;

  return (
    <Panel
      step={1}
      title="Evidence"
      caption="Literature retrieved for the research question"
      status={stage.status}
      error={stage.error}
      tight
    >
      {stage.status === "running" ? (
        <div style={{ padding: 18 }}>
          <LoadingState label="Searching the literature…" />
        </div>
      ) : state.evidence.length === 0 ? (
        <EmptyState>
          No evidence collected yet. Start a research run to gather sources.
        </EmptyState>
      ) : (
        <div>
          {state.evidence.map((item, index) => (
            <article className="evidence-item" key={`${item.url}-${index}`}>
              <div className="title">
                <a href={item.url} target="_blank" rel="noreferrer noopener">
                  {item.title}
                </a>
              </div>
              <div className="source">
                {item.source} · {item.url}
              </div>
              {item.snippet ? <p className="snippet">{item.snippet}</p> : null}
            </article>
          ))}
        </div>
      )}
    </Panel>
  );
}
