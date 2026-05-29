"""
Bootstrap - 应用启动时的配置编排
将 main.py 中的启动配置逻辑抽离，保持入口文件干净
"""
import os

DEFAULT_PROVIDER = "OpenAI"
DEFAULT_PROVIDER_TYPE = "openai_compatible"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 60


def _prefer_non_default_setting(settings_value: str, env_value: str, default_value: str) -> str:
    settings_value = (settings_value or "").strip()
    env_value = (env_value or "").strip()

    if settings_value and settings_value != default_value:
        return settings_value
    if env_value:
        return env_value
    if settings_value:
        return settings_value
    return default_value


def resolve_ai_configuration(settings_manager) -> dict:
    """Resolve the effective runtime AI configuration from settings + environment."""
    provider = os.environ.get("AI_PROVIDER") or settings_manager.get("ai.provider", DEFAULT_PROVIDER)
    provider_type = settings_manager.get("ai.provider_type", DEFAULT_PROVIDER_TYPE)

    settings_api_key = (settings_manager.get("ai.api_key", "") or "").strip()
    env_api_key = (os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY", "") or "").strip()
    api_key = settings_api_key or env_api_key

    settings_base_url = settings_manager.get("ai.base_url", DEFAULT_BASE_URL)
    env_base_url = os.environ.get("AI_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    base_url = _prefer_non_default_setting(settings_base_url, env_base_url, DEFAULT_BASE_URL)

    settings_model = settings_manager.get("ai.model", DEFAULT_MODEL)
    env_model = os.environ.get("AI_MODEL") or os.environ.get("MODEL")
    model = _prefer_non_default_setting(settings_model, env_model, DEFAULT_MODEL)

    try:
        timeout = int(os.environ.get("AI_TIMEOUT") or settings_manager.get("ai.timeout", DEFAULT_TIMEOUT))
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT

    return {
        "provider": provider,
        "provider_type": provider_type,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "timeout": timeout,
        "api_key_source": "settings" if settings_api_key else ("environment" if env_api_key else "none"),
    }


def configure_ai_client(ai_client, settings_manager) -> bool:
    """配置 AI 客户端：综合 settings.json 与环境变量解析运行态配置

    Returns:
        True 如果成功配置了 API Key
    """
    resolved = resolve_ai_configuration(settings_manager)
    api_key = resolved["api_key"]

    if api_key:
        ai_client.configure(
            api_key=resolved["api_key"],
            base_url=resolved["base_url"],
            model=resolved["model"],
            timeout=resolved["timeout"],
            provider=resolved["provider"],
            provider_type=resolved["provider_type"],
        )
        print(
            "AI client configured via "
            f"{resolved['api_key_source']}: model={ai_client._model}, base_url={ai_client._base_url}"
        )
        return True
    else:
        print("WARNING: No API key found. Screenshot analysis disabled.")
        return False
