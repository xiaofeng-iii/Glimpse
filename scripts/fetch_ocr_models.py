"""Fetch the PP-OCRv5-mobile ONNX models used by the local OCR engine.

The desktop runtime never downloads models. This script runs at build time
(and can be run manually for development), verifies SHA256, and leaves the
verified files under ``assets/ocr``.
"""
from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = PROJECT_ROOT / "assets" / "ocr"

MODELS = {
    "ch_PP-OCRv5_det_mobile.onnx": {
        "url": (
            "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
            "onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx"
        ),
        "sha256": "4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae",
    },
    "ch_PP-OCRv5_rec_mobile.onnx": {
        "url": (
            "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
            "onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx"
        ),
        "sha256": "5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_ocr_models(model_dir: Path = DEFAULT_MODEL_DIR) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    for filename, spec in MODELS.items():
        target = model_dir / filename
        if target.is_file() and sha256_file(target) == spec["sha256"]:
            continue

        print(f"[ocr] downloading {filename}")
        temporary = target.with_suffix(target.suffix + ".part")
        request = urllib.request.Request(
            spec["url"],
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                with temporary.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
            actual = sha256_file(temporary)
            if actual != spec["sha256"]:
                raise RuntimeError(
                    f"SHA256 mismatch for {filename}: expected {spec['sha256']}, got {actual}"
                )
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        print(f"[ocr] verified {filename}")


if __name__ == "__main__":
    ensure_ocr_models()
