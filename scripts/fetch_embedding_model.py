"""Fetch the bge-small-zh-v1.5 ONNX embedding model and tokenizer.

The desktop runtime never downloads models. This script runs at build time
(and can be run manually for development), verifies SHA256, and leaves the
verified files under ``assets/embedding``. Source: Xenova/bge-small-zh-v1.5
(fp32 export, bit-identical to the previous sentence-transformers pipeline).
"""
from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = PROJECT_ROOT / "assets" / "embedding"

HF_REPO = "Xenova/bge-small-zh-v1.5"

MODELS = {
    "bge-small-zh-v1.5.onnx": {
        "paths": ("onnx/model.onnx",),
        "sha256": "69a0b846f4f116b5e6aabf9546ea6754d02264f3211a13a1bd69b31b8040749a",
    },
    "bge-small-zh-v1.5.tokenizer.json": {
        "paths": ("tokenizer.json",),
        "sha256": "48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26",
    },
}

MIRRORS = (
    "https://hf-mirror.com",
    "https://huggingface.co",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(spec: dict, target: Path) -> None:
    last_error: Exception | None = None
    for mirror in MIRRORS:
        url = f"{mirror}/{HF_REPO}/resolve/main/{spec['paths'][0]}"
        temporary = target.with_suffix(target.suffix + ".part")
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                with temporary.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
            actual = sha256_file(temporary)
            if actual != spec["sha256"]:
                raise RuntimeError(
                    f"SHA256 mismatch for {target.name}: expected {spec['sha256']}, got {actual}"
                )
            temporary.replace(target)
            return
        except Exception as exc:  # noqa: BLE001 - 逐镜像重试
            temporary.unlink(missing_ok=True)
            last_error = exc
    raise RuntimeError(f"Failed to fetch {target.name}: {last_error}")


def ensure_embedding_models(model_dir: Path = DEFAULT_MODEL_DIR) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    for filename, spec in MODELS.items():
        target = model_dir / filename
        if target.is_file() and sha256_file(target) == spec["sha256"]:
            continue
        print(f"[embedding] downloading {filename}")
        _download(spec, target)
        print(f"[embedding] verified {filename}")


if __name__ == "__main__":
    ensure_embedding_models()
