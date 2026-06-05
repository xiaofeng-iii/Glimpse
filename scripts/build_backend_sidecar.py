"""
Build the Python API backend as a single-file sidecar binary for Tauri.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = PROJECT_ROOT / "main_api.py"
BINARIES_DIR = PROJECT_ROOT / "glimpse-frontend" / "src-tauri" / "binaries"
WORK_ROOT = PROJECT_ROOT / "build" / "backend-sidecar"
PYINSTALLER_BUILD_DIR = WORK_ROOT / "build"
PYINSTALLER_SPEC_DIR = WORK_ROOT / "spec"
STAMP_FILE = WORK_ROOT / "backend-build-stamp.json"
BUILD_NAME = "python-backend"

HASH_INPUTS = [
    "main_api.py",
    "api",
    "config",
    "core",
    "db",
    "services",
    "async_runtime.py",
    "container.py",
    "event_bus.py",
    "runtime_env.py",
    "requirements*.txt",
    "scripts/build_backend_sidecar.py",
]

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

EXCLUDED_FILE_PATTERNS = {
    "*.pyc",
    "*.pyo",
}


def target_triple() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()

    arch_map = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }

    arch = arch_map.get(machine)
    if arch is None:
        raise RuntimeError(f"Unsupported architecture for sidecar build: {machine}")

    if system == "windows":
        return f"{arch}-pc-windows-msvc"
    if system == "darwin":
        return f"{arch}-apple-darwin"
    if system == "linux":
        return f"{arch}-unknown-linux-gnu"

    raise RuntimeError(f"Unsupported operating system for sidecar build: {system}")


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def resource_separator() -> str:
    return ";" if os.name == "nt" else ":"


def sidecar_output_dir(build_name: str = BUILD_NAME) -> Path:
    return BINARIES_DIR / build_name


def sidecar_exe_path(build_name: str = BUILD_NAME) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return sidecar_output_dir(build_name) / f"{build_name}{suffix}"


def path_is_excluded(path: Path) -> bool:
    if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
        return True
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in EXCLUDED_FILE_PATTERNS)


def expand_hash_inputs() -> list[Path]:
    files: set[Path] = set()
    for item in HASH_INPUTS:
        if "*" in item:
            matches = PROJECT_ROOT.glob(item)
            for match in matches:
                if match.is_file() and not path_is_excluded(match):
                    files.add(match)
            continue

        path = PROJECT_ROOT / item
        if path.is_file() and not path_is_excluded(path):
            files.add(path)
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and not path_is_excluded(child):
                    files.add(child)

    return sorted(files, key=lambda file: file.relative_to(PROJECT_ROOT).as_posix())


def compute_backend_hash() -> str:
    digest = hashlib.sha256()
    for path in expand_hash_inputs():
        relative_path = path.relative_to(PROJECT_ROOT).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def read_stamp() -> dict[str, object] | None:
    try:
        return json.loads(STAMP_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_stamp(build_hash: str, build_name: str) -> None:
    STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = {
        "hash": build_hash,
        "build_name": build_name,
        "target_triple": target_triple(),
        "entrypoint": ENTRYPOINT.relative_to(PROJECT_ROOT).as_posix(),
        "output_exe": sidecar_exe_path(build_name).relative_to(PROJECT_ROOT).as_posix(),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    STAMP_FILE.write_text(
        json.dumps(stamp, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sidecar_is_current(build_hash: str, build_name: str) -> bool:
    output_exe = sidecar_exe_path(build_name)
    if not output_exe.exists():
        return False

    stamp = read_stamp()
    if not stamp:
        return False

    return (
        stamp.get("hash") == build_hash
        and stamp.get("build_name") == build_name
        and stamp.get("target_triple") == target_triple()
    )


def collect_pyinstaller_resources() -> tuple[list[str], list[tuple[str, str]], list[tuple[str, str]]]:
    try:
        from PyInstaller.utils.hooks import (
            collect_data_files,
            collect_dynamic_libs,
            collect_submodules,
            copy_metadata,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PyInstaller is not installed. Run: python -m pip install -r requirements-packaging.txt"
        ) from exc

    hiddenimports = [
        "api.server",
        "api.dependencies",
        "api.desktop_actions",
        "api.hotkeys",
        "api.schemas",
        "api.websocket",
        "api.routes.cluster",
        "api.routes.images",
        "api.routes.memories",
        "api.routes.search",
        "api.routes.screenshot",
        "api.routes.settings",
        "config.path_manager",
        "config.settings_manager",
        "core.capture",
        "core.cluster_buffer",
        "core.task_queue",
        "db.chroma_manager",
        "db.sqlite_manager",
        "services.ai_client",
        "services.bootstrap",
        "services.embedding_client",
        "services.keyboard_manager",
        "services.memory_service",
        "services.ocr_engine",
        "services.search_service",
        "async_runtime",
        "container",
        "event_bus",
        "runtime_env",
    ]

    dynamic_packages = [
        "uvicorn",
        "fastapi",
        "starlette",
        "pydantic",
        "websockets",
        "openai",
        "pynput",
        "mss",
        "PIL",
        "chromadb",
        "onnxruntime",
        "rapidocr_onnxruntime",
        "sentence_transformers",
        "transformers",
        "tokenizers",
        "huggingface_hub",
    ]

    data_packages = [
        "certifi",
        "chromadb",
        "onnxruntime",
        "rapidocr_onnxruntime",
        "sentence_transformers",
        "transformers",
        "tokenizers",
        "huggingface_hub",
    ]

    metadata_packages = [
        "chromadb",
        "sentence-transformers",
        "transformers",
        "tokenizers",
        "huggingface-hub",
        "openai",
        "fastapi",
        "uvicorn",
        "rapidocr-onnxruntime",
        "onnxruntime",
    ]

    datas: list[tuple[str, str]] = []
    binaries: list[tuple[str, str]] = []

    for package in dynamic_packages:
        try:
            hiddenimports.extend(collect_submodules(package))
        except Exception as exc:
            print(f"[warn] Unable to collect submodules for {package}: {exc}")

    for package in data_packages:
        try:
            datas.extend(collect_data_files(package))
        except Exception as exc:
            print(f"[warn] Unable to collect data files for {package}: {exc}")
        try:
            binaries.extend(collect_dynamic_libs(package))
        except Exception as exc:
            print(f"[warn] Unable to collect dynamic libs for {package}: {exc}")

    for package in metadata_packages:
        try:
            datas.extend(copy_metadata(package))
        except Exception as exc:
            print(f"[warn] Unable to copy package metadata for {package}: {exc}")

    return dedupe(hiddenimports), datas, binaries


def packaging_python_candidates() -> list[Path]:
    candidates: list[Path] = []
    for env_var in ("GLIMPSE_PACKAGING_PYTHON", "GLIMPSE_PYTHON"):
        value = os.environ.get(env_var)
        if value:
            candidates.append(Path(value))

    candidates.extend(
        [
            Path.home() / ".conda" / "envs" / "glimpse" / ("python.exe" if os.name == "nt" else "bin/python"),
            PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
        ]
    )
    return candidates


def reexec_with_packaging_python() -> int | None:
    current = Path(sys.executable).resolve()
    for candidate in packaging_python_candidates():
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        if resolved == current:
            continue

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        print(f"Retrying backend sidecar build with packaging Python: {resolved}")
        completed = subprocess.run([str(resolved), str(Path(__file__).resolve()), *sys.argv[1:]], env=env)
        return completed.returncode

    return None


def build_backend_sidecar(build_name: str, build_hash: str) -> int:
    separator = resource_separator()

    try:
        import PyInstaller.__main__
    except ImportError as exc:
        reexec_result = reexec_with_packaging_python()
        if reexec_result is not None:
            return reexec_result
        print("PyInstaller is not installed. Run: python -m pip install -r requirements-packaging.txt")
        return 1

    hiddenimports, datas, binaries = collect_pyinstaller_resources()

    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(PYINSTALLER_BUILD_DIR, ignore_errors=True)
    shutil.rmtree(PYINSTALLER_SPEC_DIR, ignore_errors=True)
    shutil.rmtree(sidecar_output_dir(build_name), ignore_errors=True)

    args = [
        str(ENTRYPOINT),
        "--noconfirm",
        "--clean",
        "--onedir",
        "--noconsole",
        f"--name={build_name}",
        f"--distpath={BINARIES_DIR}",
        f"--workpath={PYINSTALLER_BUILD_DIR}",
        f"--specpath={PYINSTALLER_SPEC_DIR}",
        f"--paths={PROJECT_ROOT}",
    ]

    for hiddenimport in hiddenimports:
        args.append(f"--hidden-import={hiddenimport}")

    for source, destination in datas:
        args.append(f"--add-data={source}{separator}{destination}")

    for source, destination in binaries:
        args.append(f"--add-binary={source}{separator}{destination}")

    print(f"Building backend sidecar: {build_name}")
    PyInstaller.__main__.run(args)

    onedir_output = sidecar_output_dir(build_name)
    onedir_exe = sidecar_exe_path(build_name)
    if not onedir_exe.exists():
        print(f"Expected sidecar output not found: {onedir_exe}")
        return 1

    write_stamp(build_hash, build_name)
    print(f"Backend sidecar ready: {onedir_output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Glimpse Python backend sidecar")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--if-needed",
        action="store_true",
        help="Rebuild only when backend inputs changed or output is missing",
    )
    mode.add_argument(
        "--force",
        action="store_true",
        help="Force a rebuild even when the stamp is current",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_name = BUILD_NAME
    build_hash = compute_backend_hash()

    if args.if_needed and sidecar_is_current(build_hash, build_name):
        print(f"Backend sidecar is current ({build_hash[:12]}); skipping rebuild.")
        return 0

    if args.if_needed:
        print("Backend sidecar is missing or stale; rebuilding.")
    elif args.force:
        print("Forcing backend sidecar rebuild.")

    return build_backend_sidecar(build_name, build_hash)


if __name__ == "__main__":
    sys.exit(main())
