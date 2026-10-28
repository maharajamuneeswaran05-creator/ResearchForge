"use client";

// Orchestrates the autonomous research workflow. The backend owns all
// research logic; this provider sequences the API calls, logs events,
// and manages selection state for the 3D graph and inspector workspace.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { api } from "./api";
import type {
  EvidenceItem,
  ExperimentCodeResponse,
  ExperimentExecutionResult,
  ExperimentJobResponse,
  ExperimentPlanResponse,
  ResearchCriticResponse,
  ResearchGapResponse,
  ResearchReportResponse,
  StructuredResearchGap,
} from "./types";

export type StageId =
  | "evidence"
  | "gap"
  | "hypothesis"
  | "experiment"
  | "execution"
  | "results"
  | "critic"
  | "report";

export type StageStatus = "idle" | "running" | "done" | "error";

export interface StageState {
  status: StageStatus;
  error?: string;
}

export interface StageDefinition {
  id: StageId;
  label: string;
  caption: string;
}

export const STAGES: StageDefinition[] = [
  { id: "evidence", label: "Evidence", caption: "Retrieve literature" },
  { id: "gap", label: "Gap", caption: "Identify the gap" },
  { id: "hypothesis", label: "Hypothesis", caption: "Design the experiment" },
  { id: "experiment", label: "Experiment", caption: "Generate runnable code" },
  { id: "execution", label: "Execution", caption: "Run on Nebius Serverless" },
  { id: "results", label: "Results", caption: "Collect metrics" },
  { id: "critic", label: "Critic", caption: "Adversarial review" },
  { id: "report", label: "Report", caption: "Final write-up" },
];

export interface WorkflowLogEntry {
  id: string;
  timestamp: string;
  stageId?: StageId | "system";
  type: "info" | "success" | "warning" | "error";
  message: string;
  detail?: string;
}

export interface RecentSessionItem {
  id: string;
  question: string;
  timestamp: string;
}

export interface ProviderHealth {
  backend: "checking" | "online" | "offline";
  backendDetails?: string;
  nebius: "checking" | "online" | "unconfigured" | "error";
  nebiusModel?: string;
  nebiusDetails?: string;
}

export interface WorkflowState {
  question: string;
  stages: Record<StageId, StageState>;
  evidence: EvidenceItem[];
  gap: ResearchGapResponse | null;
  plan: ExperimentPlanResponse | null;
  code: ExperimentCodeResponse | null;
  job: ExperimentJobResponse | null;
  result: ExperimentExecutionResult | null;
  critique: ResearchCriticResponse | null;
  report: ResearchReportResponse | null;
  isDemo?: boolean;
}

const STORAGE_KEY = "researchforge.workflow.v2";
const SESSIONS_KEY = "researchforge.sessions.v1";

const EMPTY_STAGES: Record<StageId, StageState> = STAGES.reduce(
  (acc, stage) => {
    acc[stage.id] = { status: "idle" };
    return acc;
  },
  {} as Record<StageId, StageState>,
);

const INITIAL_STATE: WorkflowState = {
  question: "",
  stages: EMPTY_STAGES,
  evidence: [],
  gap: null,
  plan: null,
  code: null,
  job: null,
  result: null,
  critique: null,
  report: null,
  isDemo: false,
};

const TERMINAL_STATUSES = ["completed", "failed", "timeout", "cancelled"];

interface WorkflowContextValue {
  state: WorkflowState;
  busy: boolean;
  selectedNodeId: string;
  setSelectedNodeId: (id: string) => void;
  logs: WorkflowLogEntry[];
  clearLogs: () => void;
  recentSessions: RecentSessionItem[];
  providerStatus: ProviderHealth;
  checkProviders: () => Promise<void>;
  beginResearch: (question: string) => Promise<boolean>;
  runExperiment: (demo?: boolean) => Promise<void>;
  runCritique: () => Promise<void>;
  runReport: () => Promise<void>;
  runRemaining: () => Promise<void>;
  retryStage: (stageId: StageId) => Promise<void>;
  loadDemoData: () => void;
  reset: () => void;
}

const WorkflowContext = createContext<WorkflowContextValue | null>(null);

export function toStructuredGap(gap: ResearchGapResponse): StructuredResearchGap {
  return {
    research_question: gap.research_question,
    potential_research_gaps: gap.potential_research_gaps,
    missing_evidence: gap.missing_evidence,
    established_findings: gap.established_findings,
    conflicting_findings: gap.conflicting_findings,
    limitations: gap.limitations,
    confidence_assessment: gap.confidence_assessment,
  };
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatTime(date: Date = new Date()): string {
  return date.toTimeString().split(" ")[0];
}

export function WorkflowProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<WorkflowState>(INITIAL_STATE);
  const [busy, setBusy] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string>("core");
  const [logs, setLogs] = useState<WorkflowLogEntry[]>([]);
  const [recentSessions, setRecentSessions] = useState<RecentSessionItem[]>([]);
  const [providerStatus, setProviderStatus] = useState<ProviderHealth>({
    backend: "checking",
    nebius: "checking",
  });

  const stateRef = useRef(state);
  const activeStage = useRef<StageId | null>(null);

  stateRef.current = state;

  const addLog = useCallback(
    (
      type: WorkflowLogEntry["type"],
      message: string,
      stageId?: StageId | "system",
      detail?: string,
    ) => {
      const entry: WorkflowLogEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        timestamp: formatTime(),
        stageId,
        type,
        message,
        detail,
      };
      setLogs((prev) => [entry, ...prev.slice(0, 99)]);
    },
    [],
  );

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  // Check providers on initial load
  const checkProviders = useCallback(async () => {
    setProviderStatus((prev) => ({
      ...prev,
      backend: "checking",
      nebius: "checking",
    }));

    // Check backend health
    try {
      const health = await api.health();
      setProviderStatus((prev) => ({
        ...prev,
        backend: "online",
        backendDetails: `Service: ${health.service}`,
      }));
      addLog("info", `Backend online (${health.service})`, "system");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unreachable";
      setProviderStatus((prev) => ({
        ...prev,
        backend: "offline",
        backendDetails: msg,
      }));
      addLog("error", `Backend offline: ${msg}`, "system");
    }

    // Check Nebius provider
    try {
      const nebius = await api.testNebius();
      setProviderStatus((prev) => ({
        ...prev,
        nebius: "online",
        nebiusModel: nebius.model,
        nebiusDetails: "Model responding normally",
      }));
      addLog("info", `Nebius AI model connected: ${nebius.model}`, "system");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Provider error";
      const isUnconfigured =
        msg.includes("401") ||
        msg.includes("NEBIUS_API_KEY") ||
        msg.includes("unconfigured");
      setProviderStatus((prev) => ({
        ...prev,
        nebius: isUnconfigured ? "unconfigured" : "error",
        nebiusDetails: msg,
      }));
      addLog(
        isUnconfigured ? "warning" : "error",
        `Nebius check: ${msg}`,
        "system",
      );
    }
  }, [addLog]);

  // Load session from storage
  useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<WorkflowState>;
        setState((current) => ({
          ...current,
          ...parsed,
          stages: { ...current.stages, ...(parsed.stages ?? {}) },
        }));
      }

      const storedSessions = window.localStorage.getItem(SESSIONS_KEY);
      if (storedSessions) {
        setRecentSessions(JSON.parse(storedSessions));
      }
    } catch {
      // storage is optional
    }

    void checkProviders();
  }, [checkProviders]);

  // Persist workflow state
  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // storage is optional
    }
  }, [state]);

  const saveRecentSession = useCallback((question: string) => {
    if (!question.trim()) return;
    setRecentSessions((prev) => {
      const filtered = prev.filter((s) => s.question !== question);
      const updated = [
        {
          id: `${Date.now()}`,
          question: question.trim(),
          timestamp: new Date().toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
        ...filtered,
      ].slice(0, 8);
      try {
        window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(updated));
      } catch {
        // storage is optional
      }
      return updated;
    });
  }, []);

  const setStage = useCallback(
    (id: StageId, status: StageStatus, error?: string) => {
      setState((current) => ({
        ...current,
        stages: { ...current.stages, [id]: { status, error } },
      }));
    },
    [],
  );

  const failActiveStage = useCallback(
    (error: unknown) => {
      const stage = activeStage.current;
      const message =
        error instanceof Error ? error.message : "Unexpected pipeline failure";
      if (stage) {
        setStage(stage, "error", message);
        addLog("error", `Stage [${stage}] failed: ${message}`, stage);
      }
      return message;
    },
    [addLog, setStage],
  );

  const beginResearch = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed) return false;

      setBusy(true);
      setState({ ...INITIAL_STATE, question: trimmed });
      setSelectedNodeId("evidence");
      saveRecentSession(trimmed);
      addLog("info", `Initiated research: "${trimmed.slice(0, 70)}..."`, "system");

      try {
        // Stage 1: Evidence
        activeStage.current = "evidence";
        setStage("evidence", "running");
        addLog("info", "Stage 1: Querying scientific literature via Tavily...", "evidence");
        const evidenceRes = await api.collectEvidence(trimmed, 5);
        setState((current) => ({ ...current, evidence: evidenceRes.evidence }));
        setStage("evidence", "done");
        addLog(
          "success",
          `Stage 1: Retrieved ${evidenceRes.count} relevant research sources`,
          "evidence",
        );

        // Stage 2: Gap
        activeStage.current = "gap";
        setStage("gap", "running");
        setSelectedNodeId("gap");
        addLog("info", "Stage 2: Synthesizing literature and identifying research gaps...", "gap");
        const gap = await api.analyzeGap(trimmed, 5, evidenceRes.evidence);
        setState((current) => ({ ...current, gap }));
        setStage("gap", "done");
        addLog(
          "success",
          `Stage 2: Identified ${gap.potential_research_gaps.length} potential gaps (${gap.confidence_assessment.confidence_level} confidence)`,
          "gap",
        );

        // Stage 3: Hypothesis
        activeStage.current = "hypothesis";
        setStage("hypothesis", "running");
        setSelectedNodeId("hypothesis");
        addLog("info", "Stage 3: Formulating testable hypothesis and experimental design...", "hypothesis");
        const plan = await api.planExperiment(toStructuredGap(gap));
        setState((current) => ({ ...current, plan }));
        setStage("hypothesis", "done");
        addLog("success", `Stage 3: Designed hypothesis with baseline: ${plan.baseline.slice(0, 50)}...`, "hypothesis");

        // Stage 4: Experiment Code
        activeStage.current = "experiment";
        setStage("experiment", "running");
        setSelectedNodeId("experiment");
        addLog("info", "Stage 4: Generating runnable Python experiment code...", "experiment");
        const code = await api.generateCode(plan);
        setState((current) => ({ ...current, code }));
        setStage("experiment", "done");
        addLog("success", `Stage 4: Generated ${code.language} script with entrypoint ${code.entrypoint}`, "experiment");

        activeStage.current = null;
        return true;
      } catch (error) {
        failActiveStage(error);
        activeStage.current = null;
        return false;
      } finally {
        setBusy(false);
      }
    },
    [addLog, failActiveStage, saveRecentSession, setStage],
  );

  const runExperiment = useCallback(async (demo?: boolean) => {
    const code = stateRef.current.code;
    if (!code) {
      addLog("warning", "Cannot run experiment: No experiment code generated yet", "execution");
      return;
    }

    setBusy(true);
    setSelectedNodeId("execution");
    if (demo) {
      addLog("info", "Executing experiment in simulated demo mode (isolated environment)...", "execution");
    } else {
      addLog("info", "Submitting experiment to Nebius Serverless compute...", "execution");
    }

    try {
      activeStage.current = "execution";
      setStage("execution", "running");
      const submitted = await api.submitExperiment(code, demo);

      const job: ExperimentJobResponse = {
        job_id: submitted.job_id,
        status: submitted.status,
        nebius_job_id: null,
        research_question: submitted.research_question,
        error: submitted.error,
        submitted_at: new Date().toISOString(),
        result: null,
        is_demo: submitted.is_demo,
      };
      setState((current) => ({
        ...current,
        job,
        isDemo: current.isDemo || Boolean(submitted.is_demo),
      }));
      addLog(
        "info",
        `Job submitted [ID: ${submitted.job_id}${submitted.is_demo ? " - DEMO" : ""}]. Awaiting runner execution...`,
        "execution"
      );

      const deadline = Date.now() + 20 * 60 * 1000;
      while (Date.now() < deadline) {
        await sleep(2000);
        const updated = await api.getJob(submitted.job_id);
        setState((current) => ({
          ...current,
          job: updated,
          isDemo: current.isDemo || Boolean(updated.is_demo),
        }));

        if (TERMINAL_STATUSES.includes(updated.status)) {
          const isDone = updated.status === "completed";
          setStage("execution", isDone ? "done" : "error", updated.error ?? undefined);

          if (isDone) {
            addLog(
              "success",
              `Execution completed successfully in ${updated.result?.execution_time_seconds ?? 0}s${updated.is_demo ? " [DEMO]" : ""}`,
              "execution"
            );
          } else {
            addLog("error", `Execution ${updated.status}: ${updated.error ?? "Exit with non-zero code"}`, "execution");
          }

          if (updated.result) {
            setStage("results", "done");
            setState((current) => ({
              ...current,
              result: updated.result,
              isDemo: current.isDemo || Boolean(updated.result?.is_demo),
            }));
            addLog("success", "Collected experimental metrics and execution output", "results");
            setSelectedNodeId("results");
          }
          activeStage.current = null;
          return;
        }
      }

      throw new Error("The experiment did not finish within 20 minutes.");
    } catch (error) {
      failActiveStage(error);
      activeStage.current = null;
    } finally {
      setBusy(false);
    }
  }, [addLog, failActiveStage, setStage]);

  const runCritique = useCallback(async () => {
    const current = stateRef.current;
    if (!current.gap) {
      addLog("warning", "Cannot critique: Research gap has not been analyzed yet", "critic");
      return;
    }

    setBusy(true);
    setSelectedNodeId("critic");
    addLog("info", "Running adversarial peer review on experiment and findings...", "critic");

    try {
      activeStage.current = "critic";
      setStage("critic", "running");
      const critique = await api.critique({
        research_question: current.question,
        hypothesis: current.plan?.hypothesis ?? "",
        research_gap: toStructuredGap(current.gap),
        experiment_design: current.plan,
        experiment_results: current.result,
      });
      setState((prev) => ({ ...prev, critique }));
      setStage("critic", "done");
      addLog(
        "success",
        `Critique complete: Verdict: ${critique.verdict.slice(0, 50)}... (Confidence: ${Math.round(critique.confidence_score * 100)}%)`,
        "critic",
      );
      activeStage.current = null;
    } catch (error) {
      failActiveStage(error);
      activeStage.current = null;
    } finally {
      setBusy(false);
    }
  }, [addLog, failActiveStage, setStage]);

  const runReport = useCallback(async () => {
    const current = stateRef.current;
    if (!current.question) {
      addLog("warning", "Cannot generate report: No active research question", "report");
      return;
    }

    setBusy(true);
    setSelectedNodeId("report");
    addLog("info", "Synthesizing comprehensive final research report...", "report");

    try {
      activeStage.current = "report";
      setStage("report", "running");
      const report = await api.generateReport({
        research_question: current.question,
        evidence: current.evidence,
        research_gap: current.gap ? toStructuredGap(current.gap) : null,
        hypothesis: current.plan?.hypothesis ?? "",
        experiment_plan: current.plan,
        experiment_results: current.result,
        research_critique: current.critique,
      });
      setState((prev) => ({ ...prev, report }));
      setStage("report", "done");
      addLog("success", `Final research report generated: "${report.title}"`, "report");
      activeStage.current = null;
    } catch (error) {
      failActiveStage(error);
      activeStage.current = null;
    } finally {
      setBusy(false);
    }
  }, [addLog, failActiveStage, setStage]);

  const runRemaining = useCallback(async () => {
    if (stateRef.current.code && !stateRef.current.result) {
      await runExperiment();
    }
    if (stateRef.current.gap && !stateRef.current.critique) {
      await runCritique();
    }
    if (stateRef.current.question && !stateRef.current.report) {
      await runReport();
    }
  }, [runCritique, runExperiment, runReport]);

  const retryStage = useCallback(
    async (stageId: StageId) => {
      const current = stateRef.current;
      addLog("info", `Retrying stage: ${stageId}...`, stageId);
      switch (stageId) {
        case "evidence":
        case "gap":
        case "hypothesis":
        case "experiment":
          await beginResearch(current.question);
          break;
        case "execution":
        case "results":
          await runExperiment();
          break;
        case "critic":
          await runCritique();
          break;
        case "report":
          await runReport();
          break;
      }
    },
    [addLog, beginResearch, runCritique, runExperiment, runReport],
  );

  const loadDemoData = useCallback(() => {
    const demoQuestion =
      "Does self-supervised pretraining on scientific corpora improve sample efficiency for protein structure prediction?";

    const demoEvidence: EvidenceItem[] = [
      {
        title: "Biological Structure and Sequence Representation Learning with ESM-2",
        url: "https://www.biorxiv.org/content/10.1101/2022.07.20.500902v1",
        source: "bioRxiv",
        snippet:
          "Language models trained on millions of evolutionary sequences capture atomic-level structural constraints without explicit physical simulation, boosting downstream structure prediction efficiency.",
      },
      {
        title: "Highly accurate protein structure prediction with AlphaFold",
        url: "https://www.nature.com/articles/s41586-021-03819-2",
        source: "Nature",
        snippet:
          "AlphaFold demonstrates that incorporating evolutionary multi-sequence alignments (MSAs) dramatically reduces the required sample complexity for de novo folding.",
      },
      {
        title: "Self-Supervised Pre-Training of Protein Embeddings for Structural Ensembles",
        url: "https://arxiv.org/abs/2301.04221",
        source: "arXiv:q-bio",
        snippet:
          "Pretrained masked amino-acid models reduce fine-tuning steps by 4.2x compared to random initialization across CASP14 target benchmarks.",
      },
    ];

    const demoGap: ResearchGapResponse = {
      research_question: demoQuestion,
      established_findings: [
        {
          claim:
            "Pretrained masked sequence transformers learn biophysical contacts and secondary structure motifs implicitly.",
          evidence_refs: ["https://www.biorxiv.org/content/10.1101/2022.07.20.500902v1"],
        },
        {
          claim:
            "MSA-based representations remain computationally heavy during inference for orphan proteins.",
          evidence_refs: ["https://www.nature.com/articles/s41586-021-03819-2"],
        },
      ],
      conflicting_findings: [
        {
          claim:
            "Whether scientific literature text corpora (PubMed) adds complementary inductive bias over raw FASTA sequence corpora remains contested.",
          evidence_refs: ["https://arxiv.org/abs/2301.04221"],
        },
      ],
      limitations: [
        {
          claim:
            "Existing benchmarks rely heavily on high-homology proteins in PDB, masking out-of-distribution sample efficiency gains.",
          evidence_refs: [],
        },
      ],
      missing_evidence: [
        "Systematic ablation of vocabulary size vs. contact map precision under low-sample (<100 target) regimes.",
      ],
      potential_research_gaps: [
        "Quantifying convergence rate acceleration when pretraining jointly on scientific text and amino-acid sequence tokens.",
        "Evaluating sample complexity on orphan proteins without known homologous families.",
      ],
      confidence_assessment: {
        confidence_level: "high",
        reliability_score: 0.88,
        reasoning:
          "Strong peer-reviewed consensus on sequence-based pretraining; clear empirical open question regarding multi-modal corpus integration.",
      },
      evidence_count: demoEvidence.length,
      evidence: demoEvidence,
    };

    const demoPlan: ExperimentPlanResponse = {
      research_question: demoQuestion,
      hypothesis:
        "Joint pretraining on scientific domain text and primary amino-acid sequences reduces downstream fine-tuning steps by >= 35% to reach TM-score > 0.70 compared to sequence-only pretraining.",
      research_objective:
        "Measure downstream sample efficiency curves across 5 training set size tiers (50, 100, 250, 500, 1000 targets).",
      variables: {
        independent: ["Pretraining corpus modality (Text+Seq vs. Seq-only vs. Random baseline)"],
        dependent: ["Sample efficiency (steps to TM-score 0.70)", "Final mean GDT-TS score"],
        controls: ["Architecture parameter count (85M)", "Batch size (32)", "Optimizer (AdamW, lr=1e-4)"],
      },
      baseline: "ESM-2 85M sequence-only pretrained model fine-tuned on CASP14 target split.",
      proposed_method:
        "Dual-tower cross-attention encoder fine-tuned on synthetic contact map prediction and backbone coordinate regression.",
      dataset_requirements: ["CASP14 & CAMEO validation targets", "PDB redundant clusters filtered at 30% sequence identity"],
      evaluation_metrics: ["TM-score", "GDT-TS", "Contact map precision at L/5", "Gradient steps to convergence"],
      expected_outcome:
        "Text-augmented representations accelerate initial epoch loss reduction by 40% on fold-classification targets.",
      risks: [
        "Overfitting on high-frequency literature terms",
        "Disjoint vocabulary tokenization bottleneck",
      ],
      model: "nvidia/nemotron-4-340b-instruct",
    };

    const demoCode: ExperimentCodeResponse = {
      research_question: demoQuestion,
      language: "python",
      code: `"""
[DEMO DATA - NOT ACTUAL RESEARCH]
Controlled sample-efficiency benchmark for protein representation pretraining.
"""
import time
import numpy as np

def run_sample_efficiency_trial(corpus_mode: str, num_samples: int, seed: int = 42):
    rng = np.random.default_rng(seed)
    print(f"[*] Initializing evaluation trial: mode={corpus_mode}, n={num_samples}")
    
    # Simulate convergence trajectory
    epochs = 20
    convergence_step = int(rng.normal(loc=12 if corpus_mode == 'joint_text_seq' else 19, scale=1.5))
    tm_score = min(0.89, float(0.55 + 0.025 * np.log(num_samples + 1) + (0.08 if corpus_mode == 'joint_text_seq' else 0.0)))
    gdt_ts = float(tm_score * 0.92)
    
    time.sleep(0.5)
    return {
        "corpus_mode": corpus_mode,
        "sample_size": num_samples,
        "steps_to_threshold": max(6, convergence_step),
        "tm_score": round(tm_score, 4),
        "gdt_ts": round(gdt_ts, 4),
        "efficiency_gain_pct": 36.8 if corpus_mode == 'joint_text_seq' else 0.0
    }

if __name__ == "__main__":
    results = run_sample_efficiency_trial("joint_text_seq", 250)
    print(f"[RESULT] {results}")
`,
      dependencies: ["numpy>=1.24.0", "scipy>=1.10.0"],
      entrypoint: "python experiment.py",
      random_seed: 42,
      inputs: ["casp14_subset_250.h5"],
      outputs: ["metrics.json", "convergence_curve.png"],
      model: "nvidia/nemotron-4-340b-instruct",
      notes: "Demonstration script configured with deterministic random seed.",
    };

    const demoResult: ExperimentExecutionResult = {
      job_id: "demo-job-8849-sample-efficiency",
      status: "completed",
      exit_code: 0,
      stdout: `[*] Initializing evaluation trial: mode=joint_text_seq, n=250
[*] Model parameter count: 85,214,400
[*] Training progress: 20/20 epochs completed
[*] Evaluated against CASP14 target set (n=250)
[RESULT] {'corpus_mode': 'joint_text_seq', 'sample_size': 250, 'steps_to_threshold': 11, 'tm_score': 0.7842, 'gdt_ts': 0.7215, 'efficiency_gain_pct': 36.8}`,
      stderr: "",
      metrics: {
        tm_score: 0.7842,
        gdt_ts: 0.7215,
        steps_to_threshold: 11,
        efficiency_gain_pct: 36.8,
        contact_precision_l5: 0.812,
        inference_latency_ms: 14.6,
      },
      execution_time_seconds: 4.82,
      error: null,
      research_question: demoQuestion,
    };

    const demoJob: ExperimentJobResponse = {
      job_id: demoResult.job_id,
      status: "completed",
      nebius_job_id: "nebius-srvless-demo-4482",
      research_question: demoQuestion,
      error: null,
      submitted_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      result: demoResult,
    };

    const demoCritique: ResearchCriticResponse = {
      research_question: demoQuestion,
      verdict:
        "The empirical findings tentatively corroborate the sample-efficiency hypothesis, but critical confounding variables must be isolated before causal claims can be generalized.",
      hypothesis_supported: true,
      strengths: [
        {
          category: "Methodological Rigor",
          finding:
            "Controlled baseline with identical model architectures isolates the corpus difference effectively.",
          severity: "low",
        },
        {
          category: "Metric Relevance",
          finding:
            "Using standard TM-score and GDT-TS metrics ensures compatibility with CASP community standards.",
          severity: "low",
        },
      ],
      weaknesses: [
        {
          category: "Generalization Scope",
          finding:
            "CASP14 sample size (250) has limited coverage of multi-domain transmembrane complexes.",
          severity: "medium",
        },
        {
          category: "Leakage Risk",
          finding:
            "Scientific text corpora may contain structural coordinates described in publication text, risking evaluation leakage.",
          severity: "high",
        },
      ],
      threats_to_validity: [
        {
          category: "Construct Validity",
          finding:
            "Pretraining duration was not strictly compute-normalized between text-sequence and sequence-only runs.",
          severity: "medium",
        },
      ],
      recommended_followup: [
        "Ablate text-token masking to explicitly filter out PDB IDs and structural coordinate tables from training text.",
        "Benchmark across orphan proteins in the CAMEO continuous validation set.",
      ],
      confidence_score: 0.84,
      model: "nvidia/nemotron-4-340b-instruct",
    };

    const demoReport: ResearchReportResponse = {
      research_question: demoQuestion,
      title:
        "Autonomous Investigation: Multi-Modal Pretraining Synergies in Sample-Efficient Protein Structure Prediction",
      sections: [
        {
          key: "executive_summary",
          title: "Executive Summary",
          content:
            "This investigation systematically analyzed whether integrating scientific literature corpora with primary amino-acid sequences accelerates structural representation learning. Under a 250-target sample constraint, joint pretraining attained TM-score > 0.70 in 36.8% fewer gradient updates compared to sequence-only baselines.",
          evidence_refs: ["https://www.biorxiv.org/content/10.1101/2022.07.20.500902v1"],
        },
        {
          key: "methodology",
          title: "Experimental Methodology & Controls",
          content:
            "A dual-tower transformer was evaluated across controlled sample tiers (50 through 1,000 targets) with identical batch size and optimizer hyper-parameters. Downstream contact prediction precision was tracked across all CASP14 domains.",
          evidence_refs: ["https://www.nature.com/articles/s41586-021-03819-2"],
        },
        {
          key: "critical_findings",
          title: "Critical Findings & Adversarial Evaluation",
          content:
            "While statistical gains were confirmed (TM-score 0.7842 vs baseline 0.6910), adversarial critique identified potential textual leakage of PDB annotations. Mitigations require string-sanitization of literature pretraining sets.",
          evidence_refs: ["https://arxiv.org/abs/2301.04221"],
        },
      ],
      sources: demoEvidence,
      confidence_assessment: {
        confidence_level: "high",
        reliability_score: 0.86,
        reasoning:
          "Statistically significant sample efficiency gain observed across replicated random seeds with documented adversarial boundaries.",
      },
      generated_at: new Date().toISOString(),
      model: "nvidia/nemotron-4-340b-instruct",
    };

    const allDoneStages: Record<StageId, StageState> = STAGES.reduce(
      (acc, s) => {
        acc[s.id] = { status: "done" };
        return acc;
      },
      {} as Record<StageId, StageState>,
    );

    setState({
      question: demoQuestion,
      stages: allDoneStages,
      evidence: demoEvidence,
      gap: demoGap,
      plan: demoPlan,
      code: demoCode,
      job: demoJob,
      result: demoResult,
      critique: demoCritique,
      report: demoReport,
      isDemo: true,
    });

    setSelectedNodeId("core");
    saveRecentSession(demoQuestion);
    setLogs([
      {
        id: "demo-log-1",
        timestamp: formatTime(),
        stageId: "system",
        type: "info",
        message: "Loaded complete demonstration research workflow dataset [DEMO MODE]",
      },
      {
        id: "demo-log-2",
        timestamp: formatTime(),
        stageId: "report",
        type: "success",
        message: "Final report and adversarial critique synthesized successfully",
      },
      {
        id: "demo-log-3",
        timestamp: formatTime(),
        stageId: "execution",
        type: "success",
        message: "Simulated Nebius serverless execution completed (exit code 0)",
      },
    ]);
  }, [saveRecentSession]);

  const reset = useCallback(() => {
    setState(INITIAL_STATE);
    setSelectedNodeId("core");
    setLogs([]);
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // storage is optional
    }
  }, []);

  const value = useMemo(
    () => ({
      state,
      busy,
      selectedNodeId,
      setSelectedNodeId,
      logs,
      clearLogs,
      recentSessions,
      providerStatus,
      checkProviders,
      beginResearch,
      runExperiment,
      runCritique,
      runReport,
      runRemaining,
      retryStage,
      loadDemoData,
      reset,
    }),
    [
      state,
      busy,
      selectedNodeId,
      setSelectedNodeId,
      logs,
      clearLogs,
      recentSessions,
      providerStatus,
      checkProviders,
      beginResearch,
      runExperiment,
      runCritique,
      runReport,
      runRemaining,
      retryStage,
      loadDemoData,
      reset,
    ],
  );

  return (
    <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>
  );
}

export function useWorkflow(): WorkflowContextValue {
  const context = useContext(WorkflowContext);
  if (!context) {
    throw new Error("useWorkflow must be used inside a WorkflowProvider");
  }
  return context;
}
