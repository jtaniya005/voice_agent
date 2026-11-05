from fastapi import APIRouter, Depends, Query, WebSocket, status
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logger import logger
from app.schemas.events import HealthResponse
from app.services.gemini_live import GeminiLiveService
from app.services.session_manager import SessionManager

router = APIRouter()


def get_session_manager(settings: Settings = Depends(get_settings)) -> SessionManager:
    # Will be overridden in main.py app state or dependency injection
    raise NotImplementedError


@router.get(
    "/healthz",
    response_model=HealthResponse,
    tags=["Monitoring"],
    summary="Liveness and Health Telemetry",
)
async def health_check(
    settings: Settings = Depends(get_settings),
    manager: SessionManager = Depends(get_session_manager),
) -> HealthResponse:
    """Returns application health, active session load, and model status."""
    return HealthResponse(
        status="ok",
        service="ssb-journey-voice-api",
        active_sessions=manager.active_count,
        max_concurrent_sessions=settings.MAX_CONCURRENT_SESSIONS,
        model=settings.GEMINI_MODEL,
        uptime_seconds=manager.uptime_seconds,
    )


@router.get(
    "/readyz",
    tags=["Monitoring"],
    summary="Readiness Probe",
)
async def readiness_check(settings: Settings = Depends(get_settings)):
    """Verifies environment and API key configuration readiness."""
    if not settings.GEMINI_API_KEY:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "error": "GEMINI_API_KEY not configured"},
        )
    return {"status": "ready"}


@router.get("/", tags=["Info"])
async def root_info(settings: Settings = Depends(get_settings)):
    """API root metadata and service information."""
    return {
        "service": "SSB Journey Voice API",
        "portal": "SSB Journey",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "websocket_url": "/live",
        "skills_url": "/skills",
    }


@router.get("/skills", tags=["Skills"])
async def list_skills():
    """Returns available voice skills, their focus areas, and prompt availability."""
    return {
        "portal": "SSB Journey",
        "framework": "LangGraph StateGraph",
        "specialization": "Services Selection Board (SSB) Only",
        "skills": [
            {
                "id": "onboarding",
                "name": "SSB Journey Overview & 5-Day Framework",
                "description": "Comprehensive briefing of SSB Journey portal, 5-day selection stages, and assessor parameters",
            },
            {
                "id": "roadmap",
                "name": "5-Day SSB Roadmap & Stage Details",
                "description": "Guides through Screening (OIR/PPDT), Psych tests (TAT, WAT, SRT, SD), GTO ground tasks, and Interview/Conference",
            },
            {
                "id": "checklist",
                "name": "Pre-Reporting 68-Item Checklist",
                "description": "Validates reporting documents, GTO white attire, formal clothes, stationery, and travel essentials",
            },
            {
                "id": "mock_interview",
                "name": "15 Officer Like Qualities (OLQ) & Interview Details",
                "description": "Detailed breakdown of 15 OLQs in 4 factors and Interviewing Officer parameters",
            },
            {
                "id": "motivation",
                "name": "Defense & Armed Forces Motivation",
                "description": "Provides 20 military quotes and overcomes screening/rejection anxiety",
            },
        ],
    }


@router.websocket("/live")
async def websocket_live_endpoint(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
    manager: SessionManager = Depends(get_session_manager),
):
    """
    Bi-directional voice streaming WebSocket endpoint.
    - Upstream: 16 kHz mono PCM16 binary chunks + JSON control frames.
    - Downstream: 24 kHz mono PCM16 binary chunks + JSON event frames.
    """
    origin = websocket.headers.get("origin")
    if not settings.is_origin_allowed(origin):
        logger.warning(f"Rejected unauthorized WebSocket origin: {origin}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Origin not allowed")
        return

    service = GeminiLiveService(settings=settings, session_manager=manager)
    await service.handle_connection(websocket)

