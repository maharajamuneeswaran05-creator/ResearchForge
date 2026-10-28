"""Tests for the Research Critic service (no live model calls needed)."""

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
from _fake_nebius import FakeNebiusChatClient  # noqa: E402

from app.schemas.research import (  # noqa: E402
    ExperimentExecutionResult,
    ExperimentJobStatus,
    ExperimentPlanResponse,
    ExperimentVariables,
    ResearchCriticRequest,
    StructuredResearchGap,
)
from app.services.research_critic import (  # noqa: E402
    ResearchCriticError,
    ResearchCriticService,
)

CRITIQUE_JSON = {
    "verdict": (
        "The single synthetic run shows a 0.05 accuracy gain but provides no "
        "variance estimate, so the hypothesis is not established."
    ),
    "hypothesis_supported": False,
    "strengths": [
        {
            "category": "methodology",
            "finding": "The experiment compares against a named baseline.",
            "severity": "low",
        }
    ],
    "weaknesses": [
        {
            "category": "statistical_reasoning",
            "finding": "Only one run per condition, so no variance or significance.",
            "severity": "high",
        },
        {
            "category": "reproducibility",
            "finding": "Random seed is fixed but the dataset size is tiny (100 samples).",
            "severity": "medium",
        },
    ],
    "threats_to_validity": [
        {
            "category": "confounding_factors",
            "finding": "Loss values are hard-coded, so the gain is baked into the code.",
            "severity": "high",
        },
        {
            "category": "alternative_explanations",
            "finding": "Any method could 'improve' accuracy if the loss is hard-coded.",
            "severity": "high",
        },
    ],
    "recommended_followup": [
        "Repeat the comparison over 10 seeds and report mean and standard deviation.",
        "Replace the hard-coded loss with a real training loop.",
    ],
    "confidence_score": 0.78,
}


def _request() -> ResearchCriticRequest:
    gap = StructuredResearchGap(
        research_question="Does dropout improve LSTM accuracy?",
        potential_research_gaps=["No ablation study of dropout on sentiment data"],
        missing_evidence=["Repeated runs with variance"],
        established_findings=[],
        conflicting_findings=[],
        limitations=[],
    )
    design = ExperimentPlanResponse(
        research_question="Does dropout improve LSTM accuracy?",
        hypothesis="Dropout improves accuracy versus no dropout.",
        research_objective="Measure the accuracy delta.",
        variables=ExperimentVariables(
            independent=["dropout rate"],
            dependent=["accuracy"],
            controls=["random seed", "dataset size"],
        ),
        baseline="LSTM without dropout",
        proposed_method="LSTM with dropout=0.3",
        dataset_requirements=["synthetic sentiment dataset"],
        evaluation_metrics=["accuracy"],
        expected_outcome="Accuracy increases",
        risks=["synthetic data"],
        model="test-model",
    )
    results = ExperimentExecutionResult(
        job_id="job-1",
        status=ExperimentJobStatus.COMPLETED,
        exit_code=0,
        stdout="Baseline accuracy: 0.5000\nMETRIC baseline_accuracy=0.5\nMETRIC improvement=0.05",
        stderr="",
        metrics={"baseline_accuracy": 0.5, "improvement": 0.05},
        execution_time_seconds=1.25,
        research_question="Does dropout improve LSTM accuracy?",
    )
    return ResearchCriticRequest(
        research_question="Does dropout improve LSTM accuracy?",
        hypothesis="Dropout improves accuracy versus no dropout.",
        research_gap=gap,
        experiment_design=design,
        experiment_results=results,
    )


def test_critique_parses_structured_output():
    client = FakeNebiusChatClient(json.dumps(CRITIQUE_JSON))
    svc = ResearchCriticService(client)
    result = asyncio.run(svc.critique(_request()))

    assert "0.05" in result.verdict, result.verdict
    assert result.hypothesis_supported is False, result
    assert result.confidence_score == 0.78, result
    assert [i.category for i in result.weaknesses] == [
        "statistical_reasoning",
        "reproducibility",
    ], result.weaknesses
    assert {i.category for i in result.threats_to_validity} == {
        "confounding_factors",
        "alternative_explanations",
    }, result.threats_to_validity
    assert len(result.recommended_followup) == 2, result
    assert result.model == client.model, result
    print("PASS test_critique_parses_structured_output")


def test_prompt_contains_artifacts_and_skeptic_instructions():
    client = FakeNebiusChatClient(json.dumps(CRITIQUE_JSON))
    svc = ResearchCriticService(client)
    asyncio.run(svc.critique(_request()))

    prompt = client.prompts[0]["user_message"]
    system_prompt = client.prompts[0]["system_message"]
    for expected in (
        "Does dropout improve LSTM accuracy?",
        "Dropout improves accuracy versus no dropout.",
        "LSTM without dropout",
        "improvement = 0.05",
        "baseline_accuracy = 0.5",
        "alternative_explanations",
    ):
        assert expected in prompt, f"missing from prompt: {expected}"
    assert "DISPROVE" in system_prompt, system_prompt
    print("PASS test_prompt_contains_artifacts_and_skeptic_instructions")


def test_missing_verdict_is_rejected():
    client = FakeNebiusChatClient(json.dumps({"strengths": [], "weaknesses": []}))
    svc = ResearchCriticService(client)
    try:
        asyncio.run(svc.critique(_request()))
    except ResearchCriticError as exc:
        assert exc.status_code == 502, exc
        print("PASS test_missing_verdict_is_rejected")
        return
    raise AssertionError("expected ResearchCriticError")


def test_invalid_json_is_rejected():
    client = FakeNebiusChatClient("this is not json")
    svc = ResearchCriticService(client)
    try:
        asyncio.run(svc.critique(_request()))
    except ResearchCriticError as exc:
        assert exc.status_code == 502, exc
        print("PASS test_invalid_json_is_rejected")
        return
    raise AssertionError("expected ResearchCriticError")


def test_endpoint_returns_critique():
    from app.main import app

    client = FakeNebiusChatClient(json.dumps(CRITIQUE_JSON))
    service = ResearchCriticService(client)

    async def run() -> None:
        async with app.router.lifespan_context(app):
            app.state.research_critic_service = service
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as http:
                response = await http.post(
                    "/api/research/critic",
                    json=_request().model_dump(mode="json"),
                )
                assert response.status_code == 200, response.text
                payload = response.json()
                assert payload["hypothesis_supported"] is False, payload
                assert payload["weaknesses"], payload
                assert payload["model"] == client.model, payload

    asyncio.run(run())
    print("PASS test_endpoint_returns_critique")


if __name__ == "__main__":
    test_critique_parses_structured_output()
    test_prompt_contains_artifacts_and_skeptic_instructions()
    test_missing_verdict_is_rejected()
    test_invalid_json_is_rejected()
    test_endpoint_returns_critique()
    print("All tests passed.")
