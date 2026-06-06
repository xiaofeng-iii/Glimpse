"""
Glimpse API Server Entry Point
Start the FastAPI server for Tauri frontend communication

Usage:
    python main_api.py [--port PORT] [--host HOST]

Default: http://localhost:8000
"""
import sys
import os
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)


def _packaged_log_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data).resolve() / "Glimpse" / "logs" / "python-backend.log"
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "python-backend.log"
    return Path.cwd() / "python-backend.log"


if sys.stdout is None:
    log_path = _packaged_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
if sys.stderr is None:
    if sys.stdout is not None and getattr(sys.stdout, "name", None) != os.devnull:
        sys.stderr = sys.stdout
    else:
        log_path = _packaged_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sys.stderr = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")

import argparse
from runtime_env import get_env_file, get_runtime_root

# Ensure project root is in path
project_root = get_runtime_root(Path(__file__).parent)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load .env environment variables
try:
    from dotenv import load_dotenv
    env_path = get_env_file(project_root)
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded .env from %s", env_path)
except ImportError:
    pass

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Glimpse API Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--auth-token", type=str, default="", help="Optional local auth token for desktop clients")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()
    if args.auth_token:
        os.environ["GLIMPSE_AUTH_TOKEN"] = args.auth_token
    else:
        os.environ.pop("GLIMPSE_AUTH_TOKEN", None)

    logger.info("""
╔═══════════════════════════════════════════════════════════╗
║                    Glimpse API Server                      ║
║                                                            ║
║  REST API:  http://%s:%s/api/                  ║
║  WebSocket: ws://%s:%s/ws/events             ║
║  Docs:      http://%s:%s/docs                 ║
║                                                            ║
╚═══════════════════════════════════════════════════════════╝
    """, args.host, args.port, args.host, args.port, args.host, args.port)

    uvicorn.run(
        "api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
