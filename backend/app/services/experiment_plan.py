"""Experiment planning service: Research Gap -> Hypothesis + Experiment Plan."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.schemas.research import (
    ExperimentPlanResponse,
    ExperimentVariables,
    FindingWithEvidence,
    StructuredResearchGap,
)
from app.services.nebius import NebiusClient, NebiusError
from app.services.research_gap import ResearchGapError, ResearchGapService

logger = logging.getLogger(__name__)


class ExperimentPlanError(Exception):
    """Raised when experiment planning fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ExperimentPlanService:
    """Generate a testable hypothesis and experiment plan from a structured research gap."""

    def __init__(self, nebius_client: NebiusClient) -> None:
        self._nebius = nebius_client

    async def plan(self, research_gap: StructuredResearchGap) -> ExperimentPlanResponse:
        system_message = (
            "You are a scientific experiment designer. Given a structured research gap, "
            "produce a testable hypothesis and a concrete experiment plan.\n"
            "Return ONLY a valid JSON object. No markdown, no preamble."
        )
        user_message = self._build_prompt(research_gap)

        try:
            payload = await self._nebius.chat_completion(
                user_message=user_message,
                system_message=system_message,
                max_tokens=1800,
                temperature=0.2,
            )
            raw_text = self._nebius.extract_assistant_text(payload)
        except NebiusError as exc:
            raise ExperimentPlanError(
                f"Nemotron experiment planning failed: {exc}",
                status_code=exc.status_code,
            ) from exc

        try:
            data = ResearchGapService._extract_json(raw_text)
        except ResearchGapError as exc:
            raise ExperimentPlanError(
                f"Failed to parse experiment plan JSON: {exc}",
                status_code=exc.status_code or 502,
            ) from exc
        return self._build_response(research_gap.research_question, data)

    @staticmethod
    def _build_prompt(gap: StructuredResearchGap) -> str:
        def _findings(items: list[FindingWithEvidence]) -> str:
            if not items:
                return "[]"
            lines = []
            for item in items:
                refs = ", ".join(item.evidence_refs) if item.evidence_refs else "n/a"
                lines.append(f"- {item.claim} (refs: {refs})")
            return "\n".join(lines)

        return (
            f"Research Question: {gap.research_question}\n\n"
            f"Potential Research Gaps:\n- "
            + "\n- ".join(gap.potential_research_gaps)
            + "\n\nMissing Evidence:\n- "
            + ("\n- ".join(gap.missing_evidence) if gap.missing_evidence else "(none)")
            + "\n\nEstablished Findings:\n"
            + _findings(gap.established_findings)
            + "\n\nConflicting Findings:\n"
            + _findings(gap.conflicting_findings)
            + "\n\nLimitations:\n"
            + _findings(gap.limitations)
            + "\n\nRespond with ONLY this JSON schema:\n"
            "{\n"
            '  "hypothesis": "clear, testable hypothesis",\n'
            '  "research_objective": "primary objective",\n'
            '  "variables": {\n'
            '    "independent": ["..."],\n'
            '    "dependent": ["..."],\n'
            '    "controls": ["..."]\n'
            "  },\n"
            '  "baseline": "explicit baseline comparison method or model",\n'
            '  "proposed_method": "concise experimental method",\n'
            '  "dataset_requirements": ["dataset or data needs"],\n'
            '  "evaluation_metrics": ["measurable metric 1", "measurable metric 2"],\n'
            '  "expected_outcome": "what success looks like",\n'
            '  "risks": ["key risk"]\n'
            "}\n\n"
            "Rules:\n"
            "- hypothesis must be falsifiable.\n"
            "- baseline is REQUIRED and must name a concrete comparison.\n"
            "- evaluation_metrics must be measurable (e.g. accuracy, F1, AUROC, latency).\n"
            "- Keep the plan domain-agnostic to the provided gap.\n"
            "- Do not invent unrelated research topics.\n"
        )

    def _build_response(
        self, research_question: str, data: dict[str, Any]
    ) -> ExperimentPlanResponse:
        try:
            variables_raw = data.get("variables") or {}
            if not isinstance(variables_raw, dict):
                raise ValueError("variables must be an object")

            variables = ExperimentVariables(
                independent=[
                    str(v).strip()
                    for v in (variables_raw.get("independent") or [])
                    if str(v).strip()
                ],
                dependent=[
                    str(v).strip()
                    for v in (variables_raw.get("dependent") or [])
                    if str(v).strip()
                ],
                controls=[
                    str(v).strip()
                    for v in (variables_raw.get("controls") or [])
                    if str(v).strip()
                ],
            )

            metrics = [
                str(m).strip()
                for m in (data.get("evaluation_metrics") or [])
                if str(m).strip()
            ]
            baseline = str(data.get("baseline") or "").strip()
            if not baseline:
                raise ValueError("baseline comparison is required")
            if not metrics:
                raise ValueError("at least one measurable evaluation metric is required")

            response = ExperimentPlanResponse(
                research_question=research_question,
                hypothesis=str(data.get("hypothesis") or "").strip(),
                research_objective=str(data.get("research_objective") or "").strip(),
                variables=variables,
                baseline=baseline,
                proposed_method=str(data.get("proposed_method") or "").strip(),
                dataset_requirements=[
                    str(d).strip()
                    for d in (data.get("dataset_requirements") or [])
                    if str(d).strip()
                ],
                evaluation_metrics=metrics,
                expected_outcome=str(data.get("expected_outcome") or "").strip(),
                risks=[
                    str(r).strip() for r in (data.get("risks") or []) if str(r).strip()
                ],
                model=self._nebius.model,
            )
        except (ValidationError, ValueError, TypeError) as exc:
            logger.error("Invalid experiment plan payload: %s", data)
            raise ExperimentPlanError(
                f"Nemotron returned an incomplete experiment plan: {exc}",
                status_code=502,
            ) from exc

        return response
