"""HTTP routes for health, Nebius checks, and evidence collection."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.research import (
    EvidenceItem,
    EvidenceRequest,
    EvidenceResponse,
    ExperimentCodeRequest,
    ExperimentCodeResponse,
    ExperimentExecuteRequest,
    ExperimentExecutionResult,
    ExperimentJobResponse,
    ExperimentPlanRequest,
    ExperimentPlanResponse,
    HealthResponse,
    NebiusTestResponse,
    ResearchCriticRequest,
    ResearchCriticResponse,
    ResearchGapRequest,
    ResearchGapResponse,
    ResearchReportRequest,
    ResearchReportResponse,
    ResearchTestRequest,
    ResearchTestResponse,
)
from app.services.experiment_code import ExperimentCodeError, ExperimentCodeService
from app.services.experiment_execution import (
    ExperimentExecutionError,
    ExperimentExecutionService,
    NebiusConfigurationError,
)
from app.services.experiment_plan import ExperimentPlanError, ExperimentPlanService
from app.services.nebius import NebiusError
from app.services.research_critic import ResearchCriticError, ResearchCriticService
from app.services.research_gap import ResearchGapError, ResearchGapService
from app.services.research_report import ResearchReportError, ResearchReportService
from app.services.tavily import TavilyError

logger = logging.getLogger(__name__)

router = APIRouter()


def _http_error_from_nebius(exc: NebiusError) -> HTTPException:
    if exc.status_code == 401:
        status = 401
    elif exc.status_code == 404:
        status = 404
    else:
        status = 502
    return HTTPException(status_code=status, detail=str(exc))


def _http_error_from_tavily(exc: TavilyError) -> HTTPException:
    if exc.status_code in (401, 403):
        status = 401
    elif exc.status_code == 429:
        status = 429
    elif exc.status_code == 500 and "TAVILY_API_KEY" in str(exc):
        status = 500
    else:
        status = 502
    return HTTPException(status_code=status, detail=str(exc))


def _http_error_from_execution(exc: ExperimentExecutionError) -> HTTPException:
    if isinstance(exc, NebiusConfigurationError):
        return HTTPException(
            status_code=503,
            detail={
                "error": "NebiusExecutionNotConfigured",
                "message": str(exc),
                "missing_variables": exc.missing,
            },
        )
    status = exc.status_code or 500
    return HTTPException(status_code=status, detail=str(exc))


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness check - does not call external services."""
    return HealthResponse(status="ok", service="researchforge-backend")


@router.get("/test/nebius", response_model=NebiusTestResponse)
async def test_nebius(request: Request) -> NebiusTestResponse:
    """Send a short prompt to the configured Nemotron model."""
    client = request.app.state.nebius_client

    try:
        reply = await client.ping()
    except NebiusError as exc:
        logger.exception("Nebius connectivity test failed")
        raise _http_error_from_nebius(exc) from exc
    except Exception as exc:
        logger.exception("Unexpected error during Nebius test")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc

    return NebiusTestResponse(ok=True, model=client.model, reply=reply)


@router.post("/api/research/test", response_model=ResearchTestResponse)
async def research_test(
    body: ResearchTestRequest,
    request: Request,
) -> ResearchTestResponse:
    """Send a research question to the configured Nemotron model."""
    client = request.app.state.nebius_client
    question = body.research_question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="research_question must not be empty")

    try:
        payload = await client.chat_completion(
            user_message=question,
            system_message=(
                "You are a research assistant. Answer the research question clearly "
                "and concisely based on general scientific knowledge."
            ),
            max_tokens=512,
        )
        reply = client.extract_assistant_text(payload)
    except NebiusError as exc:
        logger.exception("Research test call to Nebius failed")
        raise _http_error_from_nebius(exc) from exc
    except Exception as exc:
        logger.exception("Unexpected error during research test")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc

    return ResearchTestResponse(
        research_question=question,
        model=client.model,
        response=reply,
    )


@router.post("/api/research/evidence", response_model=EvidenceResponse)
async def research_evidence(
    body: EvidenceRequest,
    request: Request,
) -> EvidenceResponse:
    """Collect structured web evidence for a research question via Tavily."""
    client = request.app.state.tavily_client
    question = body.research_question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="research_question must not be empty")

    try:
        items = await client.search(question, max_results=body.max_results)
    except TavilyError as exc:
        logger.exception("Tavily evidence search failed")
        raise _http_error_from_tavily(exc) from exc
    except Exception as exc:
        logger.exception("Unexpected error during evidence search")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc

    evidence = [EvidenceItem(**item) for item in items]
    return EvidenceResponse(
        research_question=question,
        evidence=evidence,
        count=len(evidence),
    )


@router.post("/api/research/gap", response_model=ResearchGapResponse)
async def research_gap(
    body: ResearchGapRequest,
    request: Request,
) -> ResearchGapResponse:
    """Analyze collected evidence using Nemotron to identify research gaps."""
    service: ResearchGapService = request.app.state.research_gap_service
    question = body.research_question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="research_question must not be empty")

    try:
        return await service.analyze(
            question=question,
            max_results=body.max_results,
            evidence=body.evidence,
        )
    except ResearchGapError as exc:
        logger.exception("Research gap analysis failed")
        status = exc.status_code or 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during research gap analysis")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc


@router.post("/api/research/experiment-plan", response_model=ExperimentPlanResponse)
async def research_experiment_plan(
    body: ExperimentPlanRequest,
    request: Request,
) -> ExperimentPlanResponse:
    """Generate hypothesis and experiment plan from a structured research gap."""
    service: ExperimentPlanService = request.app.state.experiment_plan_service

    try:
        return await service.plan(body.research_gap)
    except ExperimentPlanError as exc:
        logger.exception("Experiment planning failed")
        status = exc.status_code or 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during experiment planning")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc


@router.post("/api/research/experiment-code", response_model=ExperimentCodeResponse)
async def research_experiment_code(
    body: ExperimentCodeRequest,
    request: Request,
) -> ExperimentCodeResponse:
    """Generate a runnable Python experiment script from a validated plan (no execution)."""
    service: ExperimentCodeService = request.app.state.experiment_code_service

    try:
        return await service.generate(body.experiment_plan)
    except ExperimentCodeError as exc:
        logger.exception("Experiment code generation failed")
        status = exc.status_code or 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during experiment code generation")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc


@router.post(
    "/api/research/experiment-execute",
    response_model=ExperimentExecutionResult,
)
async def research_experiment_execute(
    body: ExperimentExecuteRequest,
    request: Request,
) -> ExperimentExecutionResult:
    """Execute generated experiment code on Nebius Serverless AI."""
    service: ExperimentExecutionService = request.app.state.experiment_execution_service

    try:
        if body.wait:
            return await service.execute(
                body.experiment_code,
                timeout_seconds=body.timeout_seconds,
                demo=body.demo,
            )
        submitted = await service.submit(
            body.experiment_code,
            timeout_seconds=body.timeout_seconds,
            demo=body.demo,
        )
        return ExperimentExecutionResult(
            job_id=submitted.job_id,
            status=submitted.status,
            error=submitted.error,
            research_question=submitted.research_question,
            is_demo=submitted.is_demo,
        )
    except NebiusConfigurationError as exc:
        logger.warning("Nebius execution requested but unconfigured: %s", exc)
        raise _http_error_from_execution(exc) from exc
    except ExperimentExecutionError as exc:
        logger.exception("Experiment execution failed")
        raise _http_error_from_execution(exc) from exc
    except Exception as exc:
        logger.exception("Unexpected error during experiment execution")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc


@router.get(
    "/api/research/experiment-jobs/{job_id}",
    response_model=ExperimentJobResponse,
)
async def research_experiment_job(
    job_id: str,
    request: Request,
) -> ExperimentJobResponse:
    """Return the status (and result, when finished) of an experiment job."""
    service: ExperimentExecutionService = request.app.state.experiment_execution_service

    try:
        return await service.get_job(job_id)
    except NebiusConfigurationError as exc:
        raise _http_error_from_execution(exc) from exc
    except ExperimentExecutionError as exc:
        logger.exception("Experiment job status lookup failed")
        raise _http_error_from_execution(exc) from exc
    except Exception as exc:
        logger.exception("Unexpected error during experiment job status lookup")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc


@router.post("/api/research/critic", response_model=ResearchCriticResponse)
async def research_critic(
    body: ResearchCriticRequest,
    request: Request,
) -> ResearchCriticResponse:
    """Critically evaluate the research with Nemotron acting as a skeptical reviewer."""
    service: ResearchCriticService = request.app.state.research_critic_service

    try:
        return await service.critique(body)
    except ResearchCriticError as exc:
        logger.exception("Research critique failed")
        status = exc.status_code or 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during research critique")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc


@router.post("/api/research/report", response_model=ResearchReportResponse)
async def research_report(
    body: ResearchReportRequest,
    request: Request,
) -> ResearchReportResponse:
    """Generate the final structured research report with Nemotron."""
    service: ResearchReportService = request.app.state.research_report_service

    try:
        return await service.generate(body)
    except ResearchReportError as exc:
        logger.exception("Research report generation failed")
        status = exc.status_code or 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during research report generation")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        ) from exc

