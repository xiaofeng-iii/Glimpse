"""
Glimpse API Server Entry Point
Start the FastAPI server for Tauri frontend communication

Usage:
    python main_api.py [--port PORT] [--host HOST]

Default: http://localhost:8000
"""
import sys
import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import argparse
from pathlib import Path
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
        print(f"Loaded .env from {env_path}")
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

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                    Glimpse API Server                      ║
║                                                            ║
║  REST API:  http://{args.host}:{args.port}/api/                  ║
║  WebSocket: ws://{args.host}:{args.port}/ws/events             ║
║  Docs:      http://{args.host}:{args.port}/docs                 ║
║                                                            ║
╚═══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
