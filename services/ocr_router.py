"""Routes OCR calls to the configured provider, with a local fallback."""
from __future__ import annotations

from threading import Lock
from typing import Callable, Optional

from services.cloud_ocr import BaiduOCREngine
from services.ocr_engine import OCREngine, RapidOCREngine
from utils.logger import get_logger


logger = get_logger(__name__)


class ConfiguredOCREngine(OCREngine):
    """Use cloud OCR only when explicitly enabled; always keep local fallback."""

    def __init__(
        self,
        settings_manager,
        local_engine: Optional[OCREngine] = None,
        cloud_factory: Optional[Callable[..., OCREngine]] = None,
    ):
        self._settings_manager = settings_manager
        self._local = local_engine or RapidOCREngine()
        self._cloud_factory = cloud_factory or BaiduOCREngine
        self._cloud_engine: Optional[OCREngine] = None
        self._cloud_signature = None
        self._lock = Lock()

    def _ocr_settings(self) -> dict:
        try:
            settings = self._settings_manager.get_all()
        except Exception as exc:
            logger.warning("Unable to read OCR settings: %s", exc)
            return {}
        if not isinstance(settings, dict):
            return {}
        section = settings.get("ocr", {})
        return section if isinstance(section, dict) else {}

    def _configured_cloud(self) -> Optional[OCREngine]:
        settings = self._ocr_settings()
        if settings.get("mode") != "cloud":
            return None
        if settings.get("provider") not in (None, "", "baidu"):
            return None
        api_key = str(settings.get("api_key") or "").strip()
        secret_key = str(settings.get("secret_key") or "").strip()
        if not api_key or not secret_key:
            return None
        try:
            timeout = max(1, int(settings.get("timeout") or 30))
        except (TypeError, ValueError):
            timeout = 30
        signature = (api_key, secret_key, timeout)
        with self._lock:
            if self._cloud_engine is None or self._cloud_signature != signature:
                self._cloud_engine = self._cloud_factory(api_key, secret_key, timeout)
                self._cloud_signature = signature
            return self._cloud_engine

    def extract_text(self, image_path: str) -> Optional[str]:
        cloud = self._configured_cloud()
        if cloud is not None:
            try:
                text = cloud.extract_text(image_path)
                if text is not None:
                    return text
            except Exception as exc:
                logger.warning("Cloud OCR failed; falling back to local OCR: %s", exc)
        return self._local.extract_text(image_path)

    def extract_text_boxes(self, image_path: str):
        return self._local.extract_text_boxes(image_path)
