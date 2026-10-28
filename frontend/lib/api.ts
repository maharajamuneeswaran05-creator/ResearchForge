// Thin client for the ResearchForge backend API.
// All business logic lives in the backend; this module only performs requests.

import type {
  EvidenceItem,
  EvidenceResponse,
  ExperimentCodeResponse,
  ExperimentExecutionResult,
  ExperimentJobResponse,
  ExperimentPlanResponse,
  ResearchCriticResponse,
  ResearchGapResponse,
  ResearchReportResponse,
  StructuredResearchGap,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "Cannot reach the ResearchForge backend. Is it running on port 8000?",
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }

  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail) return JSON.stringify(detail);
  } catch {
    // fall through to the status text
  }
  return `Request failed with status ${response.status}`;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export const api = {
  health: () => request<{ status: string; service: string }>("/health"),

  testNebius: () =>
    request<{ ok: boolean; model: string; reply: string }>("/test/nebius"),

  collectEvidence: (researchQuestion: string, maxResults = 5) =>
    post<EvidenceResponse>("/api/research/evidence", {
      research_question: researchQuestion,
      max_results: maxResults,
    }),

  analyzeGap: (
    researchQuestion: string,
    maxResults: number,
    evidence: EvidenceItem[],
  ) =>
    post<ResearchGapResponse>("/api/research/gap", {
      research_question: researchQuestion,
      max_results: maxResults,
      evidence,
    }),

  planExperiment: (researchGap: StructuredResearchGap) =>
    post<ExperimentPlanResponse>("/api/research/experiment-plan", {
      research_gap: researchGap,
    }),

  generateCode: (experimentPlan: ExperimentPlanResponse) =>
    post<ExperimentCodeResponse>("/api/research/experiment-code", {
      experiment_plan: experimentPlan,
    }),

  submitExperiment: (experimentCode: ExperimentCodeResponse, demo?: boolean) =>
    post<ExperimentExecutionResult>("/api/research/experiment-execute", {
      experiment_code: experimentCode,
      wait: false,
      ...(demo !== undefined ? { demo } : {}),
    }),

  getJob: (jobId: string) =>
    request<ExperimentJobResponse>(
      `/api/research/experiment-jobs/${encodeURIComponent(jobId)}`,
    ),

  critique: (payload: {
    research_question: string;
    hypothesis: string;
    research_gap?: StructuredResearchGap | null;
    experiment_design?: ExperimentPlanResponse | null;
    experiment_results?: ExperimentExecutionResult | null;
  }) => post<ResearchCriticResponse>("/api/research/critic", payload),

  generateReport: (payload: {
    research_question: string;
    evidence: EvidenceItem[];
    research_gap?: StructuredResearchGap | null;
    hypothesis?: string;
    experiment_plan?: ExperimentPlanResponse | null;
    experiment_results?: ExperimentExecutionResult | null;
    research_critique?: ResearchCriticResponse | null;
  }) => post<ResearchReportResponse>("/api/research/report", payload),
};
