from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.routes import get_session_manager, router
from app.core.config import get_settings
from app.core.logger import logger
from app.services.session_manager import SessionManager

settings = get_settings()
session_manager = SessionManager(max_concurrent=settings.MAX_CONCURRENT_SESSIONS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifespan Context Manager.
    Handles startup checks and graceful shutdown of all active sessions.
    """
    logger.info("Starting SSB Journey Voice API (FastAPI)...")
    logger.info(f"Environment: {settings.ENVIRONMENT} | Port: {settings.PORT} | Model: {settings.GEMINI_MODEL}")
    logger.info(f"Allowed Origins: {settings.origins_list}")

    yield

    logger.info("Shutting down SSB Journey Voice API...")
    await session_manager.close_all(reason="Server shutting down")
    logger.info("Shutdown complete.")


class PureSecurityHeadersMiddleware:
    """
    High-performance pure ASGI security headers middleware.
    Zero memory buffering, non-blocking, compatible with all ASGI runners.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"x-xss-protection", b"1; mode=block"))
                headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


def create_application() -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    app = FastAPI(
        title="SSB Journey Voice Guide API",
        description="High-performance real-time conversational voice assistant microservice for SSB Journey.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. CORS Configuration
    allow_all = "*" in settings.origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else settings.origins_list,
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Pure ASGI Security Headers Middleware
    app.add_middleware(PureSecurityHeadersMiddleware)

    # 3. Dependency Overrides
    app.dependency_overrides[get_session_manager] = lambda: session_manager

    # 4. Attach Routers
    app.include_router(router)

    return app


app = create_application()
