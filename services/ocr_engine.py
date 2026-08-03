"""
OCR Engine - OCR 抽象类与具体实现
"""
from abc import ABC, abstractmethod
import math
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger


logger = get_logger(__name__)


class OCREngine(ABC):
    """OCR 引擎抽象基类"""

    @abstractmethod
    def extract_text(self, image_path: str) -> Optional[str]:
        pass

    @abstractmethod
    def extract_text_boxes(self, image_path: str) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        pass


class NativeOCREngine(OCREngine):
    """原生 OCR 引擎 (优先使用系统内置能力，不可用时回退到 RapidOCR)"""

    def __init__(self):
        self._available = False
        self._fallback: Optional[OCREngine] = None

    def _get_fallback(self) -> Optional[OCREngine]:
        if self._fallback is None:
            try:
                self._fallback = RapidOCREngine()
            except Exception:
                self._fallback = None
        return self._fallback

    def extract_text(self, image_path: str) -> Optional[str]:
        engine = self._get_fallback()
        if engine is None:
            return None
        return engine.extract_text(image_path)

    def extract_text_boxes(self, image_path: str) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        engine = self._get_fallback()
        if engine is None:
            return []
        return engine.extract_text_boxes(image_path)


class RapidOCREngine(OCREngine):
    """RapidOCR 3.x engine using the bundled PP-OCRv6-small ONNX models."""

    _MODEL_FILENAMES = {
        "Det.model_path": "PP-OCRv6_det_small.onnx",
        "Cls.model_path": "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "Rec.model_path": "PP-OCRv6_rec_small.onnx",
    }

    def __init__(self):
        self._engine = None
        self._initialization_attempted = False
        self._initialization_lock = Lock()
        self._inference_lock = Lock()

    @classmethod
    def _resolve_bundled_model_paths(cls, rapidocr_module) -> Optional[Dict[str, str]]:
        """Resolve only the models shipped inside the installed RapidOCR package.

        RapidOCR downloads a default model when ``model_path`` is omitted.  The
        desktop runtime must remain fully offline, so initialization is aborted
        before constructing RapidOCR unless every fixed model asset is present.
        """
        package_file = getattr(rapidocr_module, "__file__", None)
        if not package_file:
            logger.warning("RapidOCR package path is unavailable; OCR is disabled")
            return None

        model_dir = (Path(package_file).resolve().parent / "models").resolve()
        resolved = {
            key: (model_dir / filename).resolve()
            for key, filename in cls._MODEL_FILENAMES.items()
        }
        missing = [path.name for path in resolved.values() if not path.is_file()]
        if missing:
            logger.warning(
                "Bundled RapidOCR models are incomplete; OCR is disabled (missing: %s)",
                ", ".join(missing),
            )
            return None

        return {key: str(path) for key, path in resolved.items()}

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        if self._initialization_attempted:
            return None

        with self._initialization_lock:
            if self._engine is not None:
                return self._engine
            if self._initialization_attempted:
                return None

            self._initialization_attempted = True
            try:
                import rapidocr
                from rapidocr import (
                    EngineType,
                    LangDet,
                    LangRec,
                    ModelType,
                    OCRVersion,
                    RapidOCR,
                )

                model_paths = self._resolve_bundled_model_paths(rapidocr)
                if model_paths is None:
                    return None

                self._engine = RapidOCR(
                    params={
                        "Global.log_level": "warning",
                        "Det.engine_type": EngineType.ONNXRUNTIME,
                        "Det.lang_type": LangDet.CH,
                        "Det.model_type": ModelType.SMALL,
                        "Det.ocr_version": OCRVersion.PPOCRV6,
                        "Cls.engine_type": EngineType.ONNXRUNTIME,
                        "Rec.engine_type": EngineType.ONNXRUNTIME,
                        "Rec.lang_type": LangRec.CH,
                        "Rec.model_type": ModelType.SMALL,
                        "Rec.ocr_version": OCRVersion.PPOCRV6,
                        **model_paths,
                        "EngineConfig.onnxruntime.use_cuda": False,
                        "EngineConfig.onnxruntime.use_dml": False,
                        "EngineConfig.onnxruntime.use_cann": False,
                        "EngineConfig.onnxruntime.use_coreml": False,
                    }
                )
            except Exception as exc:
                logger.warning("RapidOCR initialization failed: %s", exc)
                return None
        return self._engine

    def _run(self, image_path: str):
        engine = self._get_engine()
        if engine is None:
            return None

        try:
            # A single RapidOCR instance owns ONNX Runtime sessions. Serialize
            # inference so capture and maintenance jobs never race those sessions.
            with self._inference_lock:
                return engine(image_path)
        except Exception as exc:
            logger.warning("RapidOCR inference failed for %s: %s", image_path, exc)
            return None

    def extract_text(self, image_path: str) -> Optional[str]:
        result = self._run(image_path)
        if result is None:
            return None

        texts = getattr(result, "txts", None)
        if not texts:
            return None

        normalized = [str(text).strip() for text in texts if str(text).strip()]
        return "\n".join(normalized) if normalized else None

    def extract_text_boxes(self, image_path: str) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        result = self._run(image_path)
        if result is None:
            return []

        texts = getattr(result, "txts", None)
        boxes = getattr(result, "boxes", None)
        if not texts or boxes is None:
            return []

        results: List[Tuple[str, Tuple[int, int, int, int]]] = []
        for text, points in zip(texts, boxes):
            normalized_text = str(text).strip()
            if not normalized_text:
                continue
            try:
                xs = [float(point[0]) for point in points]
                ys = [float(point[1]) for point in points]
            except (TypeError, ValueError, IndexError):
                logger.warning("Ignoring malformed RapidOCR box: %r", points)
                continue
            if not xs or not ys:
                continue

            rectangle = (
                math.floor(min(xs)),
                math.floor(min(ys)),
                math.ceil(max(xs)),
                math.ceil(max(ys)),
            )
            results.append((normalized_text, rectangle))
        return results


def create_ocr_engine(engine_type: str = "rapidocr") -> OCREngine:
    if engine_type == "rapidocr":
        return RapidOCREngine()
    elif engine_type == "native":
        return NativeOCREngine()
    else:
        raise ValueError(f"Unknown OCR engine type: {engine_type}")


ocr_engine = RapidOCREngine()
