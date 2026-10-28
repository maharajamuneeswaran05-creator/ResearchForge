from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    service: str = Field(examples=["researchforge-backend"])


class NebiusTestResponse(BaseModel):
    ok: bool
    model: str
    reply: str | None = None
    error: str | None = None


class ResearchTestRequest(BaseModel):
    research_question: str = Field(..., min_length=1)


class ResearchTestResponse(BaseModel):
    research_question: str
    model: str
    response: str


class EvidenceRequest(BaseModel):
    research_question: str = Field(..., min_length=1)
    max_results: int | None = Field(default=None, ge=1, le=20)


class EvidenceItem(BaseModel):
    title: str
    url: str
    source: str
    snippet: str


class EvidenceResponse(BaseModel):
    research_question: str
    evidence: list[EvidenceItem]
    count: int


class FindingWithEvidence(BaseModel):
    claim: str = Field(description="Summary of the finding or limitation")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Source, title, or URL references from the evidence supporting this claim",
    )

    @classmethod
    def from_raw(cls, item: Any) -> "FindingWithEvidence":
        if isinstance(item, dict):
            return cls(
                claim=str(item.get("claim") or item.get("finding") or item.get("description") or "").strip(),
                evidence_refs=[str(ref) for ref in (item.get("evidence_refs") or item.get("references") or [])],
            )
        return cls(claim=str(item).strip(), evidence_refs=[])


class ConfidenceAssessment(BaseModel):
    confidence_level: str = Field(
        description="Confidence level: high, medium, or low"
    )
    reliability_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Reliability score between 0.0 and 1.0",
    )
    reasoning: str = Field(
        description="Justification based on evidence coverage and study consistency"
    )


class ResearchGapRequest(BaseModel):
    research_question: str = Field(..., min_length=1)
    max_results: int | None = Field(default=None, ge=1, le=20)
    evidence: list[EvidenceItem] | None = Field(
        default=None,
        description="Optional pre-collected evidence. If omitted, fetched via Tavily.",
    )


class ResearchGapResponse(BaseModel):
    research_question: str
    established_findings: list[FindingWithEvidence]
    conflicting_findings: list[FindingWithEvidence]
    limitations: list[FindingWithEvidence]
    missing_evidence: list[str]
    potential_research_gaps: list[str]
    confidence_assessment: ConfidenceAssessment
    evidence_count: int
    evidence: list[EvidenceItem] = Field(default_factory=list)

class StructuredResearchGap(BaseModel):
    """Structured research-gap input for experiment planning."""

    research_question: str = Field(..., min_length=1)
    potential_research_gaps: list[str] = Field(..., min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    established_findings: list[FindingWithEvidence] = Field(default_factory=list)
    conflicting_findings: list[FindingWithEvidence] = Field(default_factory=list)
    limitations: list[FindingWithEvidence] = Field(default_factory=list)
    confidence_assessment: ConfidenceAssessment | None = None


class ExperimentVariables(BaseModel):
    independent: list[str] = Field(..., min_length=1)
    dependent: list[str] = Field(..., min_length=1)
    controls: list[str] = Field(default_factory=list)


class ExperimentPlanRequest(BaseModel):
    research_gap: StructuredResearchGap


class ExperimentPlanResponse(BaseModel):
    research_question: str
    hypothesis: str = Field(..., min_length=1)
    research_objective: str = Field(..., min_length=1)
    variables: ExperimentVariables
    baseline: str = Field(..., min_length=1, description="Required baseline comparison")
    proposed_method: str = Field(..., min_length=1)
    dataset_requirements: list[str] = Field(..., min_length=1)
    evaluation_metrics: list[str] = Field(
        ...,
        min_length=1,
        description="Measurable evaluation metrics",
    )
    expected_outcome: str = Field(..., min_length=1)
    risks: list[str] = Field(default_factory=list)
    model: str


class ExperimentCodeRequest(BaseModel):
    """Validated experiment plan used to generate runnable Python code."""

    experiment_plan: ExperimentPlanResponse


class ExperimentCodeResponse(BaseModel):
    research_question: str
    language: str = "python"
    code: str = Field(..., min_length=1)
    dependencies: list[str] = Field(default_factory=list)
    entrypoint: str = "python experiment.py"
    random_seed: int = 42
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    model: str
    notes: str | None = None


class ExperimentJobStatus(str, Enum):
    """Lifecycle of an experiment executed on Nebius Serverless AI."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ExperimentExecutionResult(BaseModel):
    """Outcome of a single experiment execution."""

    job_id: str
    status: ExperimentJobStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    execution_time_seconds: float = 0.0
    error: str | None = None
    research_question: str = ""
    is_demo: bool = Field(
        default=False,
        description="True if execution was simulated in demo mode, False for real Nebius runs",
    )


class ExperimentExecuteRequest(BaseModel):
    """Approved experiment code to execute on Nebius Serverless AI."""

    experiment_code: ExperimentCodeResponse
    timeout_seconds: float | None = Field(default=None, gt=0, le=86400)
    wait: bool = Field(
        default=True,
        description=(
            "Wait for the job to finish and return the full result. When false "
            "the job is only submitted and its status must be polled."
        ),
    )
    demo: bool | None = Field(
        default=None,
        description=(
            "Explicitly run in local demo mode when Nebius Cloud is unconfigured. "
            "Demo executions are clearly tagged and do not claim to be real runs."
        ),
    )


class ExperimentJobResponse(BaseModel):
    """Status of a submitted experiment job."""

    job_id: str
    status: ExperimentJobStatus
    nebius_job_id: str | None = None
    research_question: str = ""
    error: str | None = None
    submitted_at: str | None = None
    result: ExperimentExecutionResult | None = None
    is_demo: bool = False


class CriticItem(BaseModel):
    """A single finding produced by the research critic."""

    category: str = Field(
        description=(
            "Evaluation dimension: methodology, baseline_quality, evidence_quality, "
            "statistical_reasoning, bias, confounding_factors, reproducibility, "
            "hypothesis_support, alternative_explanations, limitations"
        )
    )
    finding: str
    severity: str = Field(default="medium", description="low, medium, or high")

    @classmethod
    def from_raw(cls, item: Any) -> "CriticItem":
        if isinstance(item, dict):
            category = str(
                item.get("category") or item.get("dimension") or "general"
            ).strip()
            finding = str(
                item.get("finding")
                or item.get("claim")
                or item.get("description")
                or ""
            ).strip()
            severity = str(item.get("severity") or "medium").strip().lower()
            if severity not in ("low", "medium", "high"):
                severity = "medium"
            return cls(
                category=category or "general",
                finding=finding,
                severity=severity,
            )
        return cls(category="general", finding=str(item).strip(), severity="medium")


class ResearchCriticRequest(BaseModel):
    """Research artefacts submitted for critical evaluation."""

    research_question: str = Field(..., min_length=1)
    hypothesis: str = Field(..., min_length=1)
    research_gap: StructuredResearchGap | None = None
    experiment_design: ExperimentPlanResponse | None = None
    experiment_results: ExperimentExecutionResult | None = None
    additional_context: str | None = None


class ResearchCriticResponse(BaseModel):
    """Skeptical critique of an experiment and its results."""

    research_question: str
    verdict: str
    hypothesis_supported: bool | None = Field(
        default=None,
        description="Whether the results support the hypothesis, per the critic",
    )
    strengths: list[CriticItem] = Field(default_factory=list)
    weaknesses: list[CriticItem] = Field(default_factory=list)
    threats_to_validity: list[CriticItem] = Field(default_factory=list)
    recommended_followup: list[str] = Field(default_factory=list)
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in the critique itself, between 0.0 and 1.0",
    )
    model: str


class ResearchReportSection(BaseModel):
    """One section of the generated research report."""

    key: str = Field(description="Stable section identifier, e.g. 'methodology'")
    title: str
    content: str = ""
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="URLs of the supplied evidence referenced by this section",
    )
    confidence: ConfidenceAssessment | None = None


class ResearchReportRequest(BaseModel):
    """Research artefacts used to generate the final report."""

    research_question: str = Field(..., min_length=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    research_gap: StructuredResearchGap | None = None
    hypothesis: str = ""
    experiment_plan: ExperimentPlanResponse | None = None
    experiment_results: ExperimentExecutionResult | None = None
    research_critique: ResearchCriticResponse | None = None
    additional_context: str | None = None


class ResearchReportResponse(BaseModel):
    """Structured final research report."""

    research_question: str
    title: str
    sections: list[ResearchReportSection]
    sources: list[EvidenceItem] = Field(
        default_factory=list,
        description="Retrieved evidence, preserved verbatim with source URLs",
    )
    confidence_assessment: ConfidenceAssessment
    generated_at: str
    model: str
    markdown: str = ""


