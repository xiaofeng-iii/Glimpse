"""
API Server - FastAPI application entry point
Serves REST API and WebSocket endpoints for Tauri frontend
"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from api.routes import memories, search, screenshot, settings, cluster, images
from api.desktop_actions import setup_cluster_processing
from api.hotkeys import setup_global_hotkeys, shutdown_global_hotkeys
from api.websocket import websocket_endpoint, setup_signal_forwarding, manager
from container import container
from services.bootstrap import configure_ai_client


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
    version="1.0.0",
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
        "version": "1.0.0",
        "docs": "/docs",
        "websocket": "/ws/events",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "container_initialized": container.has("memory_service")}


@app.websocket("/ws/events")
async def websocket_handler(websocket: WebSocket):
    """WebSocket endpoint for real-time events"""
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
