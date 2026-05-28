"""
OCR Engine - OCR 抽象类与具体实现
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from pathlib import Path


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
    """RapidOCR 引擎"""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR()
            except ImportError:
                return None
        return self._engine

    def extract_text(self, image_path: str) -> Optional[str]:
        engine = self._get_engine()
        if not engine:
            return None

        try:
            result, _, _ = engine(image_path)
        except Exception:
            return None

        if not result:
            return None

        return "\n".join([item[1] for item in result])

    def extract_text_boxes(self, image_path: str) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        engine = self._get_engine()
        if not engine:
            return []

        try:
            result, _, _ = engine(image_path)
        except Exception:
            return []

        if not result:
            return []

        return [(item[1], tuple(item[0])) for item in result]


def create_ocr_engine(engine_type: str = "rapidocr") -> OCREngine:
    if engine_type == "rapidocr":
        return RapidOCREngine()
    elif engine_type == "native":
        return NativeOCREngine()
    else:
        raise ValueError(f"Unknown OCR engine type: {engine_type}")


ocr_engine = RapidOCREngine()
