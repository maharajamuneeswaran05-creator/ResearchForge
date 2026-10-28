"""Nebius AI Cloud Serverless AI client (REST).

Wraps the ``nebius.ai.v1.JobService`` endpoints documented at
https://docs.nebius.com/rest-api/ai/v1/jobs

  - POST   /ai/v1/jobs            create a job (returns an Operation)
  - GET    /ai/v1/jobs/{id}       read a job
  - GET    /ai/v1/jobs/get-by-name read a job by name
  - POST   /ai/v1/jobs/cancel     cancel a running job
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

# Job states reported by Nebius AI Cloud (nebius.ai.v1.JobStatus.State).
TERMINAL_JOB_STATES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "ERROR"})

# Failure codes documented at https://docs.nebius.com/serverless/lifecycle
TIMEOUT_ERROR_CODE = "TimeoutExceeded"


class NebiusServerlessError(Exception):
    """Raised when a Nebius Serverless AI call fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class NebiusJob:
    """Normalized view of a Nebius Serverless AI job."""

    job_id: str
    name: str
    state: str
    error_code: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_JOB_STATES


class NebiusServerlessClient:
    """Thin httpx wrapper around the Nebius Serverless AI job REST API."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._base_url = settings.nebius_serverless_base_url.rstrip("/")
        self._timeout = settings.request_timeout_seconds
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.nebius_api_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body,
                    params=params,
                )
        except httpx.TimeoutException as exc:
            raise NebiusServerlessError(
                f"Nebius Serverless AI request timed out after {self._timeout}s"
            ) from exc
        except httpx.RequestError as exc:
            raise NebiusServerlessError(
                f"Nebius Serverless AI request failed: {exc}"
            ) from exc

        if response.status_code >= 400:
            detail = response.text[:500]
            logger.error(
                "Nebius Serverless API error status=%s path=%s body=%s",
                response.status_code,
                path,
                detail,
            )
            raise NebiusServerlessError(
                f"Nebius Serverless API returned HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise NebiusServerlessError(
                "Nebius Serverless API returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise NebiusServerlessError(
                "Nebius Serverless API returned an unexpected response shape"
            )
        return payload

    async def create_job(self, *, name: str, spec: dict[str, Any]) -> str:
        """Create a Serverless AI job and return its job id."""
        payload = {
            "metadata": {"parentId": self._settings.nebius_project_id, "name": name},
            "spec": spec,
        }
        data = await self._request("POST", "/ai/v1/jobs", json_body=payload)
        job_id = data.get("resourceId")
        if not job_id:
            raise NebiusServerlessError(
                "Nebius Serverless API did not return a job id (resourceId)"
            )
        logger.info("Nebius Serverless job created name=%s job_id=%s", name, job_id)
        return str(job_id)

    async def get_job(self, job_id: str) -> NebiusJob:
        """Read the current state of a job."""
        data = await self._request("GET", f"/ai/v1/jobs/{job_id}")
        return _parse_job(job_id, data)

    async def get_job_by_name(self, name: str) -> NebiusJob | None:
        """Read a job by name, returning ``None`` when it does not exist."""
        try:
            data = await self._request(
                "GET",
                "/ai/v1/jobs/get-by-name",
                params={
                    "name": name,
                    "parentId": self._settings.nebius_project_id,
                },
            )
        except NebiusServerlessError as exc:
            if exc.status_code == 404:
                return None
            raise
        return _parse_job("", data)

    async def cancel_job(self, job_id: str) -> None:
        """Cancel a running job."""
        await self._request("POST", "/ai/v1/jobs/cancel", json_body={"id": job_id})
        logger.info("Nebius Serverless job cancelled job_id=%s", job_id)


def _parse_job(job_id: str, data: dict[str, Any]) -> NebiusJob:
    metadata = data.get("metadata") or {}
    status = data.get("status") or {}
    details = status.get("stateDetails") or {}
    return NebiusJob(
        job_id=str(metadata.get("id") or job_id or ""),
        name=str(metadata.get("name") or ""),
        state=str(status.get("state") or "STATE_UNSPECIFIED"),
        error_code=details.get("code"),
        error_message=details.get("message"),
        created_at=metadata.get("createdAt"),
        started_at=status.get("startedAt"),
        finished_at=status.get("finishedAt"),
    )
