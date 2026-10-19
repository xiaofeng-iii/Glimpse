"""
OCR Engine - OCR 抽象类与具体实现
"""
from abc import ABC, abstractmethod
import math
import sys
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Sequence, Tuple

from utils.logger import get_logger


logger = get_logger(__name__)


def _is_cjk(char: str) -> bool:
    if not char:
        return False
    code = ord(char)
    return (
        0x3400 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x3000 <= code <= 0x303F
        or 0xFF00 <= code <= 0xFFEF
    )


def _box_to_rect(points) -> Optional[Tuple[float, float, float, float]]:
    try:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
    except (TypeError, ValueError, IndexError):
        return None
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _join_line_items(items: Sequence[dict]) -> str:
    if not items:
        return ""
    result = items[0]["text"]
    previous = items[0]
    for item in items[1:]:
        text = item["text"]
        if not text:
            continue
        left = result[-1] if result else ""
        right = text[0]
        separator = ""
        if not _is_cjk(left) and not _is_cjk(right):
            if right in ",.;:!?%)]}":
                separator = ""
            elif left in "([{":
                separator = ""
            elif left in ",;:!?.":
                separator = " "
            elif left in "-'/@":
                separator = ""
            elif len(previous["text"]) >= 2 and len(text) >= 3:
                # PP-OCRv5 word boxes often touch; rely on word length rather
                # than the detected gap so "Operating" + "System" keeps a space.
                separator = " "
        result += separator + text
        previous = item
    return result.strip()


def merge_ocr_lines(texts: Sequence[str], boxes) -> Optional[str]:
    """Merge word/character boxes into visual lines.

    PP-OCRv5 mobile often emits word-level boxes. Joining ``txts`` directly
    produces one word per line; grouping by vertical overlap restores the
    visual line and keeps CJK text free of artificial spaces.
    """
    normalized = [str(text).strip() for text in texts if str(text).strip()]
    if not normalized:
        return None
    if boxes is None or len(boxes) != len(texts):
        return "\n".join(normalized)

    items: List[dict] = []
    malformed = False
    for text, points in zip(texts, boxes):
        value = str(text).strip()
        if not value:
            continue
        rect = _box_to_rect(points)
        if rect is None:
            malformed = True
            break
        x1, y1, x2, y2 = rect
        items.append(
            {
                "text": value,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "h": max(1.0, y2 - y1),
                "cy": (y1 + y2) / 2.0,
            }
        )
    if malformed:
        return "\n".join(normalized)
    if not items:
        return None

    items.sort(key=lambda item: (item["cy"], item["x1"]))
    lines: List[dict] = []
    for item in items:
        target = None
        for line in lines:
            overlap = min(item["y2"], line["y2"]) - max(item["y1"], line["y1"])
            line_height = max(1.0, line["y2"] - line["y1"])
            min_height = min(item["h"], line_height)
            if min_height <= 0:
                continue
            if overlap / min_height < 0.5:
                continue
            if abs(item["cy"] - line["cy"]) > max(item["h"], line_height) * 0.75:
                continue
            target = line
            break

        if target is None:
            lines.append(
                {
                    "y1": item["y1"],
                    "y2": item["y2"],
                    "cy": item["cy"],
                    "items": [item],
                }
            )
            continue

        target["items"].append(item)
        target["y1"] = min(target["y1"], item["y1"])
        target["y2"] = max(target["y2"], item["y2"])
        target["cy"] = (target["y1"] + target["y2"]) / 2.0

    lines.sort(key=lambda line: (line["y1"], min(item["x1"] for item in line["items"])))
    output: List[str] = []
    for line in lines:
        line_items = sorted(line["items"], key=lambda item: item["x1"])
        average_height = sum(item["h"] for item in line_items) / len(line_items)
        max_gap = max(average_height * 4.0, 24.0)
        segments: List[List[dict]] = [[line_items[0]]]
        for item in line_items[1:]:
            if item["x1"] - segments[-1][-1]["x2"] > max_gap:
                segments.append([item])
            else:
                segments[-1].append(item)
        for segment in segments:
            joined = _join_line_items(segment)
            if joined:
                output.append(joined)
    return "\n".join(output) if output else None


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
    """RapidOCR 3.x engine using bundled PP-OCRv5-mobile ONNX models."""

    _DET_FILENAME = "ch_PP-OCRv5_det_mobile.onnx"
    _REC_FILENAME = "ch_PP-OCRv5_rec_mobile.onnx"
    _CLS_FILENAME = "ch_ppocr_mobile_v2.0_cls_mobile.onnx"

    def __init__(self, model_dir: Optional[Path] = None):
        self._model_dir = Path(model_dir) if model_dir else self._default_model_dir()
        self._engine = None
        self._initialization_attempted = False
        self._initialization_lock = Lock()
        self._inference_lock = Lock()

    @staticmethod
    def _default_model_dir() -> Path:
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        else:
            base = Path(__file__).resolve().parent.parent
        return base / "assets" / "ocr"

    @classmethod
    def _resolve_model_paths(cls, rapidocr_module, model_dir: Path) -> Optional[Dict[str, str]]:
        """Resolve bundled models without ever allowing a runtime download."""
        package_file = getattr(rapidocr_module, "__file__", None)
        if not package_file:
            logger.warning("RapidOCR package path is unavailable; OCR is disabled")
            return None

        package_dir = (Path(package_file).resolve().parent / "models").resolve()
        cls_path = package_dir / cls._CLS_FILENAME
        det_path = (model_dir / cls._DET_FILENAME).resolve()
        rec_path = (model_dir / cls._REC_FILENAME).resolve()
        if det_path.is_file() and rec_path.is_file() and cls_path.is_file():
            return {
                "Det.model_path": str(det_path),
                "Rec.model_path": str(rec_path),
                "Cls.model_path": str(cls_path),
                "variant": "PP-OCRv5-mobile",
            }

        missing = [
            path.name
            for path, exists in (
                (det_path, det_path.is_file()),
                (rec_path, rec_path.is_file()),
                (cls_path, cls_path.is_file()),
            )
            if not exists
        ]
        logger.warning(
            "Bundled PP-OCRv5-mobile models are incomplete; OCR is disabled (missing: %s)",
            ", ".join(missing),
        )
        return None

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

                model_paths = self._resolve_model_paths(rapidocr, self._model_dir)
                if model_paths is None:
                    return None

                self._engine = RapidOCR(
                    params={
                        "Global.log_level": "warning",
                        "Global.max_side_len": 4000,
                        "Global.use_preprocess_img": True,
                        "Det.engine_type": EngineType.ONNXRUNTIME,
                        "Det.lang_type": LangDet.CH,
                        "Det.model_type": ModelType.MOBILE,
                        "Det.ocr_version": OCRVersion.PPOCRV5,
                        "Det.limit_side_len": 1280,
                        "Det.limit_type": "min",
                        "Det.model_path": model_paths["Det.model_path"],
                        "Cls.engine_type": EngineType.ONNXRUNTIME,
                        "Cls.model_path": model_paths["Cls.model_path"],
                        "Rec.engine_type": EngineType.ONNXRUNTIME,
                        "Rec.lang_type": LangRec.CH,
                        "Rec.model_type": ModelType.MOBILE,
                        "Rec.ocr_version": OCRVersion.PPOCRV5,
                        "Rec.model_path": model_paths["Rec.model_path"],
                        "EngineConfig.onnxruntime.use_cuda": False,
                        "EngineConfig.onnxruntime.use_dml": False,
                        "EngineConfig.onnxruntime.use_cann": False,
                        "EngineConfig.onnxruntime.use_coreml": False,
                    }
                )
                logger.info(
                    "RapidOCR initialized with %s models from %s",
                    model_paths["variant"],
                    self._model_dir,
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
        return merge_ocr_lines(texts, getattr(result, "boxes", None))

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
            rect = _box_to_rect(points)
            if rect is None:
                logger.warning("Ignoring malformed RapidOCR box: %r", points)
                continue
            x1, y1, x2, y2 = rect
            results.append(
                (
                    normalized_text,
                    (math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2)),
                )
            )
        return results


def create_ocr_engine(engine_type: str = "rapidocr") -> OCREngine:
    if engine_type == "rapidocr":
        return RapidOCREngine()
    elif engine_type == "native":
        return NativeOCREngine()
    else:
        raise ValueError(f"Unknown OCR engine type: {engine_type}")


ocr_engine = RapidOCREngine()
