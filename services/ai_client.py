"""
AI Client - 负责打包数据并与云端大模型交互
支持构造函数注入SettingsManager依赖
"""
from typing import Optional, Callable, TYPE_CHECKING, List, Tuple

import openai

if TYPE_CHECKING:
    from config.settings_manager import SettingsManager


class AIClient:
    """AI 客户端 - 支持构造函数注入依赖"""

    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_PROVIDER = "OpenAI"
    DEFAULT_PROVIDER_TYPE = "openai_compatible"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_TIMEOUT = 120

    def __init__(self, settings_manager: Optional["SettingsManager"] = None):
        self._settings_manager = settings_manager
        self._client: Optional[openai.OpenAI] = None
        self._api_key: Optional[str] = None
        self._provider: str = self.DEFAULT_PROVIDER
        self._provider_type: str = self.DEFAULT_PROVIDER_TYPE
        self._base_url: str = self.DEFAULT_BASE_URL
        self._model: str = self.DEFAULT_MODEL
        self._timeout: int = self.DEFAULT_TIMEOUT

    def clear_configuration(self):
        self._client = None
        self._api_key = None
        self._provider = self.DEFAULT_PROVIDER
        self._provider_type = self.DEFAULT_PROVIDER_TYPE
        self._base_url = self.DEFAULT_BASE_URL
        self._model = self.DEFAULT_MODEL
        self._timeout = self.DEFAULT_TIMEOUT

    def configure(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        provider: str = DEFAULT_PROVIDER,
        provider_type: str = DEFAULT_PROVIDER_TYPE,
    ):
        if provider_type != self.DEFAULT_PROVIDER_TYPE:
            raise ValueError(f"Unsupported provider_type: {provider_type}")
        if not api_key:
            self.clear_configuration()
            return False

        self._api_key = api_key
        self._provider = provider or self.DEFAULT_PROVIDER
        self._provider_type = provider_type
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._model = model or self.DEFAULT_MODEL
        self._timeout = timeout
        self._client = openai.OpenAI(api_key=api_key, base_url=self._base_url, timeout=timeout)
        return True

    def configure_from_settings(self) -> bool:
        if self._settings_manager is None:
            self.clear_configuration()
            return False
        provider = self._settings_manager.get("ai.provider", self.DEFAULT_PROVIDER)
        provider_type = self._settings_manager.get("ai.provider_type", self.DEFAULT_PROVIDER_TYPE)
        base_url = self._settings_manager.get("ai.base_url", self.DEFAULT_BASE_URL)
        api_key = self._settings_manager.get("ai.api_key", "")
        model = self._settings_manager.get("ai.model", self.DEFAULT_MODEL)
        timeout = self._settings_manager.get("ai.timeout", self.DEFAULT_TIMEOUT)
        if not api_key:
            self.clear_configuration()
            return False
        return self.configure(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            provider=provider,
            provider_type=provider_type,
        )

    def is_configured(self) -> bool:
        return self._client is not None

    def test_connection(self) -> bool:
        success, _ = self.test_model_connection()
        return success

    def test_model_connection(self) -> Tuple[bool, str]:
        if not self._client:
            return False, "AI client not configured"
        try:
            self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0,
            )
            return True, "Connection successful!"
        except Exception as exc:
            return False, str(exc)

    def analyze_image(
        self,
        image_path: str,
        prompt: str = "描述这张截图的内容",
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        return self.analyze_images([image_path], prompt, stream_callback)

    def analyze_images(
        self,
        image_paths: List[str],
        prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        if not self._client:
            raise RuntimeError("AI client not configured")

        content = []
        for path in image_paths:
            image_base64 = self._read_image_base64(path)
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            )
        content.append({"type": "text", "text": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": content}],
            max_tokens=500,
            temperature=0.7,
            stream=True if stream_callback else False,
        )

        if stream_callback:
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    stream_callback(content)
            return full_response
        else:
            return response.choices[0].message.content

    def generate_summary(self, text: str, prompt: str = "为以下内容生成简短摘要：") -> str:
        if not self._client:
            raise RuntimeError("AI client not configured")

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "你是一个文本摘要助手。"},
                {"role": "user", "content": f"{prompt}\n\n{text}"},
            ],
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content

    def _read_image_base64(self, image_path: str) -> str:
        import base64
        import io
        try:
            from PIL import Image
            img = Image.open(image_path)
            # Resize to max 1920px width to keep payload under API limits
            if img.width > 1920:
                ratio = 1920 / img.width
                new_size = (1920, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            # Convert to JPEG with compression for faster upload
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=70, optimize=True)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            # Fallback: read raw file if PIL fails
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")


ai_client = AIClient()
