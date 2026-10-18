"""Optional Baidu Cloud high-precision OCR provider.

The desktop runtime stays local by default. When the user explicitly enables
cloud OCR, this adapter uploads the image to Baidu's accurate_basic endpoint.
Any cloud failure is surfaced as CloudOCRError so the routing engine can fall
back to the bundled local engine.
"""
from __future__ import annotations

from io import BytesIO
import base64
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

from services.ocr_engine import OCREngine
from utils.logger import get_logger


logger = get_logger(__name__)

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
MAX_IMAGE_BYTES = 4 * 1024 * 1024


class CloudOCRError(RuntimeError):
    """Cloud OCR failure with enough context to choose a fallback policy."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        quota: bool = False,
        rate: bool = False,
        auth: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.quota = quota
        self.rate = rate
        self.auth = auth


class BaiduOCREngine(OCREngine):
    """Baidu text recognition (accurate_basic) adapter."""

    def __init__(self, api_key: str, secret_key: str, timeout: int = 30):
        self._api_key = (api_key or "").strip()
        self._secret_key = (secret_key or "").strip()
        self._timeout = max(1, int(timeout))
        self._token: Optional[str] = None
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()

    def _get_access_token(self, force: bool = False) -> str:
        with self._token_lock:
            now = time.monotonic()
            if not force and self._token and now < self._token_expires_at:
                return self._token
            if not self._api_key or not self._secret_key:
                raise CloudOCRError(
                    "未填写百度 OCR 的 API Key 或 Secret Key",
                    auth=True,
                )
            try:
                response = requests.post(
                    TOKEN_URL,
                    params={
                        "grant_type": "client_credentials",
                        "client_id": self._api_key,
                        "client_secret": self._secret_key,
                    },
                    timeout=self._timeout,
                )
                payload = response.json()
            except requests.RequestException as exc:
                raise CloudOCRError(f"百度 OCR 连接失败：{exc}") from exc
            except ValueError as exc:
                raise CloudOCRError("百度 OCR 返回了无效的令牌响应") from exc

            if payload.get("error"):
                detail = payload.get("error_description") or payload["error"]
                raise CloudOCRError(f"百度 OCR 鉴权失败：{detail}", auth=True)

            token = str(payload.get("access_token") or "").strip()
            if not token:
                raise CloudOCRError("百度 OCR 未返回访问令牌", auth=True)

            expires_in = int(payload.get("expires_in") or 2592000)
            self._token = token
            self._token_expires_at = now + max(60, expires_in - 60)
            return token

    def _prepare_image(self, image_path: str) -> bytes:
        try:
            data = Path(image_path).read_bytes()
        except OSError as exc:
            raise CloudOCRError(f"读取图片失败：{exc}") from exc
        if len(data) <= MAX_IMAGE_BYTES:
            return data

        try:
            with Image.open(BytesIO(data)) as image:
                image = image.convert("RGB")
                for quality in (92, 85, 78, 70):
                    buffer = BytesIO()
                    image.save(buffer, format="JPEG", quality=quality, optimize=True)
                    if buffer.tell() <= MAX_IMAGE_BYTES:
                        return buffer.getvalue()
                resized = image
                for _ in range(4):
                    resized = resized.resize(
                        (max(1, int(resized.width * 0.8)), max(1, int(resized.height * 0.8))),
                        Image.LANCZOS,
                    )
                    buffer = BytesIO()
                    resized.save(buffer, format="JPEG", quality=85, optimize=True)
                    if buffer.tell() <= MAX_IMAGE_BYTES:
                        return buffer.getvalue()
        except Exception as exc:
            raise CloudOCRError(f"图片压缩失败：{exc}") from exc

        raise CloudOCRError("图片过大，无法压缩到百度 OCR 的 4MB 限制内")

    def _request_ocr_bytes(self, image_bytes: bytes, token: str) -> dict:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        try:
            response = requests.post(
                OCR_URL,
                params={"access_token": token},
                data={"image": encoded, "detect_direction": "true"},
                timeout=self._timeout,
            )
            payload = response.json()
        except requests.RequestException as exc:
            raise CloudOCRError(f"百度 OCR 请求失败：{exc}") from exc
        except ValueError as exc:
            raise CloudOCRError("百度 OCR 返回了无效的响应") from exc
        if not isinstance(payload, dict):
            raise CloudOCRError("百度 OCR 返回了无效的响应")
        return payload

    def _request_ocr(self, image_path: str, token: str) -> dict:
        return self._request_ocr_bytes(self._prepare_image(image_path), token)

    @staticmethod
    def _test_image() -> bytes:
        image = Image.new("RGB", (320, 80), "white")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.load_default(size=36)
        except TypeError:
            font = ImageFont.load_default()
        draw.text((12, 20), "TEST 123", fill="black", font=font)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def extract_text(self, image_path: str) -> Optional[str]:
        token = self._get_access_token()
        for attempt in range(2):
            payload = self._request_ocr(image_path, token)
            error_code = str(payload.get("error_code") or "").strip()
            if error_code in {"110", "111"} and attempt == 0:
                token = self._get_access_token(force=True)
                continue
            if error_code:
                raise self._error_from_payload(error_code, payload)
            words_result = payload.get("words_result") or []
            if not isinstance(words_result, list):
                return None
            text = "\n".join(
                str(item.get("words", "")).strip()
                for item in words_result
                if isinstance(item, dict) and str(item.get("words", "")).strip()
            )
            return text or None
        return None

    def extract_text_boxes(self, image_path: str):
        return []

    def test_connection(self) -> Tuple[bool, str]:
        try:
            token = self._get_access_token(force=True)
            payload = self._request_ocr_bytes(self._test_image(), token)
            error_code = str(payload.get("error_code") or "").strip()
            if error_code:
                raise self._error_from_payload(error_code, payload)
            return True, "百度 OCR 连接成功"
        except CloudOCRError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"百度 OCR 连接失败：{exc}"

    @staticmethod
    def _error_from_payload(error_code: str, payload: dict) -> CloudOCRError:
        detail = str(payload.get("error_msg") or "").strip()
        if error_code in {"17", "19"}:
            message = "百度 OCR 免费额度已用完"
        elif error_code == "18":
            message = "百度 OCR 请求过于频繁（QPS 超限）"
        elif error_code in {"110", "111"}:
            message = "百度 OCR 访问令牌已失效"
        elif detail:
            message = f"百度 OCR 错误：{detail}"
        else:
            message = f"百度 OCR 错误（{error_code}）"
        return CloudOCRError(
            message,
            code=error_code,
            quota=error_code in {"17", "19"},
            rate=error_code == "18",
            auth=error_code in {"110", "111"},
        )
