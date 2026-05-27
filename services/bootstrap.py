"""
Bootstrap - 应用启动时的配置编排
将 main.py 中的启动配置逻辑抽离，保持入口文件干净
"""
import os


def configure_ai_client(ai_client, settings_manager) -> bool:
    """配置 AI 客户端：优先从 settings.json，其次从环境变量

    Returns:
        True 如果成功配置了 API Key
    """
    if ai_client.configure_from_settings():
        print(f"AI client configured via settings: model={ai_client._model}")
        return True

    # 从环境变量回退
    provider = os.environ.get("AI_PROVIDER") or settings_manager.get("ai.provider", "OpenAI")
    provider_type = settings_manager.get("ai.provider_type", "openai_compatible")
    api_key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = (
        os.environ.get("AI_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or settings_manager.get("ai.base_url", "https://api.openai.com/v1")
    )
    model = os.environ.get("AI_MODEL") or os.environ.get("MODEL") or settings_manager.get("ai.model", "gpt-4o-mini")
    try:
        timeout = int(os.environ.get("AI_TIMEOUT") or settings_manager.get("ai.timeout", 30))
    except (TypeError, ValueError):
        timeout = 30

    if api_key:
        ai_client.configure(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            provider=provider,
            provider_type=provider_type,
        )
        print(f"AI client configured via environment: model={ai_client._model}")
        return True
    else:
        print("WARNING: No API key found. Screenshot analysis disabled.")
        return False
