"""ResearchForge FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.services.nebius import NebiusClient
from app.services.experiment_code import ExperimentCodeService
from app.services.experiment_execution import ExperimentExecutionService
from app.services.experiment_plan import ExperimentPlanService
from app.services.research_critic import ResearchCriticService
from app.services.research_gap import ResearchGapService
from app.services.research_report import ResearchReportService
from app.services.tavily import TavilyClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.nebius_client = NebiusClient(settings)
    app.state.tavily_client = TavilyClient(settings)
    app.state.research_gap_service = ResearchGapService(
        nebius_client=app.state.nebius_client,
        tavily_client=app.state.tavily_client,
    )
    app.state.experiment_plan_service = ExperimentPlanService(
        nebius_client=app.state.nebius_client,
    )
    app.state.experiment_code_service = ExperimentCodeService(
        nebius_client=app.state.nebius_client,
    )
    app.state.experiment_execution_service = ExperimentExecutionService(settings)
    app.state.research_critic_service = ResearchCriticService(
        nebius_client=app.state.nebius_client,
    )
    app.state.research_report_service = ResearchReportService(
        nebius_client=app.state.nebius_client,
    )
    logger.info(
        "ResearchForge backend ready (provider=%s model=%s tavily_max_results=%s)",
        settings.inference_provider,
        settings.nebius_model,
        settings.tavily_max_results,
    )
    yield


app = FastAPI(
    title="ResearchForge API",
    description="Autonomous AI research assistant backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
settings_for_cors = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_for_cors.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add defensive security headers to all responses."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(router)

