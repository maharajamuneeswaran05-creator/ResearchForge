"""Research report generator: research artefacts -> structured final report.

Workflow:
Research Question + Evidence + Research Gap + Hypothesis + Experiment Plan +
Experiment Results + Research Critique -> Nemotron -> structured report.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from app.schemas.research import (
    ConfidenceAssessment,
    EvidenceItem,
    ResearchReportRequest,
    ResearchReportResponse,
    ResearchReportSection,
)
from app.services.nebius import NebiusClient, NebiusError
from app.services.research_formatting import (
    format_critique,
    format_design,
    format_evidence,
    format_gap,
    format_results,
)
from app.services.research_gap import ResearchGapError, ResearchGapService

logger = logging.getLogger(__name__)

# Canonical report sections, in rendering order.
REPORT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("abstract", "Abstract"),
    ("research_question", "Research Question"),
    ("background", "Background"),
    ("evidence", "Evidence"),
    ("research_gap", "Research Gap"),
    ("hypothesis", "Hypothesis"),
    ("methodology", "Methodology"),
    ("experiment", "Experiment"),
    ("results", "Results"),
    ("critical_evaluation", "Critical Evaluation"),
    ("limitations", "Limitations"),
    ("future_work", "Future Work"),
    ("conclusion", "Conclusion"),
)

# Numeric literals in the results narrative must be traceable to the artefacts.
_NUMERIC = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")


def render_report_markdown(
    *,
    title: str,
    research_question: str,
    sections: list[ResearchReportSection],
    sources: list[EvidenceItem],
    confidence: ConfidenceAssessment,
    generated_at: str,
    model: str,
) -> str:
    """Render the structured report into clean, publishable Markdown format."""
    lines: list[str] = [
        f"# {title}",
        "",
        f"**Research Question:** {research_question}  ",
        f"**Generated:** {generated_at}  ",
        f"**Model:** {model}  ",
        f"**Confidence Level:** {confidence.confidence_level.upper()} (score: {confidence.reliability_score:.2f})  ",
        f"**Reasoning:** {confidence.reasoning}",
        "",
        "---",
        "",
    ]
    for section in sections:
        lines.append(f"## {section.title}")
        lines.append("")
        if section.content:
            lines.append(section.content)
            lines.append("")
        if section.evidence_refs:
            lines.append("**Evidence References:**")
            for ref in section.evidence_refs:
                lines.append(f"- <{ref}>")
            lines.append("")
    if sources:
        lines.append("## Retrieved Sources")
        lines.append("")
        for idx, src in enumerate(sources, start=1):
            lines.append(f"{idx}. [{src.title}]({src.url}) - *{src.source}*")
            if src.snippet:
                lines.append(f"   > {src.snippet}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


class ResearchReportError(Exception):
    """Raised when the research report generation fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ResearchReportService:
    """Generate the final structured research report with Nemotron."""


    def __init__(self, nebius_client: NebiusClient) -> None:
        self._nebius = nebius_client

    async def generate(self, request: ResearchReportRequest) -> ResearchReportResponse:
        """Run the report workflow and return the structured report."""
        system_message = (
            "You are a research writer producing the final report of an autonomous "
            "research pipeline. You report only what the supplied artefacts contain "
            "and you never fabricate results, citations or numbers.\n"
            "You must return ONLY a valid JSON object matching the requested schema. "
            "Do not include markdown codeblocks, preambles, or explanations outside "
            "the JSON."
        )
        user_message = self._build_prompt(request)

        try:
            payload = await self._nebius.chat_completion(
                user_message=user_message,
                system_message=system_message,
                max_tokens=4000,
                temperature=0.2,
            )
            raw_text = self._nebius.extract_assistant_text(payload)
        except NebiusError as exc:
            raise ResearchReportError(
                f"Nemotron report generation failed: {exc}",
                status_code=exc.status_code,
            ) from exc

        try:
            data = ResearchGapService._extract_json(raw_text)
        except ResearchGapError as exc:
            raise ResearchReportError(
                f"Failed to parse report JSON: {exc}",
                status_code=exc.status_code or 502,
            ) from exc

        return self._build_response(request, data)

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    @classmethod
    def _build_prompt(cls, request: ResearchReportRequest) -> str:
        sections: list[str] = [
            f"Research Question: {request.research_question}",
            f"Hypothesis: {cls._hypothesis(request)}",
            "Retrieved Evidence:\n" + format_evidence(request.evidence),
        ]

        if request.research_gap is not None:
            sections.append("Research Gap:\n" + format_gap(request.research_gap))
        if request.experiment_plan is not None:
            sections.append(
                "Experiment Plan:\n" + format_design(request.experiment_plan)
            )
        if request.experiment_results is not None:
            sections.append(
                "Experiment Results:\n" + format_results(request.experiment_results)
            )
        if request.research_critique is not None:
            sections.append(
                "Research Critique:\n" + format_critique(request.research_critique)
            )
        if request.additional_context:
            sections.append(
                "Additional Context:\n" + request.additional_context.strip()
            )

        keys = ", ".join(key for key, _ in REPORT_SECTIONS)
        titles = ", ".join(title for _, title in REPORT_SECTIONS)
        return (
            "\n\n".join(sections)
            + "\n\nRespond with ONLY this JSON schema:\n"
            "{\n"
            '  "title": "report title",\n'
            '  "sections": {\n'
            '    "abstract": {"content": "2-4 sentence summary", '
            '"evidence_refs": ["<url from the evidence list>"], '
            '"confidence": {"confidence_level": "medium", "reliability_score": 0.6, '
            '"reasoning": "why this confidence level"}},\n'
            '    "research_question": {"content": "..."},\n'
            '    "background": {"content": "..."},\n'
            '    "evidence": {"content": "..."},\n'
            '    "research_gap": {"content": "..."},\n'
            '    "hypothesis": {"content": "..."},\n'
            '    "methodology": {"content": "..."},\n'
            '    "experiment": {"content": "..."},\n'
            '    "results": {"content": "..."},\n'
            '    "critical_evaluation": {"content": "..."},\n'
            '    "limitations": {"content": "..."},\n'
            '    "future_work": {"content": "..."},\n'
            '    "conclusion": {"content": "..."}\n'
            "  },\n"
            '  "confidence_assessment": {"confidence_level": "medium", '
            '"reliability_score": 0.6, "reasoning": "overall confidence in the '
            'findings"}\n'
            "}\n\n"
            f"Rules:\n"
            f"- Provide exactly these sections, in this order: {titles}.\n"
            f"- The section keys are: {keys}.\n"
            "- NEVER invent experimental results. Only report numbers, metrics and "
            "outcomes that appear in the supplied Experiment Results. If no results "
            "were supplied, state that the experiment was not executed.\n"
            "- Do not invent citations or URLs. evidence_refs may only contain URLs "
            "from the supplied evidence list; use [] when no source supports a claim.\n"
            "- Clearly separate evidence from interpretation: quote or cite the "
            "source for evidence-based statements and label your own analysis as "
            "interpretation.\n"
            "- Carry the critique's weaknesses, threats to validity and follow-up "
            "recommendations into Critical Evaluation, Limitations and Future Work; "
            "do not soften them.\n"
            "- Do not claim the hypothesis is supported unless the supplied results "
            "and critique justify it; otherwise state that it remains unconfirmed.\n"
            "- confidence_level must be 'high', 'medium' or 'low'; reliability_score "
            "must be a float between 0.0 and 1.0.\n"
            "- Each section may carry a confidence object; omit it when a single "
            "confidence for the whole report is enough.\n"
        )

    @staticmethod
    def _hypothesis(request: ResearchReportRequest) -> str:
        if request.hypothesis.strip():
            return request.hypothesis.strip()
        if request.experiment_plan is not None:
            return request.experiment_plan.hypothesis
        return "(not specified)"

    # ------------------------------------------------------------------
    # Response construction
    # ------------------------------------------------------------------

    def _build_response(
        self, request: ResearchReportRequest, data: dict[str, Any]
    ) -> ResearchReportResponse:
        raw_sections = self._raw_sections(data.get("sections"))
        known_urls = {item.url for item in request.evidence}

        sections: list[ResearchReportSection] = []
        for key, title in REPORT_SECTIONS:
            raw = raw_sections.get(key) or {}
            content = str(raw.get("content") or "").strip()
            refs = [
                str(ref).strip()
                for ref in (raw.get("evidence_refs") or [])
                if str(ref).strip() in known_urls
            ]
            sections.append(
                ResearchReportSection(
                    key=key,
                    title=title,
                    content=content,
                    evidence_refs=refs,
                    confidence=self._confidence(raw.get("confidence")),
                )
            )

        if not any(section.content for section in sections):
            raise ResearchReportError(
                "Nemotron returned a report without any section content.",
                status_code=502,
            )

        self._append_sources(sections, request.evidence)
        self._ground_results(sections, request)

        report_title = str(data.get("title") or "").strip() or request.research_question
        generated_at = datetime.now().astimezone().isoformat()
        confidence = self._report_confidence(request, data)
        markdown = render_report_markdown(
            title=report_title,
            research_question=request.research_question,
            sections=sections,
            sources=list(request.evidence),
            confidence=confidence,
            generated_at=generated_at,
            model=self._nebius.model,
        )

        return ResearchReportResponse(
            research_question=request.research_question,
            title=report_title,
            sections=sections,
            sources=list(request.evidence),
            confidence_assessment=confidence,
            generated_at=generated_at,
            model=self._nebius.model,
            markdown=markdown,
        )


    @staticmethod
    def _raw_sections(raw: Any) -> dict[str, dict[str, Any]]:
        """Normalise the model output into a {key: {...}} mapping."""
        sections: dict[str, dict[str, Any]] = {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, dict):
                    sections[str(key).strip()] = value
                elif isinstance(value, str):
                    sections[str(key).strip()] = {"content": value}
        elif isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                key = str(entry.get("key") or entry.get("title") or "").strip()
                if key:
                    sections[key] = entry
        return sections

    @staticmethod
    def _append_sources(
        sections: list[ResearchReportSection], evidence: list[EvidenceItem]
    ) -> None:
        """Append the retrieved sources verbatim to the Evidence section."""
        for section in sections:
            if section.key != "evidence":
                continue
            if not evidence:
                section.content = (
                    (section.content + "\n\n" if section.content else "")
                    + "No external evidence was retrieved for this question."
                )
                return
            lines = ["---", "Sources (retrieved evidence, unmodified):"]
            for index, item in enumerate(evidence, start=1):
                lines.append(f"[{index}] {item.title} - {item.source}")
                lines.append(f"    URL: {item.url}")
                if item.snippet:
                    lines.append(f"    Snippet: {item.snippet}")
            prefix = section.content + "\n\n" if section.content else ""
            section.content = prefix + "\n".join(lines)
            section.evidence_refs = list(
                dict.fromkeys(section.evidence_refs + [item.url for item in evidence])
            )

    @staticmethod
    def _ground_results(
        sections: list[ResearchReportSection], request: ResearchReportRequest
    ) -> None:
        """Guard the Results section against invented numbers."""
        results = request.experiment_results
        for section in sections:
            if section.key != "results":
                continue
            if results is None:
                section.content = (
                    "No experiment was executed, so no experimental results are "
                    "available. Nothing in this section is based on a measurement."
                )
                return

            corpus = ResearchReportService._results_corpus(request)
            unsupported = sorted(
                {
                    token
                    for token in _NUMERIC.findall(section.content)
                    if token not in corpus
                }
            )
            if unsupported:
                section.content += (
                    "\n\nGrounding check: the value(s) "
                    + ", ".join(unsupported)
                    + " do not appear in the supplied experiment output and could "
                    "not be verified."
                )

    @staticmethod
    def _confidence(raw: Any) -> ConfidenceAssessment | None:
        if not isinstance(raw, dict):
            return None
        level = str(raw.get("confidence_level") or "medium").strip().lower()
        if level not in ("high", "medium", "low"):
            level = "medium"
        try:
            score = float(raw.get("reliability_score", 0.5))
        except (TypeError, ValueError):
            score = 0.5
        score = max(0.0, min(1.0, score))
        reasoning = str(raw.get("reasoning") or "").strip()
        return ConfidenceAssessment(
            confidence_level=level,
            reliability_score=score,
            reasoning=reasoning,
        )

    def _report_confidence(
        self, request: ResearchReportRequest, data: dict[str, Any]
    ) -> ConfidenceAssessment:
        confidence = self._confidence(data.get("confidence_assessment"))
        if confidence is not None:
            return confidence
        if request.research_gap is not None and request.research_gap.confidence_assessment:
            return request.research_gap.confidence_assessment
        return ConfidenceAssessment(
            confidence_level="low",
            reliability_score=0.5,
            reasoning="No explicit confidence assessment was produced for this report.",
        )


    @staticmethod
    def _results_corpus(request: ResearchReportRequest) -> str:
        """Build the text that numeric claims in the Results section must come from."""
        parts: list[str] = []
        results = request.experiment_results
        if results is not None:
            parts.append(results.stdout or "")
            parts.append(results.stderr or "")
            parts.append(str(results.exit_code))
            parts.append(f"{results.execution_time_seconds:.3f}")
            for key, value in results.metrics.items():
                parts.append(f"{key} = {value}")
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                parts.append(f"{numeric:g}")
                parts.append(f"{numeric * 100:g}")
                parts.append(f"{numeric * 100:.2f}")
        if request.experiment_plan is not None:
            parts.append(" ".join(request.experiment_plan.evaluation_metrics))
            parts.append(" ".join(request.experiment_plan.dataset_requirements))
        if request.research_critique is not None:
            parts.append(request.research_critique.verdict)
            parts.append(" ".join(request.research_critique.recommended_followup))
            for item in (
                request.research_critique.strengths
                + request.research_critique.weaknesses
                + request.research_critique.threats_to_validity
            ):
                parts.append(item.finding)
        return " ".join(parts)
