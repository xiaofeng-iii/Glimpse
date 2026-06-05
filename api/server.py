"""
API Server - FastAPI application entry point
Serves REST API and WebSocket endpoints for Tauri frontend
"""
import os
import secrets

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio

from api.routes import memories, search, screenshot, settings, cluster, images
from api.desktop_actions import setup_cluster_processing
from api.hotkeys import setup_global_hotkeys, shutdown_global_hotkeys
from api.websocket import websocket_endpoint, setup_signal_forwarding, manager
from container import container
from services.bootstrap import configure_ai_client

APP_VERSION = "1.0.0"
AUTH_HEADER = "X-Glimpse-Auth"
AUTH_QUERY_PARAM = "auth_token"


def configured_auth_token() -> str:
    return os.environ.get("GLIMPSE_AUTH_TOKEN", "").strip()


def auth_token_is_valid(candidate: str | None) -> bool:
    expected = configured_auth_token()
    if not expected:
        return True
    return bool(candidate) and secrets.compare_digest(candidate, expected)


def request_is_authorized(request: Request) -> bool:
    return auth_token_is_valid(
        request.headers.get(AUTH_HEADER)
        or request.query_params.get(AUTH_QUERY_PARAM)
    )


def websocket_is_authorized(websocket: WebSocket) -> bool:
    return auth_token_is_valid(
        websocket.headers.get(AUTH_HEADER)
        or websocket.query_params.get(AUTH_QUERY_PARAM)
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup: Initialize container and services
    print("Starting Glimpse API Server...")
    container.initialize_defaults()
    configure_ai_client(container.get("ai_client"), container.get("settings_manager"))

    # Initialize signal forwarding for WebSocket
    loop = asyncio.get_running_loop()
    setup_signal_forwarding(loop)
    setup_cluster_processing(loop)
    setup_global_hotkeys(loop)

    print("API Server ready!")

    yield

    # Shutdown: Clean up resources
    print("Shutting down API Server...")
    shutdown_global_hotkeys()
    container.shutdown()


app = FastAPI(
    title="Glimpse API",
    description="AI-powered desktop memory retrieval system API",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware for Tauri frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_local_auth(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path.startswith("/api/") and not request_is_authorized(request):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid Glimpse backend auth token"},
        )

    return await call_next(request)


# Include routers
app.include_router(memories.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(screenshot.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(cluster.router, prefix="/api")
app.include_router(images.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint - API info"""
    return {
        "name": "Glimpse API",
        "version": APP_VERSION,
        "docs": "/docs",
        "websocket": "/ws/events",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": "Glimpse",
        "role": "backend",
        "version": APP_VERSION,
        "pid": os.getpid(),
        "container_initialized": container.has("memory_service"),
    }


@app.websocket("/ws/events")
async def websocket_handler(websocket: WebSocket):
    """WebSocket endpoint for real-time events"""
    if not websocket_is_authorized(websocket):
        await websocket.close(code=1008)
        return
    await websocket_endpoint(websocket)


# Additional endpoint for quick status
@app.get("/api/stats")
async def get_stats():
    """Get application statistics"""
    try:
        sqlite_manager = container.get("sqlite_manager")
        chroma_manager = container.get("chroma_manager")

        sqlite_count = sqlite_manager.get_memories_count()
        chroma_count = chroma_manager.get_memory_count()

        return {
            "sqlite_count": sqlite_count,
            "chroma_count": chroma_count,
            "synced": sqlite_count == chroma_count,
        }
    except Exception as e:
        return {"error": str(e)}
