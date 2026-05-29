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
        print(f"Loaded .env from {env_path}")


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
        print(f"Frontend directory not found: {FRONTEND_DIR}", file=sys.stderr)
        return 1

    if not TAURI_ENV_SCRIPT.exists():
        print(f"Tauri environment script not found: {TAURI_ENV_SCRIPT}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["GLIMPSE_PYTHON"] = sys.executable

    print("Starting Glimpse Tauri frontend...")
    print("The Tauri shell will start the Python API automatically if needed.")

    completed = subprocess.run(
        ["cmd.exe", "/c", _build_tauri_command()],
        cwd=PROJECT_ROOT,
        env=env,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
