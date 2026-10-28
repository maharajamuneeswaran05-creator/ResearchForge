"""ResearchForge diagnostic script: test inference connection via httpx.

This script tests the configured inference provider (NVIDIA NIM or Nebius Token Factory)
using the installed httpx client and settings from backend/.env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Locate backend root and load .env
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
load_dotenv(BACKEND_DIR / ".env")

NVIDIA_KEY = (os.getenv("NVIDIA_API_KEY") or "").strip()
NEBIUS_KEY = (os.getenv("NEBIUS_API_KEY") or "").strip()

if NVIDIA_KEY:
    PROVIDER = "nvidia"
    API_KEY = NVIDIA_KEY
    DEFAULT_BASE = "https://integrate.api.nvidia.com/v1/"
elif NEBIUS_KEY.startswith("nvapi-"):
    PROVIDER = "nvidia"
    API_KEY = NEBIUS_KEY
    DEFAULT_BASE = "https://integrate.api.nvidia.com/v1/"
elif NEBIUS_KEY:
    PROVIDER = "nebius"
    API_KEY = NEBIUS_KEY
    DEFAULT_BASE = "https://api.studio.nebius.ai/v1/"
else:
    print("ERROR: Neither NVIDIA_API_KEY nor NEBIUS_API_KEY found in backend/.env", file=sys.stderr)
    sys.exit(1)

BASE_URL = (
    os.getenv("NVIDIA_BASE_URL")
    if PROVIDER == "nvidia" and os.getenv("NVIDIA_BASE_URL")
    else (os.getenv("NEBIUS_BASE_URL") or DEFAULT_BASE)
).rstrip("/") + "/"

MODEL = (
    os.getenv("NEBIUS_MODEL")
    or os.getenv("NVIDIA_MODEL")
    or "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
)


def main() -> None:
    masked_key = f"{API_KEY[:6]}...{API_KEY[-4:]}" if len(API_KEY) > 10 else "***"
    print(f"Provider:  {PROVIDER}")
    print(f"Base URL:  {BASE_URL}")
    print(f"Model:     {MODEL}")
    print(f"API Key:   {masked_key}")
    print("-" * 50)
    print("Sending ping request to chat/completions...")

    url = f"{BASE_URL}chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a concise AI research assistant."},
            {"role": "user", "content": "Reply with exactly: 'ResearchForge inference online'"},
        ],
        "max_tokens": 64,
        "temperature": 0.1,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
    except Exception as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"HTTP Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response: {response.text[:500]}", file=sys.stderr)
        sys.exit(3)

    data = response.json()
    try:
        content = data["choices"][0]["message"].get("content")
        if not content:
            content = data["choices"][0]["message"].get("reasoning_content")
        print(f"Response:    {str(content).strip()}")
        print("-" * 50)
        print("Inference test SUCCESS.")
    except Exception as exc:
        print(f"Failed to parse response: {exc}", file=sys.stderr)
        print(f"Raw data: {data}")
        sys.exit(4)


if __name__ == "__main__":
    main()