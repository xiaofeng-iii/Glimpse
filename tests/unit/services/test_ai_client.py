"""
AIClient 单元测试

测试服务模块 services/ai_client.py
覆盖: AIClient 配置, 连接测试, 图像分析, 文本摘要
"""
import base64
import pytest
from unittest.mock import MagicMock, patch, mock_open

from services.ai_client import AIClient, ai_client


@pytest.fixture
def mock_openai_client():
    """创建一个 mock 的 OpenAI 客户端"""
    client = MagicMock()
    # 设置 analyze_image 响应
    mock_choice = MagicMock()
    mock_choice.message.content = "这张截图显示了一个浏览器窗口"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


class TestAIClientInit:
    """AIClient 初始化测试"""

    def test_init_without_settings(self):
        """验证: 不传 settings_manager 也能正常初始化"""
        client = AIClient()
        assert client._settings_manager is None
        assert client._client is None

    def test_init_with_settings(self, mock_settings_manager):
        """验证: 传入 settings_manager 后存储引用"""
        client = AIClient(mock_settings_manager)
        assert client._settings_manager is mock_settings_manager

    def test_not_configured_initially(self):
        """验证: 新实例默认未配置"""
        client = AIClient()
        assert client.is_configured() is False


class TestAIClientConfigure:
    """AIClient.configure 测试"""

    def test_configure_creates_client(self):
        """验证: configure 创建 OpenAI 客户端"""
        with patch("openai.OpenAI") as mock_openai:
            client = AIClient()
            client.configure("test-key")
            mock_openai.assert_called_once_with(
                api_key="test-key",
                base_url="https://api.openai.com/v1",
                timeout=30,
            )

    def test_configure_custom_base_url(self):
        """验证: configure 支持自定义 base_url"""
        with patch("openai.OpenAI") as mock_openai:
            client = AIClient()
            client.configure("test-key", base_url="https://custom.api.com/v1")
            mock_openai.assert_called_once_with(
                api_key="test-key",
                base_url="https://custom.api.com/v1",
                timeout=30,
            )

    def test_configure_custom_base_url_and_timeout(self):
        """验证: configure 将自定义 base_url 和 timeout 传给 OpenAI 客户端"""
        with patch("openai.OpenAI") as mock_openai:
            client = AIClient()
            client.configure(
                api_key="test-key",
                base_url="https://custom.api.com/v1",
                model="custom-model",
                timeout=60,
                provider="Local Provider",
                provider_type="openai_compatible",
            )
            mock_openai.assert_called_once_with(
                api_key="test-key",
                base_url="https://custom.api.com/v1",
                timeout=60,
            )
            assert client._provider == "Local Provider"
            assert client._provider_type == "openai_compatible"
            assert client._base_url == "https://custom.api.com/v1"
            assert client._model == "custom-model"
            assert client._timeout == 60

    def test_is_configured_after_configure(self):
        """验证: configure 后 is_configured 返回 True"""
        with patch("openai.OpenAI"):
            client = AIClient()
            client.configure("test-key")
            assert client.is_configured() is True

    def test_clear_configuration_resets_unconfigured_state(self):
        """验证: clear_configuration 清理客户端状态"""
        with patch("openai.OpenAI"):
            client = AIClient()
            client.configure("test-key")
            client.clear_configuration()
            assert client.is_configured() is False
            assert client._api_key is None
            assert client._base_url == "https://api.openai.com/v1"


class TestAIClientConfigureFromSettings:
    """AIClient.configure_from_settings 测试"""

    def test_no_settings_returns_false(self):
        """验证: 无 settings_manager 时返回 False"""
        client = AIClient()
        assert client.configure_from_settings() is False

    def test_empty_api_key_returns_false(self, mock_settings_manager):
        """验证: API Key 为空时返回 False"""
        mock_settings_manager.get.return_value = ""
        client = AIClient(mock_settings_manager)
        client._client = MagicMock()
        assert client.configure_from_settings() is False
        assert client.is_configured() is False

    def test_valid_api_key_returns_true(self, mock_settings_manager):
        """验证: 有效 API Key 时配置成功返回 True"""
        # 修改 _get 函数的返回值以模拟有效 API Key
        def _get_with_key(key, default=None):
            if key == "ai.api_key":
                return "sk-test-123"
            if key == "ai.provider":
                return "Custom Provider"
            if key == "ai.provider_type":
                return "openai_compatible"
            if key == "ai.base_url":
                return "https://custom.api.com/v1"
            if key == "ai.model":
                return "custom-model"
            if key == "ai.timeout":
                return 45
            return default

        mock_settings_manager.get = _get_with_key
        with patch("openai.OpenAI") as mock_openai:
            client = AIClient(mock_settings_manager)
            result = client.configure_from_settings()
            assert result is True
            mock_openai.assert_called_once_with(
                api_key="sk-test-123",
                base_url="https://custom.api.com/v1",
                timeout=45,
            )
            assert client._provider == "Custom Provider"
            assert client._model == "custom-model"


class TestAIClientTestConnection:
    """AIClient.test_connection 测试"""

    def test_not_configured_returns_false(self):
        """验证: 未配置时返回 False"""
        client = AIClient()
        assert client.test_connection() is False

    def test_connection_success(self):
        """验证: API 响应正常时返回 True"""
        with patch("openai.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_client.chat.completions.create.return_value = MagicMock()

            client = AIClient()
            client.configure("test-key")
            assert client.test_connection() is True

    def test_connection_failure(self):
        """验证: API 异常时返回 False"""
        with patch("openai.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_client.chat.completions.create.side_effect = Exception("Connection refused")

            client = AIClient()
            client.configure("test-key")
            assert client.test_connection() is False

    def test_model_connection_returns_error_message(self):
        """验证: test_model_connection 返回具体错误信息"""
        with patch("openai.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_client.chat.completions.create.side_effect = Exception("Invalid model")

            client = AIClient()
            client.configure("test-key", model="bad-model")
            success, message = client.test_model_connection()
            assert success is False
            assert "Invalid model" in message


class TestAIClientAnalyzeImage:
    """AIClient.analyze_image 测试"""

    @pytest.fixture
    def configured_client(self):
        """创建一个已配置的 AIClient"""
        with patch("openai.OpenAI"):
            client = AIClient()
            client.configure("test-key")
            return client

    def test_not_configured_raises(self):
        """验证: 未配置时调用 analyze_image 抛出 RuntimeError"""
        client = AIClient()
        with pytest.raises(RuntimeError, match="not configured"):
            client.analyze_image("test.png")

    def test_analyze_image_returns_content(self, configured_client):
        """验证: analyze_image 返回 AI 响应内容"""
        mock_choice = MagicMock()
        mock_choice.message.content = "这张截图显示了一个IDE界面"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = mock_response

        with patch.object(configured_client, '_read_image_base64', return_value="base64data"):
            result = configured_client.analyze_image("test.png")
            assert result == "这张截图显示了一个IDE界面"

    def test_analyze_image_custom_prompt(self, configured_client):
        """验证: analyze_image 使用自定义提示语"""
        mock_choice = MagicMock()
        mock_choice.message.content = "Custom response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = mock_response

        with patch.object(configured_client, '_read_image_base64', return_value="base64data"):
            result = configured_client.analyze_image("test.png", prompt="分析这张图片")
            assert result == "Custom response"

            # 验证 API 调用包含自定义 prompt
            call_args = configured_client._client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            text_content = messages[0]["content"][1]
            assert text_content["text"] == "分析这张图片"

    def test_analyze_image_streaming(self, configured_client):
        """验证: stream_callback 时逐块返回"""
        # 模拟流式响应：code accesses choice.delta.content
        mock_delta = MagicMock()
        mock_delta.content = "这是测试"
        mock_choice = MagicMock()
        mock_choice.delta = mock_delta
        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = [mock_chunk]

        collected = []
        with patch.object(configured_client, '_read_image_base64', return_value="base64data"):
            result = configured_client.analyze_image(
                "test.png",
                stream_callback=lambda s: collected.append(s),
            )
            assert result == "这是测试"
            assert collected == ["这是测试"]

    def test_analyze_image_encodes_to_base64(self, configured_client):
        """验证: analyze_image 将图片编码为 base64"""
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = mock_response

        fake_image_data = b"\x89PNG\r\n\x1a\n"
        with patch("builtins.open", mock_open(read_data=fake_image_data)):
            with patch.object(configured_client, '_read_image_base64',
                              wraps=configured_client._read_image_base64) as spy:
                configured_client.analyze_image("test.png")
                assert spy.called

    def test_default_prompt_used(self, configured_client):
        """验证: 未指定 prompt 时使用默认提示"""
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = mock_response

        with patch.object(configured_client, '_read_image_base64', return_value="base64data"):
            configured_client.analyze_image("test.png")
            call_args = configured_client._client.chat.completions.create.call_args
            assert call_args[1]["model"] == "gpt-4o-mini"
            assert call_args[1]["max_tokens"] == 500

    def test_analyze_images_not_configured_raises(self):
        """验证: 未配置时调用 analyze_images 抛出 RuntimeError"""
        client = AIClient()
        with pytest.raises(RuntimeError, match="not configured"):
            client.analyze_images(["test1.png", "test2.png"], "prompt")

    def test_analyze_images_returns_content(self, configured_client):
        """验证: analyze_images 返回 AI 响应内容"""
        mock_choice = MagicMock()
        mock_choice.message.content = "这些截图显示了多个界面"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = mock_response

        with patch.object(configured_client, '_read_image_base64', return_value="base64data"):
            result = configured_client.analyze_images(["test1.png", "test2.png"], "分析这些图片")
            assert result == "这些截图显示了多个界面"

            # 验证 API 调用包含多个 image_url 和最后的 text prompt
            call_args = configured_client._client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            content = messages[0]["content"]
            assert len(content) == 3
            assert content[0]["type"] == "image_url"
            assert content[0]["image_url"]["url"] == "data:image/jpeg;base64,base64data"
            assert content[1]["type"] == "image_url"
            assert content[1]["image_url"]["url"] == "data:image/jpeg;base64,base64data"
            assert content[2]["type"] == "text"
            assert content[2]["text"] == "分析这些图片"

    def test_analyze_images_streaming(self, configured_client):
        """验证: analyze_images 在 stream_callback 时逐块返回"""
        mock_delta = MagicMock()
        mock_delta.content = "流式响应"
        mock_choice = MagicMock()
        mock_choice.delta = mock_delta
        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = [mock_chunk]

        collected = []
        with patch.object(configured_client, '_read_image_base64', return_value="base64data"):
            result = configured_client.analyze_images(
                ["test1.png", "test2.png"],
                "分析这些图片",
                stream_callback=lambda s: collected.append(s),
            )
            assert result == "流式响应"
            assert collected == ["流式响应"]


class TestAIClientGenerateSummary:
    """AIClient.generate_summary 测试"""

    @pytest.fixture
    def configured_client(self):
        with patch("openai.OpenAI"):
            client = AIClient()
            client.configure("test-key")
            return client

    def test_not_configured_raises(self):
        """验证: 未配置时抛出 RuntimeError"""
        client = AIClient()
        with pytest.raises(RuntimeError, match="not configured"):
            client.generate_summary("some text")

    def test_generate_summary_returns_content(self, configured_client):
        """验证: generate_summary 返回摘要内容"""
        mock_choice = MagicMock()
        mock_choice.message.content = "这是一个关于桌面应用的摘要"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = mock_response

        result = configured_client.generate_summary("some long text content")
        assert result == "这是一个关于桌面应用的摘要"

    def test_generate_summary_custom_prompt(self, configured_client):
        """验证: generate_summary 使用自定义提示"""
        mock_choice = MagicMock()
        mock_choice.message.content = "Custom summary"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        configured_client._client.chat.completions.create.return_value = mock_response

        configured_client.generate_summary("text", prompt="Summarize:")
        call_args = configured_client._client.chat.completions.create.call_args
        assert call_args[1]["max_tokens"] == 200


class TestAIClientReadImageBase64:
    """_read_image_base64 私有方法测试"""

    def test_read_image_base64(self):
        """验证: _read_image_base64 正确编码图片为 base64"""
        client = AIClient()
        fake_data = b"hello_world"
        expected = base64.b64encode(fake_data).decode("utf-8")

        with patch("builtins.open", mock_open(read_data=fake_data)):
            result = client._read_image_base64("fake.png")
            assert result == expected


class TestAIClientGlobal:
    """全局 ai_client 测试"""

    def test_global_is_aiclient(self):
        """验证: 全局 ai_client 是 AIClient 实例"""
        assert isinstance(ai_client, AIClient)

    def test_global_not_configured_initially(self):
        """验证: 全局实例初始未配置"""
        assert ai_client.is_configured() is False
