"""Experiment execution service: run generated experiment code on Nebius Serverless AI.

Generated experiment code is never executed inside the FastAPI process.  It is
injected into a Nebius AI Cloud Serverless AI job (https://docs.nebius.com/serverless)
as a read-only file, executed by a runner script inside the job container, and
the captured output is uploaded by the container to Nebius Object Storage.  The
backend then polls the job and downloads the result document.

Captured per execution:
  - status  (pending | running | completed | failed | timeout | cancelled)
  - stdout  (full captured output of the experiment)
  - stderr  (full captured error output of the experiment)
  - exit_code
  - metrics (key/value pairs parsed from stdout lines of the form "METRIC key=value")
  - execution_time_seconds
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import logging
import math
import os
import re
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas.research import (
    ExperimentCodeResponse,
    ExperimentExecutionResult,
    ExperimentJobResponse,
    ExperimentJobStatus,
)
from app.services.nebius_serverless import (
    TIMEOUT_ERROR_CODE,
    NebiusJob,
    NebiusServerlessClient,
    NebiusServerlessError,
)
from app.services.nebius_storage import (
    NebiusObjectStorageClient,
    NebiusStorageError,
    sign_s3_request,
)

logger = logging.getLogger(__name__)

# Matches lines like:  METRIC accuracy=0.92  or  METRIC f1_score=0.87
_METRIC_LINE = re.compile(
    r"^\s*METRIC\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)\s*$", re.MULTILINE
)

# Maximum bytes captured from stdout/stderr to avoid memory issues.
_MAX_OUTPUT_BYTES = 256 * 1024  # 256 KB

# Nebius Serverless AI accepts injected files of at most 64 KiB each.
_MAX_INJECTED_FILE_BYTES = 64 * 1024

# Nebius Serverless AI enforces a minimum job timeout of one hour.
_MIN_JOB_TIMEOUT_SECONDS = 3600

# Directory inside the job container that holds the injected files.
_JOB_DIR = "/opt/researchforge"

RUNNER_SCRIPT = r'''#!/usr/bin/env python3
"""ResearchForge experiment runner.

Executed inside a Nebius Serverless AI job container.  It runs the injected
experiment script in a child process, captures stdout/stderr and uploads the
result document to Nebius Object Storage so that the backend can collect it.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s3_signing import sign_s3_request  # noqa: E402

EXPERIMENT_PATH = os.environ.get(
    "RESEARCHFORGE_EXPERIMENT_PATH", "/opt/researchforge/experiment.py"
)
RESULT_KEY = os.environ.get("RESEARCHFORGE_RESULT_KEY", "result.json")
TIMEOUT_SECONDS = float(os.environ.get("RESEARCHFORGE_TIMEOUT_SECONDS", "900"))
DEPENDENCIES = os.environ.get("RESEARCHFORGE_DEPENDENCIES", "")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION", "")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "").rstrip("/")
S3_BUCKET = os.environ.get("S3_BUCKET", "")


def _install_dependencies():
    packages = [p.strip() for p in DEPENDENCIES.split(",") if p.strip()]
    if not packages:
        return ""
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "--disable-pip-version-check",
            ]
            + packages,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except Exception as exc:  # noqa: BLE001 - setup problems must not abort the run
        return "[setup] dependency installation failed: " + str(exc) + "\n"
    if completed.returncode != 0:
        return (
            "[setup] dependency installation failed:\n"
            + (completed.stdout + completed.stderr)[-2000:]
            + "\n"
        )
    return ""


def _upload(payload):
    body = json.dumps(payload).encode("utf-8")
    host = S3_ENDPOINT_URL.split("://", 1)[-1].strip("/")
    path = "/" + S3_BUCKET + "/" + RESULT_KEY.lstrip("/")
    headers = sign_s3_request(
        method="PUT",
        path=path,
        host=host,
        region=AWS_DEFAULT_REGION,
        access_key_id=AWS_ACCESS_KEY_ID,
        secret_key=AWS_SECRET_ACCESS_KEY,
        payload=body,
    )
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        S3_ENDPOINT_URL + path, data=body, headers=headers, method="PUT"
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        response.read()


def main():
    notes = _install_dependencies()
    started = time.monotonic()
    stdout = ""
    stderr = notes
    exit_code = None
    timed_out = False

    try:
        completed = subprocess.run(
            [sys.executable, EXPERIMENT_PATH],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=os.path.dirname(EXPERIMENT_PATH),
        )
        stdout = completed.stdout or ""
        stderr += completed.stderr or ""
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (
            exc.stdout.decode("utf-8", "replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr += (
            exc.stderr.decode("utf-8", "replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        stderr += "\n[runner] experiment timed out after " + str(TIMEOUT_SECONDS) + "s\n"
    except Exception as exc:  # noqa: BLE001 - reported through the result document
        stderr += "\n[runner] failed to run experiment: " + str(exc) + "\n"

    elapsed = time.monotonic() - started
    payload = {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "execution_time_seconds": round(elapsed, 3),
    }

    try:
        _upload(payload)
    except Exception as exc:  # noqa: BLE001 - surfaced through the job status
        print("[runner] failed to upload result: " + str(exc), file=sys.stderr)
        return 2

    print(
        "[runner] experiment finished in "
        + ("%.2f" % elapsed)
        + "s (exit_code="
        + str(exit_code)
        + ")"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


class ExperimentExecutionError(Exception):
    """Raised when the execution layer itself fails (not the experiment code)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NebiusConfigurationError(ExperimentExecutionError):
    """Raised when required Nebius Cloud infrastructure variables are not configured."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        message = (
            "Nebius Serverless AI execution is not configured. Missing required environment variables: "
            + ", ".join(missing)
            + ". Add them to backend/.env to enable live execution."
        )
        super().__init__(message, status_code=503)


@dataclass(slots=True)
class _JobRecord:
    """Bookkeeping for a submitted experiment job."""

    job_id: str
    nebius_job_id: str
    name: str
    result_key: str
    timeout_seconds: float
    research_question: str
    submitted_at: str
    started_monotonic: float
    is_demo: bool = False
    demo_result: ExperimentExecutionResult | None = None


class ExperimentExecutionService:
    """Execute generated experiment code on Nebius Serverless AI jobs."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: Any = None,
    ) -> None:
        self._settings = settings
        self._jobs = NebiusServerlessClient(settings, transport=transport)
        self._storage = NebiusObjectStorageClient(settings, transport=transport)
        self._records: dict[str, _JobRecord] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_demo_requested(self, demo: bool | None = None) -> bool:
        """Return True if demo mode is requested either via argument or setting."""
        if demo is not None:
            return demo
        return bool(getattr(self._settings, "experiment_demo_mode", False))

    def missing_configuration(self) -> list[str]:
        """Return list of required Nebius cloud environment variables that are missing."""
        missing: list[str] = []
        if not self._settings.nebius_project_id:
            missing.append("NEBIUS_PROJECT_ID")
        if not self._settings.nebius_results_bucket:
            missing.append("NEBIUS_RESULTS_BUCKET")
        if not self._settings.nebius_storage_region:
            missing.append("NEBIUS_STORAGE_REGION")
        if not self._settings.nebius_storage_access_key_id:
            missing.append("NEBIUS_STORAGE_ACCESS_KEY_ID")
        if not self._settings.nebius_storage_secret_key:
            missing.append("NEBIUS_STORAGE_SECRET_KEY")
        return missing

    @property
    def is_configured(self) -> bool:
        """True if all required Nebius cloud environment variables are configured."""
        return len(self.missing_configuration()) == 0

    async def _execute_demo(
        self,
        experiment_code: ExperimentCodeResponse,
        timeout: float,
    ) -> ExperimentExecutionResult:
        """Execute experiment in an explicit local demo mode (no Nebius cloud calls)."""
        from app.services.experiment_code import validate_experiment_code_safety

        started = time.monotonic()
        job_id = f"demo-{uuid.uuid4().hex[:12]}"
        banner = (
            "========================================================================\n"
            "[DEMO MODE: SIMULATED EXECUTION - NOT A REAL NEBIUS CLOUD RUN]\n"
            "This experiment was simulated locally because EXPERIMENT_DEMO_MODE is enabled\n"
            "or explicitly requested. No Nebius Serverless compute or storage was billed.\n"
            "========================================================================\n\n"
        )

        # 1. Pre-execution static security audit
        is_safe, safety_err = validate_experiment_code_safety(experiment_code.code)
        if not is_safe:
            return ExperimentExecutionResult(
                job_id=job_id,
                status=ExperimentJobStatus.FAILED,
                exit_code=1,
                stdout=banner + f"[SECURITY POLICY VIOLATION]\nExecution blocked: {safety_err}\n",
                stderr=f"Code security violation: {safety_err}",
                metrics={"_demo_simulated": True},
                execution_time_seconds=0.0,
                error=f"Code safety check failed: {safety_err}",
                research_question=experiment_code.research_question,
                is_demo=True,
            )

        # 2. Scrubbed environment preventing access to host API keys and cloud credentials
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "WINDIR": os.environ.get("WINDIR", "C:\\Windows"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "experiment.py"
            script_path.write_text(experiment_code.code, encoding="utf-8")
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(script_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmpdir,
                    env=safe_env,
                )
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                stdout = banner + stdout_bytes.decode("utf-8", "replace")[:_MAX_OUTPUT_BYTES]
                stderr = stderr_bytes.decode("utf-8", "replace")[:_MAX_OUTPUT_BYTES]
                exit_code = proc.returncode
                status = (
                    ExperimentJobStatus.COMPLETED
                    if exit_code == 0
                    else ExperimentJobStatus.FAILED
                )
                err_msg = (
                    None
                    if exit_code == 0
                    else f"Demo experiment script exited with code {exit_code}"
                )
            except asyncio.TimeoutError:
                stdout = banner + f"\n[runner] experiment timed out after {timeout:.0f}s\n"
                stderr = f"Timed out after {timeout:.0f}s"
                exit_code = -1
                status = ExperimentJobStatus.TIMEOUT
                err_msg = f"Demo experiment timed out after {timeout:.0f}s"
            except Exception as exc:
                stdout = banner
                stderr = str(exc)
                exit_code = 1
                status = ExperimentJobStatus.FAILED
                err_msg = f"Demo runner error: {exc}"

        elapsed = time.monotonic() - started
        metrics = _extract_metrics(stdout)
        metrics["_demo_simulated"] = True

        return ExperimentExecutionResult(
            job_id=job_id,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            metrics=metrics,
            execution_time_seconds=round(elapsed, 3),
            error=err_msg,
            research_question=experiment_code.research_question,
            is_demo=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit(
        self,
        experiment_code: ExperimentCodeResponse,
        *,
        timeout_seconds: float | None = None,
        demo: bool | None = None,
    ) -> ExperimentJobResponse:
        """Submit an experiment as a Nebius Serverless AI job (or run demo if requested)."""
        timeout = self._resolve_timeout(timeout_seconds)

        if self.is_demo_requested(demo):
            result = await self._execute_demo(experiment_code, timeout)
            record = _JobRecord(
                job_id=result.job_id,
                nebius_job_id="",
                name=f"researchforge-{result.job_id}",
                result_key="",
                timeout_seconds=timeout,
                research_question=experiment_code.research_question,
                submitted_at=datetime.now().astimezone().isoformat(),
                started_monotonic=time.monotonic(),
                is_demo=True,
                demo_result=result,
            )
            self._records[result.job_id] = record
            return ExperimentJobResponse(
                job_id=result.job_id,
                status=result.status,
                nebius_job_id=None,
                research_question=experiment_code.research_question,
                submitted_at=record.submitted_at,
                result=result,
                is_demo=True,
            )

        self._require_configuration()

        job_id = uuid.uuid4().hex
        name = f"researchforge-{job_id}"
        result_key = f"researchforge/{job_id}.json"
        spec = self._build_spec(experiment_code, result_key, timeout)

        try:
            nebius_job_id = await self._jobs.create_job(name=name, spec=spec)
        except NebiusServerlessError as exc:
            logger.exception("Failed to submit Nebius Serverless AI job")
            raise ExperimentExecutionError(
                f"Failed to submit Nebius Serverless AI job: {exc}",
                status_code=exc.status_code or 502,
            ) from exc

        record = _JobRecord(
            job_id=job_id,
            nebius_job_id=nebius_job_id,
            name=name,
            result_key=result_key,
            timeout_seconds=timeout,
            research_question=experiment_code.research_question,
            submitted_at=datetime.now().astimezone().isoformat(),
            started_monotonic=time.monotonic(),
            is_demo=False,
        )
        self._records[job_id] = record

        return ExperimentJobResponse(
            job_id=job_id,
            status=ExperimentJobStatus.PENDING,
            nebius_job_id=nebius_job_id,
            research_question=experiment_code.research_question,
            submitted_at=record.submitted_at,
            is_demo=False,
        )

    async def get_job(self, job_id: str) -> ExperimentJobResponse:
        """Read the status of a submitted experiment job."""
        record = self._records.get(job_id)
        if record is not None and record.is_demo and record.demo_result is not None:
            return ExperimentJobResponse(
                job_id=job_id,
                status=record.demo_result.status,
                nebius_job_id=None,
                research_question=record.research_question,
                error=record.demo_result.error,
                submitted_at=record.submitted_at,
                result=record.demo_result,
                is_demo=True,
            )

        record = await self._resolve_record(job_id)
        job = await self._fetch_job(record)

        status = _map_state(job)
        result: ExperimentExecutionResult | None = None
        if job.is_terminal:
            result = await self._collect_result(record, job)
            status = result.status

        return ExperimentJobResponse(
            job_id=job_id,
            status=status,
            nebius_job_id=record.nebius_job_id,
            research_question=record.research_question,
            error=job.error_message,
            submitted_at=record.submitted_at,
            result=result,
            is_demo=record.is_demo,
        )

    async def wait(
        self,
        job_id: str,
        *,
        timeout_seconds: float | None = None,
    ) -> ExperimentExecutionResult:
        """Poll a job until it finishes and collect its result."""
        record = self._records.get(job_id)
        if record is not None and record.is_demo and record.demo_result is not None:
            return record.demo_result

        record = await self._resolve_record(job_id)
        timeout = timeout_seconds if timeout_seconds is not None else record.timeout_seconds
        poll_interval = max(0.1, self._settings.experiment_poll_interval_seconds)
        # The deadline is anchored on the submission time so that a timeout is
        # not silently extended by polling.
        deadline = record.started_monotonic + timeout

        while True:
            job = await self._fetch_job(record)
            if job.is_terminal:
                return await self._collect_result(record, job)

            if time.monotonic() >= deadline:
                logger.warning(
                    "experiment job_id=%s timed out after %.1fs, cancelling",
                    job_id,
                    timeout,
                )
                await self._cancel(record)
                return ExperimentExecutionResult(
                    job_id=job_id,
                    status=ExperimentJobStatus.TIMEOUT,
                    error=f"Experiment timed out after {timeout:.0f}s",
                    execution_time_seconds=round(timeout, 3),
                    research_question=record.research_question,
                    is_demo=False,
                )

            await asyncio.sleep(poll_interval)

    async def execute(
        self,
        experiment_code: ExperimentCodeResponse,
        *,
        timeout_seconds: float | None = None,
        demo: bool | None = None,
    ) -> ExperimentExecutionResult:
        """Submit an experiment and wait for its result."""
        submitted = await self.submit(
            experiment_code, timeout_seconds=timeout_seconds, demo=demo
        )
        return await self.wait(
            submitted.job_id, timeout_seconds=timeout_seconds
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_timeout(self, timeout_seconds: float | None) -> float:
        if timeout_seconds is not None:
            return float(timeout_seconds)
        return float(self._settings.experiment_timeout_seconds)

    def _require_configuration(self) -> None:
        missing = self.missing_configuration()
        if missing:
            raise NebiusConfigurationError(missing)

    def _build_spec(
        self,
        experiment_code: ExperimentCodeResponse,
        result_key: str,
        timeout: float,
    ) -> dict[str, Any]:
        settings = self._settings
        experiment_bytes = experiment_code.code.encode("utf-8")
        if len(experiment_bytes) > _MAX_INJECTED_FILE_BYTES:
            raise ExperimentExecutionError(
                "Generated experiment code exceeds the "
                f"{_MAX_INJECTED_FILE_BYTES} byte limit for injected files",
                status_code=422,
            )

        storage_endpoint = (
            f"https://storage.{settings.nebius_storage_region}.nebius.cloud"
        )
        environment = [
            {"name": "AWS_ACCESS_KEY_ID", "value": settings.nebius_storage_access_key_id},
            {
                "name": "AWS_SECRET_ACCESS_KEY",
                "value": settings.nebius_storage_secret_key,
            },
            {"name": "AWS_DEFAULT_REGION", "value": settings.nebius_storage_region},
            {"name": "S3_ENDPOINT_URL", "value": storage_endpoint},
            {"name": "S3_BUCKET", "value": settings.nebius_results_bucket},
            {
                "name": "RESEARCHFORGE_EXPERIMENT_PATH",
                "value": f"{_JOB_DIR}/experiment.py",
            },
            {"name": "RESEARCHFORGE_RESULT_KEY", "value": result_key},
            {
                "name": "RESEARCHFORGE_TIMEOUT_SECONDS",
                "value": str(int(max(1, timeout))),
            },
            {
                "name": "RESEARCHFORGE_DEPENDENCIES",
                "value": ",".join(experiment_code.dependencies or []),
            },
            {"name": "PYTHONUNBUFFERED", "value": "1"},
        ]

        spec: dict[str, Any] = {
            "image": settings.nebius_job_image,
            "containerCommand": "python3",
            "args": f"{_JOB_DIR}/runner.py",
            "workingDir": _JOB_DIR,
            "timeout": f"{max(_MIN_JOB_TIMEOUT_SECONDS, math.ceil(timeout))}s",
            "disk": {
                "type": "NETWORK_SSD",
                "sizeBytes": str(settings.nebius_job_disk_size_bytes),
            },
            "environmentVariables": environment,
            "injectedFiles": [
                {
                    "containerPath": f"{_JOB_DIR}/experiment.py",
                    "content": _b64(experiment_bytes),
                },
                {
                    "containerPath": f"{_JOB_DIR}/runner.py",
                    "content": _b64(RUNNER_SCRIPT.encode("utf-8")),
                },
                {
                    "containerPath": f"{_JOB_DIR}/s3_signing.py",
                    "content": _b64(inspect.getsource(sign_s3_request).encode("utf-8")),
                },
            ],
        }

        if settings.nebius_job_platform:
            spec["platform"] = settings.nebius_job_platform
        if settings.nebius_job_preset:
            spec["preset"] = settings.nebius_job_preset
        if settings.nebius_job_subnet_id:
            spec["subnetId"] = settings.nebius_job_subnet_id

        return spec

    async def _resolve_record(self, job_id: str) -> _JobRecord:
        record = self._records.get(job_id)
        if record is not None:
            return record

        # The job was not submitted by this process instance: look it up by
        # name so that tracking survives a backend restart.
        try:
            job = await self._jobs.get_job_by_name(f"researchforge-{job_id}")
        except NebiusServerlessError as exc:
            raise ExperimentExecutionError(
                f"Failed to read Nebius Serverless AI job {job_id}: {exc}",
                status_code=exc.status_code or 502,
            ) from exc

        if job is None or not job.job_id:
            raise ExperimentExecutionError(
                f"Unknown experiment job: {job_id}", status_code=404
            )

        record = _JobRecord(
            job_id=job_id,
            nebius_job_id=job.job_id,
            name=job.name,
            result_key=f"researchforge/{job_id}.json",
            timeout_seconds=float(self._settings.experiment_timeout_seconds),
            research_question="",
            submitted_at=job.created_at or "",
            started_monotonic=time.monotonic(),
        )
        self._records[job_id] = record
        return record

    async def _fetch_job(self, record: _JobRecord) -> NebiusJob:
        try:
            return await self._jobs.get_job(record.nebius_job_id)
        except NebiusServerlessError as exc:
            raise ExperimentExecutionError(
                f"Failed to read Nebius Serverless AI job {record.job_id}: {exc}",
                status_code=exc.status_code or 502,
            ) from exc

    async def _cancel(self, record: _JobRecord) -> None:
        try:
            await self._jobs.cancel_job(record.nebius_job_id)
        except NebiusServerlessError as exc:
            logger.warning(
                "experiment job_id=%s could not be cancelled: %s", record.job_id, exc
            )

    async def _collect_result(
        self, record: _JobRecord, job: NebiusJob
    ) -> ExperimentExecutionResult:
        status = _map_state(job)
        error = job.error_message or job.error_code
        stdout = ""
        stderr = ""
        metrics: dict[str, Any] = {}
        exit_code: int | None = None
        duration = _job_duration(job)

        try:
            payload = await self._storage.get_object(
                self._settings.nebius_results_bucket, record.result_key
            )
            document = json.loads(payload.decode("utf-8"))
            if not isinstance(document, dict):
                raise ValueError("result document is not a JSON object")
        except (NebiusStorageError, ValueError, UnicodeDecodeError) as exc:
            logger.warning(
                "experiment job_id=%s result could not be retrieved: %s",
                record.job_id,
                exc,
            )
            document = None
            if status == ExperimentJobStatus.COMPLETED:
                status = ExperimentJobStatus.FAILED
                error = f"Experiment result could not be retrieved: {exc}"

        if document is not None:
            stdout = _truncate(str(document.get("stdout") or ""))
            stderr = _truncate(str(document.get("stderr") or ""))
            exit_code = document.get("exit_code")
            metrics = _extract_metrics(stdout)
            duration = float(document.get("execution_time_seconds") or duration)

            if document.get("timed_out"):
                status = ExperimentJobStatus.TIMEOUT
                error = error or "Experiment timed out"
            elif status == ExperimentJobStatus.COMPLETED and exit_code != 0:
                status = ExperimentJobStatus.FAILED
                error = (
                    error
                    or _first_error_line(stderr)
                    or f"Experiment exited with code {exit_code}"
                )

        return ExperimentExecutionResult(
            job_id=record.job_id,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            metrics=metrics,
            execution_time_seconds=round(duration, 3),
            error=error,
            research_question=record.research_question,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _map_state(job: NebiusJob) -> ExperimentJobStatus:
    """Map a Nebius job state onto the experiment job status."""
    if job.state == "COMPLETED":
        return ExperimentJobStatus.COMPLETED
    if job.state == "CANCELLED":
        return ExperimentJobStatus.CANCELLED
    if job.state in ("FAILED", "ERROR"):
        if (job.error_code or "").upper() == TIMEOUT_ERROR_CODE.upper():
            return ExperimentJobStatus.TIMEOUT
        return ExperimentJobStatus.FAILED
    if job.state == "RUNNING":
        return ExperimentJobStatus.RUNNING
    return ExperimentJobStatus.PENDING


def _job_duration(job: NebiusJob) -> float:
    """Elapsed time of a job based on its start and finish timestamps."""
    started = _parse_timestamp(job.started_at)
    finished = _parse_timestamp(job.finished_at)
    if started is None or finished is None:
        return 0.0
    return max(0.0, (finished - started).total_seconds())


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _truncate(text: str) -> str:
    """Truncate captured output to _MAX_OUTPUT_BYTES characters."""
    if len(text) <= _MAX_OUTPUT_BYTES:
        return text
    return text[:_MAX_OUTPUT_BYTES] + "\n[output truncated]"


def _extract_metrics(stdout: str) -> dict[str, Any]:
    """
    Parse lines of the form  METRIC key=value  from stdout.

    Values are coerced to float when possible, left as str otherwise.
    Example stdout lines:
        METRIC accuracy=0.923
        METRIC f1=0.87
        METRIC training_time=12.4
    """
    metrics: dict[str, Any] = {}
    for match in _METRIC_LINE.finditer(stdout):
        key = match.group(1)
        raw_val = match.group(2).strip()
        try:
            val: Any = float(raw_val)
        except ValueError:
            val = raw_val
        metrics[key] = val
    return metrics


def _first_error_line(stderr: str) -> str | None:
    """Return the last non-empty line of stderr as a compact error summary."""
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    return lines[-1] if lines else None
