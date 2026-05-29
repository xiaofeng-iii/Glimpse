"""
Build the Python API backend as a single-file sidecar binary for Tauri.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = PROJECT_ROOT / "main_api.py"
BINARIES_DIR = PROJECT_ROOT / "glimpse-frontend" / "src-tauri" / "binaries"
WORK_ROOT = PROJECT_ROOT / "build" / "backend-sidecar"
PYINSTALLER_BUILD_DIR = WORK_ROOT / "build"
PYINSTALLER_SPEC_DIR = WORK_ROOT / "spec"


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


def main() -> int:
    build_name = f"python-backend-{target_triple()}"
    separator = resource_separator()

    try:
        import PyInstaller.__main__
    except ImportError as exc:
        print("PyInstaller is not installed. Run: python -m pip install -r requirements-packaging.txt")
        return 1

    hiddenimports, datas, binaries = collect_pyinstaller_resources()

    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(WORK_ROOT, ignore_errors=True)

    args = [
        str(ENTRYPOINT),
        "--noconfirm",
        "--clean",
        "--onefile",
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

    suffix = ".exe" if os.name == "nt" else ""
    output_path = BINARIES_DIR / f"{build_name}{suffix}"
    if not output_path.exists():
        print(f"Expected sidecar output not found: {output_path}")
        return 1

    print(f"Backend sidecar ready: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
