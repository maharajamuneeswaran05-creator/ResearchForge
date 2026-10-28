// Mirrors of the backend response contracts (backend/app/schemas/research.py).
// Only the fields the UI renders are modelled.

export interface EvidenceItem {
  title: string;
  url: string;
  source: string;
  snippet: string;
}

export interface EvidenceResponse {
  research_question: string;
  evidence: EvidenceItem[];
  count: number;
}

export interface FindingWithEvidence {
  claim: string;
  evidence_refs: string[];
}

export interface ConfidenceAssessment {
  confidence_level: "high" | "medium" | "low";
  reliability_score: number;
  reasoning: string;
}

export interface ResearchGapResponse {
  research_question: string;
  established_findings: FindingWithEvidence[];
  conflicting_findings: FindingWithEvidence[];
  limitations: FindingWithEvidence[];
  missing_evidence: string[];
  potential_research_gaps: string[];
  confidence_assessment: ConfidenceAssessment;
  evidence_count: number;
  evidence: EvidenceItem[];
}

export interface StructuredResearchGap {
  research_question: string;
  potential_research_gaps: string[];
  missing_evidence: string[];
  established_findings: FindingWithEvidence[];
  conflicting_findings: FindingWithEvidence[];
  limitations: FindingWithEvidence[];
  confidence_assessment?: ConfidenceAssessment | null;
}

export interface ExperimentVariables {
  independent: string[];
  dependent: string[];
  controls: string[];
}

export interface ExperimentPlanResponse {
  research_question: string;
  hypothesis: string;
  research_objective: string;
  variables: ExperimentVariables;
  baseline: string;
  proposed_method: string;
  dataset_requirements: string[];
  evaluation_metrics: string[];
  expected_outcome: string;
  risks: string[];
  model: string;
}

export interface ExperimentCodeResponse {
  research_question: string;
  language: string;
  code: string;
  dependencies: string[];
  entrypoint: string;
  random_seed: number;
  inputs: string[];
  outputs: string[];
  model: string;
  notes?: string | null;
}

export type ExperimentJobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "timeout"
  | "cancelled";

export interface ExperimentExecutionResult {
  job_id: string;
  status: ExperimentJobStatus;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  metrics: Record<string, unknown>;
  execution_time_seconds: number;
  error: string | null;
  research_question: string;
  is_demo?: boolean;
}

export interface ExperimentJobResponse {
  job_id: string;
  status: ExperimentJobStatus;
  nebius_job_id: string | null;
  research_question: string;
  error: string | null;
  submitted_at: string | null;
  result: ExperimentExecutionResult | null;
  is_demo?: boolean;
}

export interface CriticItem {
  category: string;
  finding: string;
  severity: "low" | "medium" | "high";
}

export interface ResearchCriticResponse {
  research_question: string;
  verdict: string;
  hypothesis_supported: boolean | null;
  strengths: CriticItem[];
  weaknesses: CriticItem[];
  threats_to_validity: CriticItem[];
  recommended_followup: string[];
  confidence_score: number;
  model: string;
}

export interface ResearchReportSection {
  key: string;
  title: string;
  content: string;
  evidence_refs: string[];
  confidence?: ConfidenceAssessment | null;
}

export interface ResearchReportResponse {
  research_question: string;
  title: string;
  sections: ResearchReportSection[];
  sources: EvidenceItem[];
  confidence_assessment: ConfidenceAssessment;
  generated_at: string;
  model: string;
  markdown?: string;
}

