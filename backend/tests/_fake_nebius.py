"""In-process fakes of the Nebius AI Cloud APIs used by the backend.

The fake emulates:
  - ``POST /ai/v1/jobs``            (create a Serverless AI job)
  - ``GET  /ai/v1/jobs/{id}``       (read a job)
  - ``GET  /ai/v1/jobs/get-by-name``(read a job by name)
  - ``POST /ai/v1/jobs/cancel``     (cancel a job)
  - ``GET  https://storage.<region>.nebius.cloud/<bucket>/<key>`` (read a result)

To stay hermetic the job container is simulated locally: the injected files are
written to a temporary directory and the injected runner script is executed with
the local interpreter.  The runner uploads its result document to a local
throwaway HTTP server that stands in for Object Storage, which is exactly the
path the real container takes.  No network access is required.

``FakeNebiusChatClient`` stubs the Nemotron chat API for the model-driven
phases (critic, report) so their parsing and validation can be tested offline.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.services.nebius import NebiusClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _LocalObjectStore:
    """Minimal S3-like endpoint used by the simulated job container."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self._lock = threading.Lock()
        store = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # noqa: D102 - silence logs
                pass

            def do_PUT(self) -> None:  # noqa: N802 - http.server API
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                with store._lock:
                    store.objects[self.path] = body
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                with store._lock:
                    body = store.objects.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


class FakeNebiusTransport(httpx.AsyncBaseTransport):
    """httpx transport that simulates the Nebius Serverless AI + Object Storage APIs."""

    def __init__(
        self,
        *,
        fail_jobs: bool = False,
        install_dependencies: bool = False,
        job_result_override: dict[str, Any] | None = None,
    ) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.objects: dict[str, bytes] = {}
        self.requests: list[tuple[str, str]] = []
        self.fail_jobs = fail_jobs
        self.install_dependencies = install_dependencies
        self.job_result_override = job_result_override
        self._counter = 0
        self._lock = threading.Lock()
        self._store = _LocalObjectStore()
        self._tmpdirs: list[str] = []

    # -- httpx API ------------------------------------------------------

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        host = request.url.host
        self.requests.append((request.method, str(request.url)))

        if host.startswith("storage."):
            return self._handle_storage(request)

        if path == "/ai/v1/jobs" and request.method == "POST":
            return self._handle_create(request)
        if path == "/ai/v1/jobs/get-by-name" and request.method == "GET":
            return self._handle_get_by_name(request)
        if path == "/ai/v1/jobs/cancel" and request.method == "POST":
            return self._handle_cancel(request)
        if path.startswith("/ai/v1/jobs/") and request.method == "GET":
            return self._handle_get(path.rsplit("/", 1)[-1])

        return httpx.Response(404, json={"error": f"unhandled route {path}"})

    async def aclose(self) -> None:
        """Called by httpx whenever a client is closed.

        The local Object Storage stand-in must outlive individual requests, so
        it is only shut down through :meth:`close`.
        """
        return None

    def close(self) -> None:
        """Release the resources held by the fake."""
        self._store.close()
        for tmp in self._tmpdirs:
            shutil.rmtree(tmp, ignore_errors=True)
        self._tmpdirs.clear()

    # -- handlers -------------------------------------------------------

    def _handle_create(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        spec = body.get("spec") or {}
        name = (body.get("metadata") or {}).get("name") or f"job-{self._counter}"

        with self._lock:
            self._counter += 1
            job_id = f"job-{self._counter:04d}"

        job: dict[str, Any] = {
            "id": job_id,
            "name": name,
            "state": "PROVISIONING",
            "stateDetails": None,
            "createdAt": _now(),
            "startedAt": None,
            "finishedAt": None,
            "cancel": threading.Event(),
            "spec": spec,
            "files": self._decode_files(spec.get("injectedFiles") or []),
        }
        self.jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_job, args=(job,), daemon=True
        )
        thread.start()

        return httpx.Response(200, json={"resourceId": job_id, "metadata": {"id": job_id}})

    def _handle_get(self, job_id: str) -> httpx.Response:
        job = self.jobs.get(job_id)
        if job is None:
            return httpx.Response(404, json={"error": "job not found"})
        return httpx.Response(200, json=self._job_payload(job))

    def _handle_get_by_name(self, request: httpx.Request) -> httpx.Response:
        name = request.url.params.get("name")
        for job in self.jobs.values():
            if job["name"] == name:
                return httpx.Response(200, json=self._job_payload(job))
        return httpx.Response(404, json={"error": "job not found"})

    def _handle_cancel(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        job = self.jobs.get(body.get("id"))
        if job is None:
            return httpx.Response(404, json={"error": "job not found"})
        job["cancel"].set()
        if job["state"] not in ("COMPLETED", "FAILED", "CANCELLED", "ERROR"):
            job["state"] = "CANCELLING"
        return httpx.Response(200, json={})

    def _handle_storage(self, request: httpx.Request) -> httpx.Response:
        key = request.url.path.lstrip("/")
        body = self.objects.get(key)
        if body is None:
            return httpx.Response(404, json={"error": "no such key"})
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})

    # -- simulation -----------------------------------------------------

    @staticmethod
    def _decode_files(injected: list[dict[str, Any]]) -> dict[str, str]:
        files: dict[str, str] = {}
        for item in injected:
            path = str(item.get("containerPath") or "")
            content = base64.b64decode(item.get("content") or "").decode("utf-8")
            files[os.path.basename(path)] = content
        return files

    def _job_payload(self, job: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "metadata": {
                "id": job["id"],
                "name": job["name"],
                "createdAt": job["createdAt"],
            },
            "status": {
                "state": job["state"],
                "startedAt": job["startedAt"],
                "finishedAt": job["finishedAt"],
            },
        }
        if job["stateDetails"]:
            payload["status"]["stateDetails"] = job["stateDetails"]
        return payload

    def _run_job(self, job: dict[str, Any]) -> None:
        if self.fail_jobs:
            job["state"] = "FAILED"
            job["stateDetails"] = {
                "code": "ContainerFailed",
                "message": "Simulated container failure",
            }
            job["startedAt"] = job["startedAt"] or _now()
            job["finishedAt"] = _now()
            return

        tmpdir = tempfile.mkdtemp(prefix="researchforge-job-")
        self._tmpdirs.append(tmpdir)
        for name, content in job["files"].items():
            (Path(tmpdir) / name).write_text(content, encoding="utf-8")

        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        for item in job["spec"].get("environmentVariables") or []:
            name = str(item.get("name") or "")
            if not name:
                continue
            if name == "RESEARCHFORGE_DEPENDENCIES" and not self.install_dependencies:
                continue
            env[name] = str(item.get("value") or "")

        # Redirect the container to the local stand-in for Object Storage.
        env["S3_ENDPOINT_URL"] = self._store.url
        env["RESEARCHFORGE_EXPERIMENT_PATH"] = str(Path(tmpdir) / "experiment.py")

        job["state"] = "RUNNING"
        job["startedAt"] = _now()

        timeout = float(env.get("RESEARCHFORGE_TIMEOUT_SECONDS") or "900")
        proc = subprocess.Popen(
            [sys.executable, "runner.py"],
            cwd=tmpdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + timeout + 30
        while proc.poll() is None:
            if job["cancel"].is_set():
                proc.kill()
                proc.communicate()
                job["state"] = "CANCELLED"
                job["finishedAt"] = _now()
                return
            if time.monotonic() > deadline:
                proc.kill()
                proc.communicate()
                job["state"] = "FAILED"
                job["stateDetails"] = {"code": "TimeoutExceeded", "message": "Job timed out"}
                job["finishedAt"] = _now()
                return
            time.sleep(0.05)

        stdout, stderr = proc.communicate()
        job["runner_stdout"] = stdout
        job["runner_stderr"] = stderr
        key = f"/{env.get('S3_BUCKET', '')}/{env.get('RESEARCHFORGE_RESULT_KEY', '')}"
        if key in self._store.objects:
            with self._lock:
                self.objects[key.lstrip("/")] = self._store.objects[key]
        elif self.job_result_override is not None:
            with self._lock:
                self.objects[key.lstrip("/")] = json.dumps(
                    self.job_result_override
                ).encode("utf-8")

        if proc.returncode == 0:
            job["state"] = "COMPLETED"
        else:
            job["state"] = "FAILED"
            job["stateDetails"] = {
                "code": "ContainerFailed",
                "message": (stderr or "").strip()[-500:] or "runner exited non-zero",
            }
        job["finishedAt"] = _now()


class FakeNebiusChatClient(NebiusClient):
    """NebiusClient stub that returns a canned assistant message.

    The real ``extract_assistant_text`` and the real response parsing are used,
    so only the network call is replaced.
    """

    def __init__(self, content: str) -> None:
        super().__init__(Settings(nebius_api_key="dummy"))
        self._content = content
        self.prompts: list[dict[str, Any]] = []

    async def chat_completion(self, **kwargs) -> dict[str, Any]:
        self.prompts.append(kwargs)
        return {"choices": [{"message": {"content": self._content}}]}
