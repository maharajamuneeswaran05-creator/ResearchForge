"""Research Gap Finder service.

Workflow:
Research Question -> Tavily Evidence -> Nemotron Analysis -> Structured Research Gap.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.schemas.research import (
    ConfidenceAssessment,
    EvidenceItem,
    FindingWithEvidence,
    ResearchGapResponse,
)
from app.services.nebius import NebiusClient, NebiusError
from app.services.tavily import TavilyClient, TavilyError

logger = logging.getLogger(__name__)


class ResearchGapError(Exception):
    """Raised when research gap analysis fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ResearchGapService:
    """Coordinates evidence retrieval and Nemotron analysis to identify research gaps."""

    def __init__(
        self,
        nebius_client: NebiusClient,
        tavily_client: TavilyClient,
    ) -> None:
        self._nebius = nebius_client
        self._tavily = tavily_client

    async def analyze(
        self,
        question: str,
        *,
        max_results: int | None = None,
        evidence: list[EvidenceItem] | None = None,
    ) -> ResearchGapResponse:
        """Run workflow: fetch evidence (if not provided) -> prompt Nemotron -> return structured gap."""
        # 1. Collect evidence if not supplied
        if evidence is None:
            try:
                raw_items = await self._tavily.search(question, max_results=max_results)
                evidence = [EvidenceItem(**item) for item in raw_items]
            except TavilyError as exc:
                raise ResearchGapError(
                    f"Evidence collection failed: {exc}",
                    status_code=exc.status_code,
                ) from exc

        if not evidence:
            raise ResearchGapError(
                "No evidence found to analyze for this research question.",
                status_code=404,
            )

        # 2. Format concise evidence context and prompts
        evidence_context = self._format_evidence(evidence)
        system_message = (
            "You are an academic research analyst. Analyze the provided literature evidence "
            "for the given research question to identify consensus, contradictions, limitations, "
            "missing evidence, and potential research gaps.\n"
            "You must return ONLY a valid JSON object matching the requested schema. "
            "Do not include markdown codeblocks, preambles, or explanations outside the JSON."
        )
        user_message = (
            f"Research Question: {question}\n\n"
            f"Collected Evidence:\n{evidence_context}\n\n"
            "Analyze the above evidence and respond with ONLY a JSON object formatted as follows:\n"
            "{\n"
            '  "established_findings": [\n'
            '    {"claim": "concise established finding", "evidence_refs": ["source or title"]}\n'
            "  ],\n"
            '  "conflicting_findings": [\n'
            '    {"claim": "contradictory or debated point", "evidence_refs": ["source or title"]}\n'
            "  ],\n"
            '  "limitations": [\n'
            '    {"claim": "methodological or scope limitation", "evidence_refs": ["source or title"]}\n'
            "  ],\n"
            '  "missing_evidence": [\n'
            '    "unaddressed aspect or missing empirical evaluation"\n'
            "  ],\n"
            '  "potential_research_gaps": [\n'
            '    "concrete high-value gap or future direction"\n'
            "  ],\n"
            '  "confidence_assessment": {\n'
            '    "confidence_level": "high",\n'
            '    "reliability_score": 0.85,\n'
            '    "reasoning": "brief justification based on evidence coverage and consensus"\n'
            "  }\n"
            "}\n\n"
            "Rules:\n"
            "- Every claim in established_findings, conflicting_findings, and limitations MUST include at least one reference in evidence_refs from the evidence list.\n"
            "- If there are no conflicting findings, return an empty list [].\n"
            "- confidence_level must be 'high', 'medium', or 'low'.\n"
            "- reliability_score must be a float between 0.0 and 1.0.\n"
            "- Do not invent citations outside the provided evidence."
        )

        # 3. Request analysis from Nemotron
        try:
            payload = await self._nebius.chat_completion(
                user_message=user_message,
                system_message=system_message,
                max_tokens=1500,
                temperature=0.1,
            )
            raw_text = self._nebius.extract_assistant_text(payload)
        except NebiusError as exc:
            raise ResearchGapError(
                f"Nemotron analysis failed: {exc}",
                status_code=exc.status_code,
            ) from exc

        # 4. Extract and validate JSON response
        data = self._extract_json(raw_text)
        return self._build_response(question, evidence, data)

    @staticmethod
    def _format_evidence(evidence: list[EvidenceItem]) -> str:
        lines: list[str] = []
        for i, item in enumerate(evidence, start=1):
            lines.append(
                f"[{i}] Title: {item.title}\n"
                f"    Source: {item.source} | URL: {item.url}\n"
                f"    Snippet: {item.snippet}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        # Remove markdown codeblock wrapper if present
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if match:
                cleaned = match.group(1).strip()

        # Extract bracketed JSON object if surrounded by extra text
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
            raise ValueError(f"Parsed JSON is not an object: {type(parsed)}")
        except Exception as exc:
            logger.error("Failed to parse JSON from Nemotron output: %s", text[:500])
            raise ResearchGapError(
                f"Nemotron returned invalid JSON structure: {exc}",
                status_code=502,
            ) from exc

    @staticmethod
    def _build_response(
        question: str,
        evidence: list[EvidenceItem],
        data: dict[str, Any],
    ) -> ResearchGapResponse:
        confidence = data.get("confidence_assessment") or {}
        if not isinstance(confidence, dict):
            confidence = {}

        raw_score = confidence.get("reliability_score")
        try:
            score = float(raw_score) if raw_score is not None else 0.75
            score = max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            score = 0.75

        level = str(confidence.get("confidence_level") or "medium").lower()
        if level not in ("high", "medium", "low"):
            level = "medium"

        reasoning = str(
            confidence.get("reasoning")
            or "Evaluated based on consistency and coverage of retrieved evidence."
        ).strip()

        return ResearchGapResponse(
            research_question=question,
            established_findings=[
                FindingWithEvidence.from_raw(f)
                for f in (data.get("established_findings") or [])
            ],
            conflicting_findings=[
                FindingWithEvidence.from_raw(f)
                for f in (data.get("conflicting_findings") or [])
            ],
            limitations=[
                FindingWithEvidence.from_raw(f)
                for f in (data.get("limitations") or [])
            ],
            missing_evidence=[
                str(item).strip()
                for item in (data.get("missing_evidence") or [])
                if str(item).strip()
            ],
            potential_research_gaps=[
                str(item).strip()
                for item in (data.get("potential_research_gaps") or [])
                if str(item).strip()
            ],
            confidence_assessment=ConfidenceAssessment(
                confidence_level=level,
                reliability_score=score,
                reasoning=reasoning,
            ),
            evidence_count=len(evidence),
            evidence=evidence,
        )
