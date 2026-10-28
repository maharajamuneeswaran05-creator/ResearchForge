"""End-to-end execution layer demonstration (simulated Nebius backend)."""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
from _fake_nebius import FakeNebiusTransport  # noqa: E402

from app.config import Settings  # noqa: E402
from app.schemas.research import ExperimentCodeResponse, ExperimentJobStatus  # noqa: E402
from app.services.experiment_execution import ExperimentExecutionService  # noqa: E402

MOCK_GENERATED_CODE = ExperimentCodeResponse(
    research_question="Does dropout improve LSTM accuracy on sentiment classification?",
    language="python",
    code="""#!/usr/bin/env python3
\"\"\"Experiment: Dropout vs No-Dropout LSTM on Synthetic Sentiment Task.\"\"\"
import random

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Synthetic data (100 samples, binary sentiment)
data = [(random.random() > 0.5, random.random() > 0.5) for _ in range(100)]
train = data[:80]
test = data[80:]

# Mock LSTM models (no TensorFlow needed)
def train_model(use_dropout):
    # Simulate training
    loss = 0.45 if use_dropout else 0.50
    return loss

# Baseline: no dropout
baseline_loss = train_model(use_dropout=False)

# Proposed: with dropout
proposed_loss = train_model(use_dropout=True)

# Evaluation metrics
baseline_acc = 1.0 - baseline_loss
proposed_acc = 1.0 - proposed_loss

print(f"Baseline (no dropout) accuracy: {baseline_acc:.4f}")
print(f"Proposed (dropout=0.3) accuracy: {proposed_acc:.4f}")
print(f"METRIC baseline_accuracy={baseline_acc:.4f}")
print(f"METRIC proposed_accuracy={proposed_acc:.4f}")
print(f"METRIC improvement={(proposed_acc - baseline_acc):.4f}")

if proposed_acc > baseline_acc:
    print("Result: Dropout improved accuracy.")
else:
    print("Result: No improvement from dropout.")
""",
    dependencies=[],
    entrypoint="python experiment.py",
    random_seed=42,
    inputs=["Synthetic binary sentiment dataset (100 samples)"],
    outputs=["baseline_accuracy", "proposed_accuracy", "improvement"],
    model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    notes="Minimal experiment with synthetic data to validate isolation.",
)


def _settings(**overrides) -> Settings:
    values = {
        "nebius_api_key": "dummy-token",
        "nebius_project_id": "project-test",
        "nebius_results_bucket": "researchforge-results",
        "nebius_storage_access_key_id": "AKIAFAKE",
        "nebius_storage_secret_key": "fake-secret",
        "nebius_storage_region": "eu-north1",
        "experiment_timeout_seconds": 60.0,
        "experiment_poll_interval_seconds": 0.05,
    }
    values.update(overrides)
    return Settings(**values)


def main() -> None:
    settings = _settings()
    transport = FakeNebiusTransport()
    svc = ExperimentExecutionService(settings, transport=transport)

    print("=== Executing Generated Experiment ===")
    print(f"Research Question: {MOCK_GENERATED_CODE.research_question}")
    print(f"Code length: {len(MOCK_GENERATED_CODE.code)} chars")
    print(f"Timeout: {settings.experiment_timeout_seconds:.0f}s\n")

    result = asyncio.run(svc.execute(MOCK_GENERATED_CODE))

    print(f"Job ID: {result.job_id}")
    print(f"Status: {result.status}")
    print(f"Exit Code: {result.exit_code}")
    print(f"Execution Time: {result.execution_time_seconds:.3f}s")
    print(f"Metrics: {result.metrics}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"\n--- STDOUT ({len(result.stdout)} bytes) ---")
    print(result.stdout[:800])
    if result.stderr:
        print(f"\n--- STDERR ({len(result.stderr)} bytes) ---")
        print(result.stderr[:400])

    assert result.status == ExperimentJobStatus.COMPLETED, f"Expected COMPLETED, got {result.status}"
    assert result.exit_code == 0, f"Expected exit_code=0, got {result.exit_code}"
    assert "baseline_accuracy" in result.metrics
    assert "proposed_accuracy" in result.metrics
    assert "improvement" in result.metrics

    print("\nEnd-to-end execution test passed.")


def http_round_trip() -> None:
    """Exercise the HTTP endpoints with the simulated Nebius backend."""
    from app.main import app

    transport = FakeNebiusTransport()
    service = ExperimentExecutionService(_settings(), transport=transport)

    async def run() -> None:
        async with app.router.lifespan_context(app):
            app.state.experiment_execution_service = service
            async with httpx.ASGITransport(app=app) as asgi:
                async with httpx.AsyncClient(
                    transport=asgi, base_url="http://testserver"
                ) as client:
                    response = await client.post(
                        "/api/research/experiment-execute",
                        json={
                            "experiment_code": MOCK_GENERATED_CODE.model_dump(),
                            "wait": True,
                        },
                    )
                    assert response.status_code == 200, response.text
                    payload = response.json()
                    print(f"\nHTTP execute -> {response.status_code} {payload['status']}")
                    assert payload["status"] == "completed", payload
                    assert payload["metrics"]["improvement"] == 0.05, payload

                    status = await client.get(
                        f"/api/research/experiment-jobs/{payload['job_id']}"
                    )
                    assert status.status_code == 200, status.text
                    print(f"HTTP job status -> {status.status_code} {status.json()['status']}")
                    assert status.json()["status"] == "completed", status.text

    asyncio.run(run())
    print("HTTP round trip passed.")


if __name__ == "__main__":
    main()
    http_round_trip()
