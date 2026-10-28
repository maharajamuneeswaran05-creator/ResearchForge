"""Tests for Tavily evidence collection and normalization."""

from __future__ import annotations

import os
import pytest
import httpx


from app.config import Settings
from app.main import app
from app.services.tavily import TavilyClient, TavilyError


def test_normalize_url():
    assert TavilyClient._normalize_url("https://www.Example.com/path/") == "https://example.com/path"
    assert TavilyClient._normalize_url("https://example.com/path") == "https://example.com/path"


def test_evidence_deduplication():
    settings = Settings(
        nebius_api_key="dummy",
        tavily_api_key="test-key",
    )
    client = TavilyClient(settings)
    raw = [
        {"url": "https://www.arxiv.org/abs/2301.0001/", "title": "Paper A", "snippet": "Text A"},
        {"url": "https://arxiv.org/abs/2301.0001", "title": "Paper A Dupe", "snippet": "Text A Dupe"},
        {"url": "https://nature.com/article/1", "title": "Paper B", "snippet": "Text B"},
    ]
    evidence = client._to_evidence(raw)
    assert len(evidence) == 2
    assert evidence[0]["title"] == "Paper A"
    assert evidence[1]["title"] == "Paper B"


def test_missing_tavily_key():
    settings = Settings(
        nebius_api_key="dummy",
        tavily_api_key="",
    )
    client = TavilyClient(settings)
    with pytest.raises(TavilyError) as exc_info:
        import asyncio
        asyncio.run(client.search("test query"))
    assert "TAVILY_API_KEY is missing" in str(exc_info.value)


def test_empty_query_rejected():
    settings = Settings(
        nebius_api_key="dummy",
        tavily_api_key="test-key",
    )
    client = TavilyClient(settings)
    with pytest.raises(TavilyError) as exc_info:
        import asyncio
        asyncio.run(client.search("   "))
    assert "Search query must not be empty" in str(exc_info.value)


@pytest.mark.asyncio
async def test_evidence_endpoint_validation():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/research/evidence",
                json={"research_question": "   ", "max_results": 3},
            )
            assert resp.status_code == 422


@pytest.mark.asyncio
async def test_live_or_mocked_evidence():
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        pytest.skip("TAVILY_API_KEY not configured in environment")

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/research/evidence",
                json={
                    "research_question": "Can explanation consistency improve hallucination detection?",
                    "max_results": 2,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "evidence" in data
            assert len(data["evidence"]) > 0
            assert "url" in data["evidence"][0]
