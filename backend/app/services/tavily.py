"""Tavily search client for research evidence collection."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyError(Exception):
    """Raised when a Tavily API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TavilyClient:
    """Thin httpx wrapper around Tavily Search."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.tavily_api_key
        self._max_results = settings.tavily_max_results
        self._timeout = settings.request_timeout_seconds

    async def search(self, query: str, *, max_results: int | None = None) -> list[dict[str, str]]:
        """Search Tavily and return structured, deduplicated evidence items."""
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            raise TavilyError("Search query must not be empty.", status_code=422)

        if not self._api_key:
            raise TavilyError(
                "TAVILY_API_KEY is missing. Add it to backend/.env to enable evidence retrieval.",
                status_code=500,
            )

        limit = max_results if max_results is not None else self._max_results
        payload = {
            "query": cleaned_query,
            "search_depth": "basic",
            "max_results": limit,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    TAVILY_SEARCH_URL, headers=headers, json=payload
                )
        except httpx.TimeoutException as exc:
            raise TavilyError(
                f"Tavily request timed out after {self._timeout}s"
            ) from exc
        except httpx.RequestError as exc:
            raise TavilyError(f"Tavily request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text[:500]
            logger.error(
                "Tavily API error status=%s body=%s",
                response.status_code,
                detail,
            )
            raise TavilyError(
                f"Tavily API returned HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
            )

        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise TavilyError("Tavily API returned invalid JSON") from exc

        return self._to_evidence(data.get("results") or [])

    @staticmethod
    def _source_from_url(url: str) -> str:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{netloc}{path}"

    def _to_evidence(self, results: list[Any]) -> list[dict[str, str]]:
        evidence: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("content") or item.get("snippet") or "").strip()
            if not url and not title and not snippet:
                continue

            normalized = self._normalize_url(url) if url else ""
            if normalized and normalized in seen_urls:
                continue
            if normalized:
                seen_urls.add(normalized)

            evidence.append(
                {
                    "title": title or "Untitled",
                    "url": url,
                    "source": self._source_from_url(url),
                    "snippet": snippet,
                }
            )
        return evidence
