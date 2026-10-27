"""
Bootstrap 配置解析测试
"""
import logging
from unittest.mock import Mock

from services.bootstrap import configure_ai_client, resolve_ai_configuration


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


def test_configure_logs_redacted_url_without_changing_client_configuration(caplog):
    url = "https://alice:password-secret@host/v1?api_key=query-secret&token=token-secret&model=demo"
    settings = _SettingsManagerStub({"ai": {"api_key": "client-secret", "base_url": url}})
    client = Mock(_base_url=url, _model="demo")
    with caplog.at_level(logging.INFO, logger="services.bootstrap"):
        assert configure_ai_client(client, settings)
    assert client.configure.call_args.kwargs["base_url"] == url
    assert client.configure.call_args.kwargs["api_key"] == "client-secret"
    for secret in ["alice", "password-secret", "query-secret", "token-secret", "client-secret"]:
        assert secret not in caplog.text
    assert "host/v1" in caplog.text
    assert "model=demo" in caplog.text
