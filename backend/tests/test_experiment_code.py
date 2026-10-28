"""Tests for the Experiment Code Generation service and AST safety validation."""

from __future__ import annotations

import asyncio
import json
import pytest
import httpx

from _fake_nebius import FakeNebiusChatClient
from app.main import app
from app.schemas.research import (
    ExperimentPlanResponse,
    ExperimentVariables,
)
from app.services.experiment_code import (
    ExperimentCodeError,
    ExperimentCodeService,
    validate_experiment_code_safety,
)

SAFE_PYTHON_CODE = '''#!/usr/bin/env python3
"""Experiment: Testing consistency metric on synthetic reasoning graph."""
import random

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Baseline: greedy decoding (no graph consistency)
baseline_acc = 0.68
# Proposed: graph consistency
proposed_acc = 0.84
improvement = proposed_acc - baseline_acc

print(f"METRIC baseline_accuracy={baseline_acc:.4f}")
print(f"METRIC proposed_accuracy={proposed_acc:.4f}")
print(f"METRIC improvement={improvement:.4f}")

if __name__ == "__main__":
    print("Done")
'''

CANNED_CODE_JSON = {
    "code": SAFE_PYTHON_CODE,
    "dependencies": [],
    "entrypoint": "python experiment.py",
    "random_seed": 42,
    "inputs": ["Synthetic QA dataset"],
    "outputs": ["baseline_accuracy", "proposed_accuracy", "improvement"],
    "notes": "Safe deterministic benchmark.",
}

SAMPLE_PLAN = ExperimentPlanResponse(
    research_question="Can explanation consistency improve hallucination detection?",
    hypothesis="Graph-conditioned consistency reduces hallucination by >=25%.",
    research_objective="Measure accuracy and hallucination rate.",
    variables=ExperimentVariables(
        independent=["decoding method"],
        dependent=["accuracy", "hallucination_rate"],
        controls=["temperature"],
    ),
    baseline="Vanilla greedy decoding",
    proposed_method="Causal graph scoring",
    dataset_requirements=["Synthetic benchmark"],
    evaluation_metrics=["accuracy", "improvement"],
    expected_outcome="Statistically significant improvement",
    risks=[],
    model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
)


def test_safe_code_passes_security_audit():
    is_safe, error = validate_experiment_code_safety(SAFE_PYTHON_CODE)
    assert is_safe is True
    assert error is None


@pytest.mark.parametrize(
    "bad_code,expected_signal",
    [
        ("import subprocess\nsubprocess.run(['ls'])", "subprocess"),
        ("import socket\ns = socket.socket()", "socket"),
        ("import shutil\nshutil.rmtree('/tmp')", "shutil"),
        ("import requests\nrequests.get('http://evil.com')", "requests"),
        ("import os\nprint(os.environ['SECRET'])", "os.environ"),
        ("import os\nos.system('whoami')", "os.system"),
        ("eval('1 + 1')", "eval"),
        ("exec('print(1)')", "exec"),
    ],
)
def test_unsafe_operations_are_blocked(bad_code: str, expected_signal: str):
    is_safe, error = validate_experiment_code_safety(bad_code)
    assert is_safe is False
    assert expected_signal in str(error)


def test_code_generation_parses_json():
    fake_client = FakeNebiusChatClient(json.dumps(CANNED_CODE_JSON))
    service = ExperimentCodeService(nebius_client=fake_client)

    code_resp = asyncio.run(service.generate(SAMPLE_PLAN))
    assert code_resp.research_question == SAMPLE_PLAN.research_question
    assert code_resp.language == "python"
    assert code_resp.random_seed == 42
    assert "METRIC baseline_accuracy" in code_resp.code
    assert code_resp.entrypoint == "python experiment.py"


def test_unsafe_generated_code_is_rejected():
    malicious_json = dict(CANNED_CODE_JSON)
    malicious_json["code"] = "import subprocess\nsubprocess.run(['rm', '-rf', '/'])"
    fake_client = FakeNebiusChatClient(json.dumps(malicious_json))
    service = ExperimentCodeService(nebius_client=fake_client)

    with pytest.raises(ExperimentCodeError) as exc_info:
        asyncio.run(service.generate(SAMPLE_PLAN))
    assert "failed security policy" in str(exc_info.value)


@pytest.mark.asyncio
async def test_endpoint_returns_experiment_code():
    fake_client = FakeNebiusChatClient(json.dumps(CANNED_CODE_JSON))
    service = ExperimentCodeService(nebius_client=fake_client)

    async with app.router.lifespan_context(app):
        app.state.experiment_code_service = service
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/research/experiment-code",
                json={"experiment_plan": SAMPLE_PLAN.model_dump()},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["language"] == "python"
            assert data["random_seed"] == 42
