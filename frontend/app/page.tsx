"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { STAGES, useWorkflow } from "@/lib/session";
import { StatusPill } from "@/components/ui/StatusPill";

const EXAMPLES = [
  "Does self-supervised pretraining on scientific corpora improve sample efficiency for protein structure prediction?",
  "How does curriculum ordering affect convergence in sparse-reward reinforcement learning?",
  "Are retrieval-augmented language models less prone to factual hallucination than parametric models?",
];

export default function LandingPage() {
  const router = useRouter();
  const { state, busy, beginResearch, loadDemoData } = useWorkflow();
  const [question, setQuestion] = useState(state.question);

  useEffect(() => {
    if (!question && state.question) setQuestion(state.question);
  }, [question, state.question]);

  const failedStage = STAGES.find((stage) => state.stages[stage.id].status === "error");
  const failure = failedStage
    ? { label: failedStage.label, message: state.stages[failedStage.id].error }
    : null;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || busy) return;
    const started = await beginResearch(trimmed);
    if (started) router.push("/workspace");
  }

  function handleDemoClick() {
    loadDemoData();
    router.push("/workspace");
  }

  return (
    <div className="page-narrow">
      <section className="hero">
        <span className="eyebrow">
          <span className="dot" style={{ color: "var(--accent)" }} />
          Evidence → Gap → Hypothesis → Experiment → Results → Critique → Report
        </span>
        <h1>
          From a research question to a <span>defensible experiment</span>.
        </h1>
        <p>
          ResearchForge runs the full loop for you: it collects the literature,
          isolates the open research gap, designs a controlled experiment,
          executes it on serverless compute, then subjects the result to an
          adversarial critique and writes the report with grounded sources.
        </p>
      </section>

      <form className="composer" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="research-question">
          Research question
        </label>
        <textarea
          id="research-question"
          value={question}
          placeholder="e.g. Does X improve Y compared to Z under condition C?"
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              void handleSubmit(event);
            }
          }}
        />
        <div className="composer-footer">
          <span className="composer-hint">
            <kbd>Ctrl</kbd> + <kbd>Enter</kbd> to start the pipeline
          </span>
          <div className="btn-row">
            <button
              type="button"
              className="btn ghost"
              onClick={handleDemoClick}
              title="Open workspace with demonstration dataset"
            >
              Explore 3D Demo
            </button>
            <button className="btn primary" type="submit" disabled={busy || !question.trim()}>
              {busy ? (
                <>
                  <span className="spinner" />
                  Running pipeline
                </>
              ) : (
                "Begin research"
              )}
            </button>
          </div>
        </div>

        {busy ? (
          <div className="stack tight" style={{ marginTop: 16 }}>
            {STAGES.slice(0, 4).map((stage) => (
              <div
                className="meter-row"
                key={stage.id}
                style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}
              >
                <span>
                  {stage.label} — {stage.caption}
                </span>
                <StatusPill status={state.stages[stage.id].status} />
              </div>
            ))}
          </div>
        ) : null}

        {failure ? (
          <div className="error-box" style={{ marginTop: 16 }}>
            <strong>{failure.label} failed</strong>
            {failure.message}
          </div>
        ) : null}
      </form>

      <div className="suggestions">
        {EXAMPLES.map((example) => (
          <button
            type="button"
            className="suggestion"
            key={example}
            onClick={() => setQuestion(example)}
          >
            {example.length > 88 ? `${example.slice(0, 88)}…` : example}
          </button>
        ))}
      </div>

      <section className="pipeline-preview">
        {STAGES.map((stage, index) => (
          <div className="pipeline-preview-item" key={stage.id}>
            <div className="index">{String(index + 1).padStart(2, "0")}</div>
            <h3>{stage.label}</h3>
            <p>{stage.caption}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
