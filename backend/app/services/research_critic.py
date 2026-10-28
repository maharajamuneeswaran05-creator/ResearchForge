"""Research critic service: skeptical peer review of an experiment and its results.

Workflow:
Research Question + Research Gap + Hypothesis + Experiment Design + Experiment
Results -> Nemotron critique -> structured skeptical assessment.
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.research import (
    CriticItem,
    ResearchCriticRequest,
    ResearchCriticResponse,
)
from app.services.nebius import NebiusClient, NebiusError
from app.services.research_formatting import format_design, format_gap, format_results
from app.services.research_gap import ResearchGapError, ResearchGapService

logger = logging.getLogger(__name__)

# Evaluation dimensions the critic is required to cover.
CRITIC_CATEGORIES = (
    "methodology",
    "baseline_quality",
    "evidence_quality",
    "statistical_reasoning",
    "bias",
    "confounding_factors",
    "reproducibility",
    "hypothesis_support",
    "alternative_explanations",
    "limitations",
)


class ResearchCriticError(Exception):
    """Raised when the research critique fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ResearchCriticService:
    """Critically evaluate research with Nemotron acting as a skeptical reviewer."""

    def __init__(self, nebius_client: NebiusClient) -> None:
        self._nebius = nebius_client

    async def critique(self, request: ResearchCriticRequest) -> ResearchCriticResponse:
        """Run the critique workflow and return the structured assessment."""
        system_message = (
            "You are a skeptical peer reviewer for an autonomous research system. "
            "Your job is to try to DISPROVE the conclusion, not to agree with it. "
            "Assume the reported results are flawed until the artefacts show otherwise. "
            "Look for methodology gaps, weak baselines, insufficient evidence, "
            "statistical and reasoning weaknesses, bias, confounding factors, "
            "reproducibility problems, alternative explanations, and limitations.\n"
            "You must return ONLY a valid JSON object matching the requested schema. "
            "Do not include markdown codeblocks, preambles, or explanations outside "
            "the JSON."
        )
        user_message = self._build_prompt(request)

        try:
            payload = await self._nebius.chat_completion(
                user_message=user_message,
                system_message=system_message,
                max_tokens=2000,
                temperature=0.2,
            )
            raw_text = self._nebius.extract_assistant_text(payload)
        except NebiusError as exc:
            raise ResearchCriticError(
                f"Nemotron critique failed: {exc}",
                status_code=exc.status_code,
            ) from exc

        try:
            data = ResearchGapService._extract_json(raw_text)
        except ResearchGapError as exc:
            raise ResearchCriticError(
                f"Failed to parse critique JSON: {exc}",
                status_code=exc.status_code or 502,
            ) from exc

        return self._build_response(request, data)

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    @classmethod
    def _build_prompt(cls, request: ResearchCriticRequest) -> str:
        sections: list[str] = [
            f"Research Question: {request.research_question}",
            f"Hypothesis: {request.hypothesis}",
        ]

        if request.research_gap is not None:
            sections.append("Research Gap:\n" + format_gap(request.research_gap))
        if request.experiment_design is not None:
            sections.append(
                "Experiment Design:\n" + format_design(request.experiment_design)
            )
        if request.experiment_results is not None:
            sections.append(
                "Experiment Results:\n" + format_results(request.experiment_results)
            )
        if request.additional_context:
            sections.append(
                "Additional Context:\n" + request.additional_context.strip()
            )

        categories = ", ".join(CRITIC_CATEGORIES)
        return (
            "\n\n".join(sections)
            + "\n\nRespond with ONLY this JSON schema:\n"
            "{\n"
            '  "verdict": "one-paragraph overall assessment, stating explicitly whether '
            'the results support the hypothesis",\n'
            '  "hypothesis_supported": true,\n'
            '  "strengths": [\n'
            '    {"category": "methodology", "finding": "what the experiment does well", '
            '"severity": "low"}\n'
            "  ],\n"
            '  "weaknesses": [\n'
            '    {"category": "statistical_reasoning", "finding": "specific methodological '
            'or reasoning weakness", "severity": "high"}\n'
            "  ],\n"
            '  "threats_to_validity": [\n'
            '    {"category": "confounding_factors", "finding": "confounder, bias or '
            'alternative explanation that could produce the same result", '
            '"severity": "high"}\n'
            "  ],\n"
            '  "recommended_followup": ["concrete next experiment or analysis"],\n'
            '  "confidence_score": 0.6\n'
            "}\n\n"
            f"Rules:\n"
            f"- Use only these categories: {categories}.\n"
            "- Cover every category that the supplied artefacts allow; call out "
            "unevaluable dimensions explicitly (for example 'hypothesis_support' when "
            "no results were supplied).\n"
            "- Be specific and reference concrete numbers from the results (metrics, "
            "exit codes, sample sizes) instead of generic statements.\n"
            "- Assume a single run with no error bars or significance tests is weak "
            "evidence; say so.\n"
            "- Always look for alternative explanations and confounds before "
            "concluding that the hypothesis is supported.\n"
            "- hypothesis_supported must be true, false, or null when there is not "
            "enough evidence to decide.\n"
            "- confidence_score must be a float between 0.0 and 1.0 expressing "
            "confidence in your critique.\n"
            "- If no results are supplied, critique the design and set "
            "hypothesis_supported to null.\n"
            "- Return empty lists [] for a section that truly has no findings.\n"
        )

    # ------------------------------------------------------------------
    # Response construction
    # ------------------------------------------------------------------

    def _build_response(
        self, request: ResearchCriticRequest, data: dict[str, Any]
    ) -> ResearchCriticResponse:
        verdict = str(data.get("verdict") or "").strip()
        if not verdict:
            raise ResearchCriticError(
                "Nemotron returned a critique without a verdict.",
                status_code=502,
            )

        strengths = self._items(data.get("strengths"))
        weaknesses = self._items(data.get("weaknesses"))
        threats = self._items(data.get("threats_to_validity"))
        if not (strengths or weaknesses or threats):
            raise ResearchCriticError(
                "Nemotron returned a critique without any findings.",
                status_code=502,
            )

        followup = [
            str(item).strip()
            for item in (data.get("recommended_followup") or [])
            if str(item).strip()
        ]

        return ResearchCriticResponse(
            research_question=request.research_question,
            verdict=verdict,
            hypothesis_supported=self._hypothesis_supported(data.get("hypothesis_supported")),
            strengths=strengths,
            weaknesses=weaknesses,
            threats_to_validity=threats,
            recommended_followup=followup,
            confidence_score=self._confidence_score(data.get("confidence_score")),
            model=self._nebius.model,
        )

    @staticmethod
    def _items(raw: Any) -> list[CriticItem]:
        if not isinstance(raw, list):
            return []
        return [
            item
            for item in (CriticItem.from_raw(entry) for entry in raw)
            if item.finding
        ]

    @staticmethod
    def _hypothesis_supported(raw: Any) -> bool | None:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            text = raw.strip().lower()
            if text in ("true", "yes", "supported", "supports", "1"):
                return True
            if text in ("false", "no", "not_supported", "unsupported", "0"):
                return False
        return None

    @staticmethod
    def _confidence_score(raw: Any) -> float:
        try:
            score = float(raw)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, score))
