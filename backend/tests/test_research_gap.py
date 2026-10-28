"""Tests for the Research Gap service."""

from __future__ import annotations

import asyncio
import json
import pytest
import httpx

from _fake_nebius import FakeNebiusChatClient
from app.main import app
from app.schemas.research import EvidenceItem
from app.services.research_gap import ResearchGapError, ResearchGapService

CANNED_GAP_JSON = {
    "established_findings": [
        {
            "claim": "Self-consistency verification improves reasoning accuracy across multiple benchmark tasks.",
            "evidence_refs": ["https://arxiv.org/html/2510.06265v1"],
        }
    ],
    "conflicting_findings": [
        {
            "claim": "Whether explanation consistency correlates with lower hallucination rate remains debated.",
            "evidence_refs": ["https://github.com/EdinburghNLP/awesome-hallucination-detection"],
        }
    ],
    "limitations": [
        {
            "claim": "Existing benchmarks measure only token overlap rather than semantic entailment.",
            "evidence_refs": ["https://arxiv.org/html/2510.06265v1"],
        }
    ],
    "missing_evidence": [
        "Ablation studies on sampling temperature under strict fact-checking protocols."
    ],
    "potential_research_gaps": [
        "Measuring hallucination reduction when conditioning consistency verification on causal graph explanations."
    ],
    "confidence_assessment": {
        "confidence_level": "high",
        "reliability_score": 0.88,
        "reasoning": "Strong peer-reviewed agreement on baseline benefits; clear gap in causal grounding.",
    },
}

SAMPLE_EVIDENCE = [
    EvidenceItem(
        title="Hallucination Survey",
        url="https://arxiv.org/html/2510.06265v1",
        source="arxiv.org",
        snippet="Self-consistency verification enhances LLM factuality.",
    ),
    EvidenceItem(
        title="Awesome Hallucination Detection",
        url="https://github.com/EdinburghNLP/awesome-hallucination-detection",
        source="github.com",
        snippet="Consistency metrics across generation samples.",
    ),
]


def test_research_gap_parses_json():
    fake_client = FakeNebiusChatClient(json.dumps(CANNED_GAP_JSON))
    service = ResearchGapService(nebius_client=fake_client, tavily_client=None)

    res = asyncio.run(
        service.analyze(
            question="Can explanation consistency improve hallucination detection?",
            evidence=SAMPLE_EVIDENCE,
        )
    )
    assert res.research_question == "Can explanation consistency improve hallucination detection?"
    assert len(res.established_findings) == 1
    assert res.established_findings[0].evidence_refs == ["https://arxiv.org/html/2510.06265v1"]
    assert res.confidence_assessment.confidence_level == "high"
    assert res.confidence_assessment.reliability_score == 0.88
    assert len(res.potential_research_gaps) == 1


def test_empty_evidence_raises_error():
    fake_client = FakeNebiusChatClient(json.dumps(CANNED_GAP_JSON))
    service = ResearchGapService(nebius_client=fake_client, tavily_client=None)

    with pytest.raises(ResearchGapError) as exc_info:
        asyncio.run(
            service.analyze(
                question="Can explanation consistency improve hallucination detection?",
                evidence=[],
            )
        )
    assert "No evidence found" in str(exc_info.value)


def test_invalid_json_rejected():
    fake_client = FakeNebiusChatClient("This is not JSON at all.")
    service = ResearchGapService(nebius_client=fake_client, tavily_client=None)

    with pytest.raises(ResearchGapError) as exc_info:
        asyncio.run(
            service.analyze(
                question="Can explanation consistency improve hallucination detection?",
                evidence=SAMPLE_EVIDENCE,
            )
        )
    assert "invalid JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_endpoint_returns_gap_analysis():
    fake_client = FakeNebiusChatClient(json.dumps(CANNED_GAP_JSON))
    service = ResearchGapService(nebius_client=fake_client, tavily_client=None)

    async with app.router.lifespan_context(app):
        app.state.research_gap_service = service
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/research/gap",
                json={
                    "research_question": "Can explanation consistency improve hallucination detection?",
                    "evidence": [e.model_dump() for e in SAMPLE_EVIDENCE],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["confidence_assessment"]["reliability_score"] == 0.88
            assert len(data["potential_research_gaps"]) == 1
