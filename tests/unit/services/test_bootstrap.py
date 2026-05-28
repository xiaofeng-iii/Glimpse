"""
Bootstrap 配置解析测试
"""
from services.bootstrap import resolve_ai_configuration


class _SettingsManagerStub:
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        value = self._values
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value


def test_resolve_ai_configuration_prefers_env_when_settings_are_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ark-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://ark.example/v3")
    monkeypatch.setenv("MODEL", "env-model")

    settings = _SettingsManagerStub(
        {
            "ai": {
                "provider": "OpenAI",
                "provider_type": "openai_compatible",
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o-mini",
                "timeout": 30,
            }
        }
    )

    resolved = resolve_ai_configuration(settings)
    assert resolved["api_key"] == "ark-test"
    assert resolved["base_url"] == "https://ark.example/v3"
    assert resolved["model"] == "env-model"
    assert resolved["api_key_source"] == "environment"


def test_resolve_ai_configuration_prefers_saved_model_with_env_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ark-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://ark.example/v3")
    monkeypatch.setenv("MODEL", "old-env-model")

    settings = _SettingsManagerStub(
        {
            "ai": {
                "provider": "OpenAI",
                "provider_type": "openai_compatible",
                "base_url": "https://ark.example/v3",
                "api_key": "",
                "model": "doubao-seed-1-8-251228",
                "timeout": 30,
            }
        }
    )

    resolved = resolve_ai_configuration(settings)
    assert resolved["api_key"] == "ark-test"
    assert resolved["model"] == "doubao-seed-1-8-251228"


def test_resolve_ai_configuration_prefers_full_saved_config(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ark-env")
    monkeypatch.setenv("MODEL", "env-model")

    settings = _SettingsManagerStub(
        {
            "ai": {
                "provider": "OpenAI",
                "provider_type": "openai_compatible",
                "base_url": "https://saved.example/v1",
                "api_key": "saved-key",
                "model": "saved-model",
                "timeout": 45,
            }
        }
    )

    resolved = resolve_ai_configuration(settings)
    assert resolved["api_key"] == "saved-key"
    assert resolved["base_url"] == "https://saved.example/v1"
    assert resolved["model"] == "saved-model"
    assert resolved["timeout"] == 45
    assert resolved["api_key_source"] == "settings"
