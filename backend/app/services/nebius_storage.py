"""Nebius Object Storage client (S3 compatible).

Nebius AI Cloud exposes Object Storage through the Amazon S3 API
(https://docs.nebius.com/object-storage/interfaces/s3-api-compatibility) at
``https://storage.<region>.nebius.cloud`` and authenticates with AWS Signature
Version 4 using a static access key pair.

The signing helper below is intentionally self contained: its source is injected
into experiment containers so that a job uploads its result document with the
exact same implementation that the backend uses to read it back.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class NebiusStorageError(Exception):
    """Raised when a Nebius Object Storage call fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def sign_s3_request(
    *,
    method: str,
    path: str,
    host: str,
    region: str,
    access_key_id: str,
    secret_key: str,
    payload: bytes = b"",
) -> dict[str, str]:
    """Return AWS SigV4 headers for a Nebius Object Storage request.

    All imports are local on purpose: this function is injected verbatim into
    experiment containers, where it signs the upload of the result document.
    """
    import datetime
    import hashlib
    import hmac

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(payload or b"").hexdigest()

    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        [
            method.upper(),
            path,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    signing_key = _sign(
        _sign(_sign(_sign(("AWS4" + secret_key).encode("utf-8"), date_stamp), region), "s3"),
        "aws4_request",
    )
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return {
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
        "Host": host,
    }


class NebiusObjectStorageClient:
    """Read objects from a Nebius Object Storage bucket."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._timeout = settings.request_timeout_seconds
        self._region = settings.nebius_storage_region
        self._endpoint = (
            f"https://storage.{settings.nebius_storage_region}.nebius.cloud"
            if settings.nebius_storage_region
            else ""
        )

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def region(self) -> str:
        return self._region

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Download an object, returning its raw bytes."""
        if not self._endpoint:
            raise NebiusStorageError(
                "NEBIUS_STORAGE_REGION is not configured, cannot read experiment results",
                status_code=500,
            )

        path = f"/{bucket}/{quote(key, safe='/')}"
        host = self._endpoint.split("://", 1)[-1]
        headers = sign_s3_request(
            method="GET",
            path=path,
            host=host,
            region=self._region,
            access_key_id=self._settings.nebius_storage_access_key_id,
            secret_key=self._settings.nebius_storage_secret_key,
        )

        url = f"{self._endpoint}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise NebiusStorageError(
                f"Nebius Object Storage request timed out after {self._timeout}s"
            ) from exc
        except httpx.RequestError as exc:
            raise NebiusStorageError(
                f"Nebius Object Storage request failed: {exc}"
            ) from exc

        if response.status_code == 404:
            raise NebiusStorageError(
                f"Object not found in bucket {bucket}: {key}", status_code=404
            )
        if response.status_code >= 400:
            detail = response.text[:500]
            logger.error(
                "Nebius Object Storage error status=%s body=%s",
                response.status_code,
                detail,
            )
            raise NebiusStorageError(
                f"Nebius Object Storage returned HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
            )

        return response.content
