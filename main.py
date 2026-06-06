"""
Glimpse source launcher.

The default desktop UI is the Vue + Tauri frontend. The old PySide6
interface is kept in main_legacy_qt.py for fallback/debugging.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parent.resolve()
FRONTEND_DIR = PROJECT_ROOT / "glimpse-frontend"
TAURI_ENV_SCRIPT = PROJECT_ROOT / "scripts" / "setup_tauri_env.bat"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded .env from %s", env_path)


def _build_tauri_command() -> str:
    return (
        f'cd /d "{PROJECT_ROOT}" '
        f'&& call "{TAURI_ENV_SCRIPT}" '
        f'&& cd /d "{FRONTEND_DIR}" '
        "&& npm.cmd run tauri:dev -- --config tauri.dev.conf.json"
    )


def main() -> int:
    _load_dotenv()

    if not FRONTEND_DIR.exists():
        logger.error("Frontend directory not found: %s", FRONTEND_DIR)
        return 1

    if not TAURI_ENV_SCRIPT.exists():
        logger.error("Tauri environment script not found: %s", TAURI_ENV_SCRIPT)
        return 1

    env = os.environ.copy()
    env["GLIMPSE_PYTHON"] = sys.executable

    logger.info("Starting Glimpse Tauri frontend...")
    logger.info("The Tauri shell will start the Python API automatically if needed.")

    completed = subprocess.run(
        _build_tauri_command(),
        shell=True,
        cwd=PROJECT_ROOT,
        env=env,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
