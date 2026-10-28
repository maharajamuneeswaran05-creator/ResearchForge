"""Smoke tests for ExperimentExecutionService against a fake Nebius backend."""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fake_nebius import FakeNebiusTransport  # noqa: E402

from app.config import Settings  # noqa: E402
from app.schemas.research import (  # noqa: E402
    ExperimentCodeResponse,
    ExperimentJobStatus,
)
from app.services.experiment_execution import (  # noqa: E402
    ExperimentExecutionError,
    ExperimentExecutionService,
)


def _settings(**overrides) -> Settings:
    values = {
        "nebius_api_key": "dummy-token",
        "nebius_project_id": "project-test",
        "nebius_results_bucket": "researchforge-results",
        "nebius_storage_access_key_id": "AKIAFAKE",
        "nebius_storage_secret_key": "fake-secret",
        "nebius_storage_region": "eu-north1",
        "experiment_timeout_seconds": 30.0,
        "experiment_poll_interval_seconds": 0.05,
    }
    values.update(overrides)
    return Settings(**values)


def _code(src: str) -> ExperimentCodeResponse:
    return ExperimentCodeResponse(
        research_question="Test",
        language="python",
        code=src,
        dependencies=[],
        model="test",
    )


def test_completed_with_metrics():
    transport = FakeNebiusTransport()
    svc = ExperimentExecutionService(_settings(), transport=transport)
    src = (
        "print('hello')\n"
        "print('METRIC accuracy=0.95')\n"
        "print('METRIC f1=0.88')\n"
    )
    r = asyncio.run(svc.execute(_code(src)))
    assert r.status == ExperimentJobStatus.COMPLETED, r
    assert r.exit_code == 0, r
    assert "hello" in r.stdout, r.stdout
    assert r.metrics == {"accuracy": 0.95, "f1": 0.88}, r.metrics
    assert r.execution_time_seconds > 0, r
    assert r.error is None, r
    print("PASS test_completed_with_metrics")


def test_failed_job():
    transport = FakeNebiusTransport()
    svc = ExperimentExecutionService(_settings(), transport=transport)
    src = "raise ValueError('intentional failure')\n"
    r = asyncio.run(svc.execute(_code(src)))
    assert r.status == ExperimentJobStatus.FAILED, r
    assert r.exit_code not in (0, None), r
    assert r.error is not None, r
    assert "intentional failure" in r.stderr, r.stderr
    print("PASS test_failed_job")


def test_nebius_side_failure():
    transport = FakeNebiusTransport(fail_jobs=True)
    svc = ExperimentExecutionService(_settings(), transport=transport)
    r = asyncio.run(svc.execute(_code("print('never runs')\n")))
    assert r.status == ExperimentJobStatus.FAILED, r
    assert r.error is not None, r
    print("PASS test_nebius_side_failure")


def test_timeout():
    transport = FakeNebiusTransport()
    svc = ExperimentExecutionService(_settings(), transport=transport)
    src = "import time\ntime.sleep(30)\n"
    r = asyncio.run(svc.execute(_code(src), timeout_seconds=2.0))
    assert r.status == ExperimentJobStatus.TIMEOUT, r
    assert "timed out" in (r.error or "").lower(), r
    assert r.execution_time_seconds is not None
    print("PASS test_timeout")


def test_submit_then_poll():
    transport = FakeNebiusTransport()
    svc = ExperimentExecutionService(_settings(), transport=transport)
    src = "print('METRIC loss=0.25')\n"

    async def scenario():
        submitted = await svc.submit(_code(src))
        assert submitted.status == ExperimentJobStatus.PENDING, submitted
        assert submitted.nebius_job_id, submitted
        for _ in range(200):
            status = await svc.get_job(submitted.job_id)
            if status.status not in (ExperimentJobStatus.PENDING, ExperimentJobStatus.RUNNING):
                return status
            await asyncio.sleep(0.05)
        raise AssertionError("job did not finish")

    status = asyncio.run(scenario())
    assert status.status == ExperimentJobStatus.COMPLETED, status
    assert status.result is not None, status
    assert status.result.metrics == {"loss": 0.25}, status.result.metrics
    print("PASS test_submit_then_poll")


def test_job_payload_shape():
    transport = FakeNebiusTransport()
    svc = ExperimentExecutionService(_settings(), transport=transport)

    async def scenario():
        submitted = await svc.submit(_code("print('x')\n"))
        return submitted

    submitted = asyncio.run(scenario())
    create_calls = [
        url for method, url in transport.requests if method == "POST" and url.endswith("/ai/v1/jobs")
    ]
    assert create_calls, transport.requests
    job = transport.jobs[submitted.nebius_job_id]
    spec = job["spec"]
    assert spec["timeout"].endswith("s")
    assert spec["disk"]["type"] == "NETWORK_SSD"
    env_names = {e["name"] for e in spec["environmentVariables"]}
    assert "AWS_ACCESS_KEY_ID" in env_names
    assert "S3_BUCKET" in env_names
    assert {"experiment.py", "runner.py", "s3_signing.py"} <= set(job["files"])
    print("PASS test_job_payload_shape")


def test_missing_configuration():
    svc = ExperimentExecutionService(
        Settings(nebius_api_key="dummy-token"), transport=FakeNebiusTransport()
    )
    try:
        asyncio.run(svc.execute(_code("print('x')\n")))
    except ExperimentExecutionError as exc:
        assert exc.status_code == 503, exc
        assert "NEBIUS_PROJECT_ID" in str(exc), exc
        print("PASS test_missing_configuration")
        return
    raise AssertionError("expected ExperimentExecutionError")


def test_structured_configuration_error_on_route():
    import httpx
    from app.main import app

    svc = ExperimentExecutionService(
        Settings(nebius_api_key="dummy-token"), transport=FakeNebiusTransport()
    )

    async def scenario():
        async with app.router.lifespan_context(app):
            app.state.experiment_execution_service = svc
            async with httpx.ASGITransport(app=app) as asgi:
                async with httpx.AsyncClient(
                    transport=asgi, base_url="http://testserver"
                ) as client:
                    response = await client.post(
                        "/api/research/experiment-execute",
                        json={
                            "experiment_code": _code("print('x')\n").model_dump(),
                            "wait": True,
                        },
                    )
                    assert response.status_code == 503, response.status_code
                    data = response.json()
                    detail = data.get("detail", {})
                    assert detail.get("error") == "NebiusExecutionNotConfigured", data
                    assert "NEBIUS_PROJECT_ID" in detail.get("missing_variables", []), data
                    print("PASS test_structured_configuration_error_on_route")

    asyncio.run(scenario())


def test_explicit_demo_mode():
    svc = ExperimentExecutionService(
        Settings(nebius_api_key="dummy-token"), transport=FakeNebiusTransport()
    )
    src = "print('METRIC demo_score=0.99')\n"
    res = asyncio.run(svc.execute(_code(src), demo=True))
    assert res.is_demo is True, res
    assert res.status == ExperimentJobStatus.COMPLETED, res
    assert "DEMO MODE" in res.stdout, res.stdout
    assert res.metrics.get("_demo_simulated") is True, res.metrics
    assert res.metrics.get("demo_score") == 0.99, res.metrics
    print("PASS test_explicit_demo_mode")


def test_unknown_job():
    transport = FakeNebiusTransport()
    svc = ExperimentExecutionService(_settings(), transport=transport)
    try:
        asyncio.run(svc.get_job("does-not-exist"))
    except ExperimentExecutionError as exc:
        assert exc.status_code == 404, exc
        print("PASS test_unknown_job")
        return
    raise AssertionError("expected ExperimentExecutionError")


if __name__ == "__main__":
    test_completed_with_metrics()
    test_failed_job()
    test_nebius_side_failure()
    test_timeout()
    test_submit_then_poll()
    test_job_payload_shape()
    test_missing_configuration()
    test_structured_configuration_error_on_route()
    test_explicit_demo_mode()
    test_unknown_job()
    print("All tests passed.")
