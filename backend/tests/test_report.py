"""Tests for the research report generator (no live model calls needed)."""

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
    ConfidenceAssessment,
    CriticItem,
    EvidenceItem,
    ExperimentExecutionResult,
    ExperimentJobStatus,
    ExperimentPlanResponse,
    ExperimentVariables,
    ResearchCriticResponse,
    ResearchReportRequest,
    StructuredResearchGap,
)
from app.services.research_report import (  # noqa: E402
    REPORT_SECTIONS,
    ResearchReportError,
    ResearchReportService,
)

EVIDENCE = [
    EvidenceItem(
        title="Dropout regularization in neural networks",
        url="https://example.org/paper-dropout",
        source="Example Journal",
        snippet="Dropout reduces overfitting on small datasets.",
    ),
    EvidenceItem(
        title="Reproducibility checklist",
        url="https://example.org/checklist",
        source="Example Labs",
        snippet="Report seeds, variance and number of runs.",
    ),
]

REPORT_JSON = {
    "title": "Dropout improves sentiment accuracy?",
    "sections": {
        "abstract": {
            "content": "A single synthetic run shows a 0.05 accuracy gain.",
            "confidence": {
                "confidence_level": "low",
                "reliability_score": 0.4,
                "reasoning": "One run, no variance.",
            },
        },
        "research_question": {"content": "Does dropout improve LSTM accuracy?"},
        "background": {"content": "Dropout is a standard regularizer."},
        "evidence": {
            "content": "Prior work reports reduced overfitting.",
            "evidence_refs": ["https://example.org/paper-dropout", "https://not-real.test/x"],
        },
        "research_gap": {"content": "No ablation study exists."},
        "hypothesis": {"content": "Dropout improves accuracy versus no dropout."},
        "methodology": {"content": "Synthetic dataset, fixed seed, one comparison."},
        "experiment": {"content": "LSTM with and without dropout=0.3."},
        "results": {
            "content": "Baseline accuracy was 0.5 and the improved accuracy was 0.55."
        },
        "critical_evaluation": {"content": "The gain is not statistically supported."},
        "limitations": {"content": "No error bars, tiny dataset."},
        "future_work": {"content": "Repeat over 10 seeds."},
        "conclusion": {"content": "The hypothesis remains unconfirmed."},
    },
    "confidence_assessment": {
        "confidence_level": "low",
        "reliability_score": 0.45,
        "reasoning": "Synthetic data, single run.",
    },
}


def _request(with_results: bool = True) -> ResearchReportRequest:
    gap = StructuredResearchGap(
        research_question="Does dropout improve LSTM accuracy?",
        potential_research_gaps=["No ablation study of dropout on sentiment data"],
        missing_evidence=["Repeated runs with variance"],
        confidence_assessment=ConfidenceAssessment(
            confidence_level="medium", reliability_score=0.6, reasoning="gap coverage"
        ),
    )
    plan = ExperimentPlanResponse(
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
    results = None
    if with_results:
        results = ExperimentExecutionResult(
            job_id="job-1",
            status=ExperimentJobStatus.COMPLETED,
            exit_code=0,
            stdout="Baseline accuracy: 0.5000\nMETRIC baseline_accuracy=0.5",
            stderr="",
            metrics={"baseline_accuracy": 0.5, "improvement": 0.05},
            execution_time_seconds=1.25,
            research_question="Does dropout improve LSTM accuracy?",
        )
    critique = ResearchCriticResponse(
        research_question="Does dropout improve LSTM accuracy?",
        verdict="Single run, no variance, hypothesis not established.",
        hypothesis_supported=False,
        strengths=[
            CriticItem(category="methodology", finding="Baseline is named.", severity="low")
        ],
        weaknesses=[
            CriticItem(
                category="statistical_reasoning",
                finding="No variance estimate.",
                severity="high",
            )
        ],
        threats_to_validity=[
            CriticItem(
                category="confounding_factors",
                finding="Loss values are hard-coded.",
                severity="high",
            )
        ],
        recommended_followup=["Repeat over 10 seeds."],
        confidence_score=0.78,
        model="test-model",
    )
    return ResearchReportRequest(
        research_question="Does dropout improve LSTM accuracy?",
        evidence=EVIDENCE,
        research_gap=gap,
        experiment_plan=plan,
        experiment_results=results,
        research_critique=critique,
    )


def test_report_has_all_sections_in_order():
    client = FakeNebiusChatClient(json.dumps(REPORT_JSON))
    svc = ResearchReportService(client)
    report = asyncio.run(svc.generate(_request()))

    assert [s.key for s in report.sections] == [k for k, _ in REPORT_SECTIONS], report
    assert [s.title for s in report.sections] == [t for _, t in REPORT_SECTIONS], report
    assert report.title == "Dropout improves sentiment accuracy?", report
    assert report.confidence_assessment.reliability_score == 0.45, report
    assert report.model == client.model, report
    print("PASS test_report_has_all_sections_in_order")


def test_source_urls_are_preserved_and_refs_filtered():
    client = FakeNebiusChatClient(json.dumps(REPORT_JSON))
    svc = ResearchReportService(client)
    report = asyncio.run(svc.generate(_request()))

    assert report.sources == EVIDENCE, report.sources
    evidence_section = next(s for s in report.sections if s.key == "evidence")
    assert "https://example.org/paper-dropout" in evidence_section.content
    assert "https://example.org/checklist" in evidence_section.content
    assert "https://not-real.test/x" not in evidence_section.evidence_refs
    assert all(
        ref in {item.url for item in EVIDENCE} for ref in evidence_section.evidence_refs
    ), evidence_section.evidence_refs
    print("PASS test_source_urls_are_preserved_and_refs_filtered")


def test_invented_result_numbers_are_flagged():
    payload = json.loads(json.dumps(REPORT_JSON))
    payload["sections"]["results"]["content"] = (
        "Baseline accuracy was 0.5 and the improved accuracy was 0.93."
    )
    client = FakeNebiusChatClient(json.dumps(payload))
    svc = ResearchReportService(client)
    report = asyncio.run(svc.generate(_request()))

    results_section = next(s for s in report.sections if s.key == "results")
    assert "Grounding check" in results_section.content, results_section.content
    assert "0.93" in results_section.content, results_section.content
    print("PASS test_invented_result_numbers_are_flagged")


def test_results_section_without_experiment_is_neutral():
    client = FakeNebiusChatClient(json.dumps(REPORT_JSON))
    svc = ResearchReportService(client)
    report = asyncio.run(svc.generate(_request(with_results=False)))

    results_section = next(s for s in report.sections if s.key == "results")
    assert "No experiment was executed" in results_section.content, results_section.content
    print("PASS test_results_section_without_experiment_is_neutral")


def test_prompt_contains_all_artefacts():
    client = FakeNebiusChatClient(json.dumps(REPORT_JSON))
    svc = ResearchReportService(client)
    asyncio.run(svc.generate(_request()))

    prompt = client.prompts[0]["user_message"]
    for expected in (
        "https://example.org/paper-dropout",
        "Dropout improves accuracy versus no dropout.",
        "LSTM without dropout",
        "baseline_accuracy = 0.5",
        "Single run, no variance, hypothesis not established.",
        "NEVER invent experimental results",
    ):
        assert expected in prompt, f"missing from prompt: {expected}"
    print("PASS test_prompt_contains_all_artefacts")


def test_empty_report_is_rejected():
    client = FakeNebiusChatClient(json.dumps({"title": "x", "sections": {}}))
    svc = ResearchReportService(client)
    try:
        asyncio.run(svc.generate(_request()))
    except ResearchReportError as exc:
        assert exc.status_code == 502, exc
        print("PASS test_empty_report_is_rejected")
        return
    raise AssertionError("expected ResearchReportError")


def test_endpoint_returns_report():
    from app.main import app

    client = FakeNebiusChatClient(json.dumps(REPORT_JSON))
    service = ResearchReportService(client)

    async def run() -> None:
        async with app.router.lifespan_context(app):
            app.state.research_report_service = service
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as http:
                response = await http.post(
                    "/api/research/report",
                    json=_request().model_dump(mode="json"),
                )
                assert response.status_code == 200, response.text
                payload = response.json()
                assert len(payload["sections"]) == len(REPORT_SECTIONS), payload
                assert payload["sources"][0]["url"] == EVIDENCE[0].url, payload
                assert payload["confidence_assessment"]["reliability_score"] == 0.45

    asyncio.run(run())
    print("PASS test_endpoint_returns_report")


if __name__ == "__main__":
    test_report_has_all_sections_in_order()
    test_source_urls_are_preserved_and_refs_filtered()
    test_invented_result_numbers_are_flagged()
    test_results_section_without_experiment_is_neutral()
    test_prompt_contains_all_artefacts()
    test_empty_report_is_rejected()
    test_endpoint_returns_report()
    print("All tests passed.")
