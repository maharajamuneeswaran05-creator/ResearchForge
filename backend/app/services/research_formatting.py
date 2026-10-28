"""Shared prompt formatting for research artefacts.

Used by the research critic and the research report generator so that both
phases present the same artefacts to Nemotron in the same way.
"""

from __future__ import annotations

from typing import Any

from app.schemas.research import (
    EvidenceItem,
    ExperimentExecutionResult,
    ExperimentPlanResponse,
    ResearchCriticResponse,
    StructuredResearchGap,
)

# Maximum number of characters of captured output forwarded to the model.
MAX_STDOUT_CHARS = 4000
MAX_STDERR_CHARS = 2000


def format_gap(gap: StructuredResearchGap) -> str:
    """Render a structured research gap as prompt text."""

    def _claims(items: list[Any]) -> str:
        if not items:
            return "  (none)"
        lines = []
        for item in items:
            claim = getattr(item, "claim", str(item))
            refs = getattr(item, "evidence_refs", []) or []
            refs_text = f" [refs: {', '.join(refs)}]" if refs else ""
            lines.append(f"  - {claim}{refs_text}")
        return "\n".join(lines)

    confidence = gap.confidence_assessment
    confidence_text = (
        f"level={confidence.confidence_level}, "
        f"reliability={confidence.reliability_score}"
        if confidence
        else "not assessed"
    )

    return (
        "Potential research gaps:\n"
        + ("\n".join(f"  - {g}" for g in gap.potential_research_gaps) or "  (none)")
        + "\nMissing evidence:\n"
        + ("\n".join(f"  - {m}" for m in gap.missing_evidence) or "  (none)")
        + "\nEstablished findings:\n"
        + _claims(gap.established_findings)
        + "\nConflicting findings:\n"
        + _claims(gap.conflicting_findings)
        + "\nLimitations:\n"
        + _claims(gap.limitations)
        + f"\nGap confidence: {confidence_text}"
    )


def format_design(design: ExperimentPlanResponse) -> str:
    """Render an experiment plan as prompt text."""
    variables = design.variables
    return (
        f"Objective: {design.research_objective}\n"
        f"Baseline: {design.baseline}\n"
        f"Proposed method: {design.proposed_method}\n"
        f"Independent variables: {', '.join(variables.independent)}\n"
        f"Dependent variables: {', '.join(variables.dependent)}\n"
        f"Controls: {', '.join(variables.controls) or '(none)'}\n"
        f"Dataset requirements: {'; '.join(design.dataset_requirements)}\n"
        f"Evaluation metrics: {', '.join(design.evaluation_metrics)}\n"
        f"Expected outcome: {design.expected_outcome}\n"
        f"Risks: {'; '.join(design.risks) if design.risks else '(none listed)'}"
    )


def format_results(results: ExperimentExecutionResult) -> str:
    """Render an experiment execution result as prompt text."""
    metrics = (
        "\n".join(f"  - {key} = {value}" for key, value in results.metrics.items())
        or "  (no metrics reported)"
    )
    stdout = results.stdout or ""
    stderr = results.stderr or ""
    return (
        f"Status: {results.status.value}\n"
        f"Exit code: {results.exit_code}\n"
        f"Execution time: {results.execution_time_seconds:.3f}s\n"
        f"Error: {results.error or '(none)'}\n"
        f"Metrics:\n{metrics}\n"
        f"stdout (first {MAX_STDOUT_CHARS} chars):\n"
        f"{stdout[:MAX_STDOUT_CHARS] or '(empty)'}\n"
        f"stderr (first {MAX_STDERR_CHARS} chars):\n"
        f"{stderr[:MAX_STDERR_CHARS] or '(empty)'}"
    )


def format_evidence(evidence: list[EvidenceItem]) -> str:
    """Render retrieved evidence as prompt text, preserving URLs."""
    if not evidence:
        return "(no evidence was retrieved)"
    blocks: list[str] = []
    for index, item in enumerate(evidence, start=1):
        blocks.append(
            f"[{index}] Title: {item.title}\n"
            f"    Source: {item.source} | URL: {item.url}\n"
            f"    Snippet: {item.snippet}"
        )
    return "\n\n".join(blocks)


def format_critique(critique: ResearchCriticResponse) -> str:
    """Render a research critique as prompt text."""

    def _items(items: list[Any]) -> str:
        if not items:
            return "  (none)"
        return "\n".join(
            f"  - [{item.category}] {item.finding} (severity: {item.severity})"
            for item in items
        )

    supported = critique.hypothesis_supported
    supported_text = (
        "not stated" if supported is None else ("yes" if supported else "no")
    )
    followup = (
        "\n".join(f"  - {item}" for item in critique.recommended_followup)
        if critique.recommended_followup
        else "  (none)"
    )
    return (
        f"Verdict: {critique.verdict}\n"
        f"Results support the hypothesis: {supported_text}\n"
        f"Critique confidence: {critique.confidence_score:.2f}\n"
        f"Strengths:\n{_items(critique.strengths)}\n"
        f"Weaknesses:\n{_items(critique.weaknesses)}\n"
        f"Threats to validity:\n{_items(critique.threats_to_validity)}\n"
        f"Recommended follow-up:\n{followup}"
    )
