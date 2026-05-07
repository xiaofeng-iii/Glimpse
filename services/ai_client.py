"""
AI Client - 负责打包数据并与云端大模型交互
支持构造函数注入SettingsManager依赖
"""
from typing import Optional, Callable, TYPE_CHECKING

import openai

if TYPE_CHECKING:
    from config.settings_manager import SettingsManager


class AIClient:
    """AI 客户端 - 支持构造函数注入依赖"""

    def __init__(self, settings_manager: Optional["SettingsManager"] = None):
        self._settings_manager = settings_manager
        self._client: Optional[openai.OpenAI] = None
        self._api_key: Optional[str] = None
        self._base_url: Optional[str] = None

    def configure(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def configure_from_settings(self) -> bool:
        if self._settings_manager is None:
            return False
        api_key = self._settings_manager.get("ai.api_key", "")
        if not api_key:
            return False
        self.configure(api_key)
        return True

    def is_configured(self) -> bool:
        return self._client is not None

    def test_connection(self) -> bool:
        if not self._client:
            return False
        try:
            self._client.models.list()
            return True
        except Exception:
            return False

    def analyze_image(
        self,
        image_path: str,
        prompt: str = "描述这张截图的内容",
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        if not self._client:
            raise RuntimeError("AI client not configured")

        image_base64 = self._read_image_base64(image_path)
        response = self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
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
            model="gpt-4o-mini",
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
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


ai_client = AIClient()
