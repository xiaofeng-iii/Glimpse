"""
Runtime environment helpers for source and packaged desktop modes.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


_CARGO_VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"$')


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _read_cargo_package_version(manifest_path: Path) -> str | None:
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    in_package_section = False
    for raw_line in lines:
        line = raw_line.split("#", 1)[0].strip()
        if line.startswith("[") and line.endswith("]"):
            in_package_section = line == "[package]"
            continue
        if not in_package_section:
            continue

        match = _CARGO_VERSION_PATTERN.fullmatch(line)
        if match:
            return match.group(1)

    return None


def get_app_version(project_root: Path) -> str:
    override = os.environ.get("GLIMPSE_APP_VERSION", "").strip()
    if override:
        return override

    if not is_frozen():
        manifest_path = project_root / "glimpse-frontend" / "src-tauri" / "Cargo.toml"
        version = _read_cargo_package_version(manifest_path)
        if version:
            return version

    return "development"


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
