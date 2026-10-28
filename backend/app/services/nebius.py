"""Nebius Token Factory client (OpenAI-compatible chat completions)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class NebiusError(Exception):
    """Raised when a Nebius API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NebiusClient:
    """Thin httpx wrapper around Nebius Token Factory chat completions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.nebius_base_url.rstrip("/") + "/"
        self._timeout = settings.request_timeout_seconds

    @property
    def model(self) -> str:
        return self._settings.nebius_model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.nebius_api_key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        *,
        user_message: str,
        system_message: str = "You are a helpful research assistant.",
        max_tokens: int = 256,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request and return the raw JSON body."""
        url = f"{self._base_url}chat/completions"
        payload: dict[str, Any] = {
            "model": self._settings.nebius_model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        retries = 3
        delay = 1.5
        response: httpx.Response | None = None

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        url, headers=self._headers(), json=payload
                    )
            except httpx.TimeoutException as exc:
                if attempt == retries - 1:
                    raise NebiusError(
                        f"Nebius request timed out after {self._timeout}s"
                    ) from exc
                await asyncio.sleep(delay)
                delay *= 2
                continue
            except httpx.RequestError as exc:
                if attempt == retries - 1:
                    raise NebiusError(f"Nebius request failed: {exc}") from exc
                await asyncio.sleep(delay)
                delay *= 2
                continue

            if response.status_code in (429, 503) and attempt < retries - 1:
                logger.warning(
                    "Nebius API returned HTTP %s, retrying in %.1fs (attempt %s/%s)...",
                    response.status_code,
                    delay,
                    attempt + 1,
                    retries,
                )
                await asyncio.sleep(delay)
                delay *= 2
                continue
            break

        if response is None:
            raise NebiusError("No response received from Nebius API")

        if response.status_code >= 400:
            detail = response.text[:500]
            logger.error(
                "Nebius API error status=%s body=%s",
                response.status_code,
                detail,
            )
            raise NebiusError(
                f"Nebius API returned HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise NebiusError("Nebius API returned invalid JSON") from exc

    @staticmethod
    def extract_assistant_text(payload: dict[str, Any]) -> str:
        """Pull the assistant message content from a chat completions response."""
        try:
            choices = payload["choices"]
            message = choices[0]["message"]
            content = message.get("content")
        except (KeyError, IndexError, TypeError) as exc:
            raise NebiusError(
                "Unexpected Nebius response shape: missing assistant content"
            ) from exc

        # Some Nemotron models return final text in content; others only reasoning_content.
        if content is None:
            content = message.get("reasoning_content")

        if content is None:
            raise NebiusError("Nebius response contained empty assistant content")

        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            text = "".join(parts).strip()
        else:
            text = str(content).strip()

        if not text:
            raise NebiusError("Nebius response contained empty assistant content")
        return text

    async def ping(self) -> str:
        """Minimal connectivity check against the configured Nemotron model."""
        data = await self.chat_completion(
            user_message="Reply with exactly: pong",
            system_message="You are a connectivity test. Reply briefly.",
            max_tokens=32,
        )
        return self.extract_assistant_text(data)
