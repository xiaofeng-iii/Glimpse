"""
Runtime environment helpers for source and packaged desktop modes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_runtime_root(default: Path) -> Path:
    override = os.environ.get("GLIMPSE_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return default.resolve()


def get_data_root(project_root: Path) -> Path:
    override = os.environ.get("GLIMPSE_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    if is_frozen():
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data).resolve() / "Glimpse" / "GlimpseData"

    return project_root / "GlimpseData"


def get_env_file(project_root: Path) -> Path:
    override = os.environ.get("GLIMPSE_ENV_FILE")
    if override:
        return Path(override).expanduser().resolve()

    if is_frozen():
        data_env = get_data_root(project_root) / ".env"
        if data_env.exists():
            return data_env

    return project_root / ".env"
