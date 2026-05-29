"""
Glimpse API Server Entry Point
Start the FastAPI server for Tauri frontend communication

Usage:
    python main_api.py [--port PORT] [--host HOST]

Default: http://localhost:8000
"""
import sys
import os
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
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

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
