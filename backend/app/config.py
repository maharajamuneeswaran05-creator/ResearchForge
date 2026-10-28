"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    """Runtime configuration for the ResearchForge backend."""

    nebius_api_key: str = Field(..., min_length=1)
    nebius_base_url: str = "https://integrate.api.nvidia.com/v1/"
    nebius_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    inference_provider: str = "nvidia"
    nvidia_api_key: str = ""
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    request_timeout_seconds: float = 60.0
    tavily_api_key: str = ""
    tavily_max_results: int = 5

    # --- Nebius AI Cloud: Serverless AI (experiment execution) ---
    nebius_project_id: str = ""
    nebius_serverless_base_url: str = "https://api.nebius.cloud"
    nebius_job_image: str = "python:3.12-slim"
    nebius_job_platform: str = ""
    nebius_job_preset: str = ""
    nebius_job_subnet_id: str = ""
    nebius_job_disk_size_bytes: int = 21474836480

    # --- Nebius AI Cloud: Object Storage (experiment result transport) ---
    nebius_results_bucket: str = ""
    nebius_storage_access_key_id: str = ""
    nebius_storage_secret_key: str = ""
    nebius_storage_region: str = ""

    # --- Experiment execution ---
    experiment_timeout_seconds: float = 900.0
    experiment_poll_interval_seconds: float = 5.0
    experiment_demo_mode: bool = False


def _load_env() -> None:
    load_dotenv(BACKEND_ROOT / ".env", override=False)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings from backend/.env and process environment."""
    _load_env()

    nvidia_key = (os.getenv("NVIDIA_API_KEY") or "").strip()
    nebius_key = (os.getenv("NEBIUS_API_KEY") or "").strip()

    if not nvidia_key and not nebius_key:
        raise RuntimeError(
            "Inference API key is missing. Set NVIDIA_API_KEY or NEBIUS_API_KEY "
            "in backend/.env before starting the API."
        )

    # Provider identification:
    # 1. If NVIDIA_API_KEY is supplied, provider is NVIDIA NIM.
    # 2. If NEBIUS_API_KEY starts with 'nvapi-', the key belongs to NVIDIA NIM.
    # 3. Otherwise, key is treated as Nebius Token Factory.
    if nvidia_key:
        provider = "nvidia"
        api_key = nvidia_key
        default_base = "https://integrate.api.nvidia.com/v1/"
    elif nebius_key.startswith("nvapi-"):
        provider = "nvidia"
        api_key = nebius_key
        default_base = "https://integrate.api.nvidia.com/v1/"
    else:
        provider = "nebius"
        api_key = nebius_key
        default_base = "https://api.studio.nebius.ai/v1/"

    base_url = (
        os.getenv("NVIDIA_BASE_URL")
        if provider == "nvidia" and os.getenv("NVIDIA_BASE_URL")
        else (os.getenv("NEBIUS_BASE_URL") or default_base)
    ).rstrip("/") + "/"

    raw_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if raw_origins:
        cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    else:
        cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

    try:
        return Settings(
            nebius_api_key=api_key,
            nebius_base_url=base_url,
            nebius_model=os.getenv("NEBIUS_MODEL")
            or os.getenv("NVIDIA_MODEL")
            or "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            inference_provider=provider,
            nvidia_api_key=nvidia_key or (api_key if provider == "nvidia" else ""),
            cors_allowed_origins=cors_origins,
            request_timeout_seconds=float(
                os.getenv("REQUEST_TIMEOUT_SECONDS") or "60"
            ),
            tavily_api_key=(os.getenv("TAVILY_API_KEY") or "").strip(),
            tavily_max_results=int(os.getenv("TAVILY_MAX_RESULTS") or "5"),
            nebius_project_id=(os.getenv("NEBIUS_PROJECT_ID") or "").strip(),
            nebius_serverless_base_url=(
                os.getenv("NEBIUS_SERVERLESS_BASE_URL") or "https://api.nebius.cloud"
            ).rstrip("/"),
            nebius_job_image=os.getenv("NEBIUS_JOB_IMAGE") or "python:3.12-slim",
            nebius_job_platform=(os.getenv("NEBIUS_JOB_PLATFORM") or "").strip(),
            nebius_job_preset=(os.getenv("NEBIUS_JOB_PRESET") or "").strip(),
            nebius_job_subnet_id=(os.getenv("NEBIUS_JOB_SUBNET_ID") or "").strip(),
            nebius_job_disk_size_bytes=int(
                os.getenv("NEBIUS_JOB_DISK_SIZE_BYTES") or "21474836480"
            ),
            nebius_results_bucket=(os.getenv("NEBIUS_RESULTS_BUCKET") or "").strip(),
            nebius_storage_access_key_id=(
                os.getenv("NEBIUS_STORAGE_ACCESS_KEY_ID") or ""
            ).strip(),
            nebius_storage_secret_key=(
                os.getenv("NEBIUS_STORAGE_SECRET_KEY") or ""
            ).strip(),
            nebius_storage_region=(os.getenv("NEBIUS_STORAGE_REGION") or "").strip(),
            experiment_timeout_seconds=float(
                os.getenv("EXPERIMENT_TIMEOUT_SECONDS") or "900"
            ),
            experiment_poll_interval_seconds=float(
                os.getenv("EXPERIMENT_POLL_INTERVAL_SECONDS") or "5"
            ),
            experiment_demo_mode=(
                (os.getenv("EXPERIMENT_DEMO_MODE") or "").strip().lower()
                in ("1", "true", "yes")
            ),
        )
    except ValidationError as exc:
        raise RuntimeError(f"Invalid backend configuration: {exc}") from exc
