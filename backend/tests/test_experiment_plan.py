"""Tests for the Experiment Planning service."""

from __future__ import annotations

import asyncio
import json
import pytest
import httpx

from _fake_nebius import FakeNebiusChatClient
from app.main import app
from app.schemas.research import (
    ConfidenceAssessment,
    FindingWithEvidence,
    StructuredResearchGap,
)
from app.services.experiment_plan import ExperimentPlanError, ExperimentPlanService

CANNED_PLAN_JSON = {
    "hypothesis": (
        "Conditioning consistency sampling on causal explanation graphs reduces "
        "factual hallucination rates by >= 25% compared to vanilla greedy decoding."
    ),
    "research_objective": (
        "Quantify hallucination rate reduction across 3 QA benchmarks under "
        "causal graph-conditioned consistency."
    ),
    "variables": {
        "independent": ["Decoding method: causal graph consistency vs vanilla greedy"],
        "dependent": ["Hallucination rate (%)", "Factuality accuracy", "Token latency"],
        "controls": ["Model size (70B)", "Sampling temperature (0.7)", "Prompt format"],
    },
    "baseline": "Vanilla greedy autoregressive decoding with standard chain-of-thought prompting.",
    "proposed_method": "Generate multi-sample candidate paths, extract causal DAG, score consistency.",
    "dataset_requirements": ["TruthfulQA", "HaluEval benchmark"],
    "evaluation_metrics": ["hallucination_rate", "accuracy", "latency_ms"],
    "expected_outcome": "Statistically significant hallucination drop with <15% compute overhead.",
    "risks": ["Graph extraction overhead during inference"],
}

SAMPLE_GAP = StructuredResearchGap(
    research_question="Can explanation consistency improve hallucination detection?",
    potential_research_gaps=["Measuring hallucination reduction under causal graph conditioning."],
    missing_evidence=["Ablation under strict fact-checking."],
    established_findings=[
        FindingWithEvidence(claim="Self-consistency helps.", evidence_refs=["http://example.com"])
    ],
    conflicting_findings=[],
    limitations=[],
    confidence_assessment=ConfidenceAssessment(
        confidence_level="high", reliability_score=0.9, reasoning="Good agreement"
    ),
)


def test_experiment_plan_parses_json():
    fake_client = FakeNebiusChatClient(json.dumps(CANNED_PLAN_JSON))
    service = ExperimentPlanService(nebius_client=fake_client)

    plan = asyncio.run(service.plan(SAMPLE_GAP))
    assert plan.research_question == SAMPLE_GAP.research_question
    assert "Conditioning consistency" in plan.hypothesis
    assert plan.baseline.startswith("Vanilla greedy")
    assert "hallucination_rate" in plan.evaluation_metrics
    assert len(plan.variables.independent) == 1
    assert len(plan.variables.dependent) == 3


def test_missing_baseline_raises_error():
    broken = dict(CANNED_PLAN_JSON)
    broken["baseline"] = ""
    fake_client = FakeNebiusChatClient(json.dumps(broken))
    service = ExperimentPlanService(nebius_client=fake_client)

    with pytest.raises(ExperimentPlanError) as exc_info:
        asyncio.run(service.plan(SAMPLE_GAP))
    assert "baseline" in str(exc_info.value).lower()


def test_missing_hypothesis_raises_error():
    broken = dict(CANNED_PLAN_JSON)
    broken["hypothesis"] = ""
    fake_client = FakeNebiusChatClient(json.dumps(broken))
    service = ExperimentPlanService(nebius_client=fake_client)

    with pytest.raises(ExperimentPlanError) as exc_info:
        asyncio.run(service.plan(SAMPLE_GAP))
    assert "hypothesis" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_endpoint_returns_experiment_plan():
    fake_client = FakeNebiusChatClient(json.dumps(CANNED_PLAN_JSON))
    service = ExperimentPlanService(nebius_client=fake_client)

    async with app.router.lifespan_context(app):
        app.state.experiment_plan_service = service
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/research/experiment-plan",
                json={"research_gap": SAMPLE_GAP.model_dump()},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["baseline"].startswith("Vanilla greedy")
            assert "hallucination_rate" in data["evaluation_metrics"]
