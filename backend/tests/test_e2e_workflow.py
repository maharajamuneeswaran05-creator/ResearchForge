"""Full 10-stage end-to-end research workflow integration test."""

from __future__ import annotations

import asyncio
import json
import pytest
import httpx

from _fake_nebius import FakeNebiusChatClient, FakeNebiusTransport
from app.config import Settings
from app.main import app
from app.schemas.research import (
    ConfidenceAssessment,
    EvidenceItem,
    ExperimentCodeResponse,
    ExperimentExecutionResult,
    ExperimentJobStatus,
    ExperimentPlanResponse,
    FindingWithEvidence,
    ResearchCriticResponse,
    ResearchGapResponse,
    ResearchReportResponse,
    ResearchReportSection,
    StructuredResearchGap,
)
from app.services.experiment_code import ExperimentCodeService
from app.services.experiment_execution import ExperimentExecutionService
from app.services.experiment_plan import ExperimentPlanService
from app.services.research_critic import ResearchCriticService
from app.services.research_gap import ResearchGapService
from app.services.research_report import ResearchReportService


@pytest.mark.asyncio
async def test_full_10_stage_research_pipeline():
    """Verify that every stage of the ResearchForge workflow produces valid artifacts and chains correctly."""
    question = "Can causal graph conditioning improve factuality consistency in LLM reasoning?"

    # Stage 1: Evidence items
    evidence = [
        EvidenceItem(
            title="Internal Consistency in LLM Generation",
            url="https://arxiv.org/abs/2301.0001",
            source="arxiv.org",
            snippet="Sampling multi-path reasoning improves accuracy on standard benchmarks.",
        ),
        EvidenceItem(
            title="Survey on Hallucination Mitigation",
            url="https://arxiv.org/abs/2302.0002",
            source="arxiv.org",
            snippet="Causal tracing reveals localized factual corruption in transformer layers.",
        ),
    ]

    # Stage 2: Research Gap Analysis
    gap_json = {
        "established_findings": [
            {
                "claim": "Multi-path consistency reduces stochastic hallucinations.",
                "evidence_refs": ["https://arxiv.org/abs/2301.0001"],
            }
        ],
        "conflicting_findings": [],
        "limitations": [
            {
                "claim": "Computational latency increases linearly with sample paths.",
                "evidence_refs": ["https://arxiv.org/abs/2301.0001"],
            }
        ],
        "missing_evidence": ["Evaluation under low-latency real-time inference regimes."],
        "potential_research_gaps": [
            "Pruning consistency paths using minimal causal explanation DAGs."
        ],
        "confidence_assessment": {
            "confidence_level": "high",
            "reliability_score": 0.90,
            "reasoning": "Consistent findings across multiple survey benchmarks.",
        },
    }
    gap_service = ResearchGapService(
        nebius_client=FakeNebiusChatClient(json.dumps(gap_json)),
        tavily_client=None,
    )
    gap_res = await gap_service.analyze(question=question, evidence=evidence)
    assert len(gap_res.potential_research_gaps) == 1
    assert gap_res.confidence_assessment.reliability_score == 0.90

    # Stage 3: Hypothesis and Experiment Planning
    plan_json = {
        "hypothesis": (
            "Causal DAG path pruning maintains >=95% of full-consistency accuracy while "
            "reducing sample inference latency by >=40% compared to greedy baseline."
        ),
        "research_objective": "Measure latency-accuracy tradeoff under causal pruning.",
        "variables": {
            "independent": ["Sampling method: Causal DAG Pruning vs Full Sampling vs Greedy"],
            "dependent": ["Accuracy", "Latency (ms)", "Hallucination Rate"],
            "controls": ["Model size (70B)", "Batch size (1)"],
        },
        "baseline": "Vanilla greedy autoregressive decoding without consistency sampling.",
        "proposed_method": "Extract minimal causal subgraph from early transformer layers.",
        "dataset_requirements": ["TruthfulQA", "GSM8K"],
        "evaluation_metrics": ["accuracy", "latency_ms", "efficiency_ratio"],
        "expected_outcome": "40% latency reduction with statistically insignificant accuracy delta.",
        "risks": ["DAG extraction overhead"],
    }
    structured_gap = StructuredResearchGap(
        research_question=question,
        potential_research_gaps=gap_res.potential_research_gaps,
        missing_evidence=gap_res.missing_evidence,
        established_findings=gap_res.established_findings,
        conflicting_findings=gap_res.conflicting_findings,
        limitations=gap_res.limitations,
        confidence_assessment=gap_res.confidence_assessment,
    )
    plan_service = ExperimentPlanService(
        nebius_client=FakeNebiusChatClient(json.dumps(plan_json))
    )
    plan_res = await plan_service.plan(structured_gap)
    assert plan_res.baseline.startswith("Vanilla greedy")
    assert "accuracy" in plan_res.evaluation_metrics

    # Stage 4: Experiment Code Generation
    code_text = '''#!/usr/bin/env python3
"""Autonomous experiment: Causal DAG pruning vs baseline greedy decoding."""
import random

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

baseline_accuracy = 0.65
proposed_accuracy = 0.81
latency_ms = 45.2
improvement = proposed_accuracy - baseline_accuracy

print(f"METRIC baseline_accuracy={baseline_accuracy:.4f}")
print(f"METRIC proposed_accuracy={proposed_accuracy:.4f}")
print(f"METRIC latency_ms={latency_ms:.2f}")
print(f"METRIC improvement={improvement:.4f}")
'''
    code_json = {
        "code": code_text,
        "dependencies": [],
        "entrypoint": "python experiment.py",
        "random_seed": 42,
        "inputs": ["Synthetic benchmark samples"],
        "outputs": ["baseline_accuracy", "proposed_accuracy", "latency_ms", "improvement"],
        "notes": "Verified safe runnable benchmark.",
    }
    code_service = ExperimentCodeService(
        nebius_client=FakeNebiusChatClient(json.dumps(code_json))
    )
    code_res = await code_service.generate(plan_res)
    assert code_res.language == "python"
    assert code_res.random_seed == 42

    # Stage 5 & 6: Secure Experiment Execution and Telemetry Capture
    settings = Settings(
        nebius_api_key="dummy-token",
        nebius_project_id="test-proj",
        nebius_results_bucket="test-bucket",
        nebius_storage_access_key_id="dummy-key",
        nebius_storage_secret_key="dummy-secret",
        nebius_storage_region="eu-north1",
        experiment_timeout_seconds=30.0,
        experiment_poll_interval_seconds=0.05,
    )
    transport = FakeNebiusTransport()
    exec_service = ExperimentExecutionService(settings, transport=transport)
    exec_res = await exec_service.execute(code_res)

    assert exec_res.status == ExperimentJobStatus.COMPLETED
    assert exec_res.exit_code == 0
    assert "baseline_accuracy" in exec_res.metrics
    assert "proposed_accuracy" in exec_res.metrics
    assert exec_res.metrics["improvement"] == 0.16

    # Stage 7 & 8: Adversarial Critique
    critic_json = {
        "verdict": "The experiment demonstrates a measurable 16% accuracy gain with low latency.",
        "hypothesis_supported": True,
        "strengths": [
            {
                "category": "methodology",
                "finding": "Grounded baseline comparison against standard greedy decoding.",
                "severity": "low",
            }
        ],
        "weaknesses": [
            {
                "category": "statistical_reasoning",
                "finding": "Single random seed run without confidence interval intervals.",
                "severity": "medium",
            }
        ],
        "threats_to_validity": [
            {
                "category": "generalizability",
                "finding": "Synthetic metrics should be replicated across OOD task sets.",
                "severity": "medium",
            }
        ],
        "recommended_followup": ["Ablate across diverse model families (Llama-3, Mistral, Nemotron)"],
        "confidence_score": 0.85,
    }
    critic_service = ResearchCriticService(
        nebius_client=FakeNebiusChatClient(json.dumps(critic_json))
    )
    from app.schemas.research import ResearchCriticRequest
    critic_res = await critic_service.critique(
        ResearchCriticRequest(
            research_question=question,
            hypothesis=plan_res.hypothesis,
            research_gap=structured_gap,
            experiment_design=plan_res,
            experiment_results=exec_res,
        )
    )
    assert critic_res.hypothesis_supported is True
    assert critic_res.confidence_score == 0.85

    # Stage 9: Final Report Generation
    report_json = {
        "title": "Investigating Causal DAG Pruning for Accelerated Factuality in Large Language Models",
        "sections": [
            {
                "key": "abstract",
                "title": "Abstract",
                "content": "Autonomous research report evaluating causal DAG pruning in multi-path reasoning.",
                "evidence_refs": ["https://arxiv.org/abs/2301.0001"],
            },
            {
                "key": "results",
                "title": "Results",
                "content": "The proposed method achieved 0.81 accuracy versus baseline 0.65 accuracy, yielding a 0.16 improvement.",
                "evidence_refs": [],
            },
            {
                "key": "critical_evaluation",
                "title": "Critical Evaluation",
                "content": "The critic evaluated single-run variance limitations.",
                "evidence_refs": [],
            },
            {
                "key": "conclusion",
                "title": "Conclusion",
                "content": "Causal DAG pruning presents a viable path toward low-latency factuality verification.",
                "evidence_refs": [],
            },
        ],
        "sources": [e.model_dump() for e in evidence],
        "confidence_assessment": {
            "confidence_level": "high",
            "reliability_score": 0.88,
            "reasoning": "Synthesized with empirical telemetry and adversarial review.",
        },
    }
    report_service = ResearchReportService(
        nebius_client=FakeNebiusChatClient(json.dumps(report_json))
    )
    from app.schemas.research import ResearchReportRequest
    report_res = await report_service.generate(
        ResearchReportRequest(
            research_question=question,
            evidence=evidence,
            research_gap=structured_gap,
            hypothesis=plan_res.hypothesis,
            experiment_plan=plan_res,
            experiment_results=exec_res,
            research_critique=critic_res,
        )
    )

    # Stage 10: Report Export & Reproducibility Review
    assert report_res.title.startswith("Investigating Causal DAG")
    assert len(report_res.sections) == 13 # Canonical 13 sections
    assert len(report_res.sources) == 2
    assert "https://arxiv.org/abs/2301.0001" in report_res.markdown
    assert "0.81" in report_res.markdown
    assert "Vanilla greedy" in plan_res.baseline
