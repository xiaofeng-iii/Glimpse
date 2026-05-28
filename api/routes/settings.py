"""
Settings Routes - Application settings management
"""
from fastapi import APIRouter, HTTPException
import copy

from api.schemas import SettingsResponse, SettingsUpdate, AITestRequest, AITestResponse
from api.dependencies import get_settings_manager, get_ai_client, get_capture_manager
from api.hotkeys import reload_global_hotkeys
from services.bootstrap import configure_ai_client, resolve_ai_configuration
from services.ai_client import AIClient

router = APIRouter(prefix="/settings", tags=["settings"])


def get_default_settings() -> dict:
    """Get default settings structure"""
    return {
        "hotkeys": {
            "screenshot": "<ctrl>+<shift>+g",
            "search": "<ctrl>+<f>",
        },
        "screenshot": {
            "debounce_interval": 5.0,
            "cluster_threshold": 2.0,
            "max_captures_per_window": 10,
        },
        "ai": {
            "provider": "OpenAI",
            "provider_type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-4o-mini",
            "timeout": 30,
        },
        "ocr": {
            "engine": "rapidocr",
            "language": "ch",
        },
        "ui": {
            "theme": "light",
            "auto_hide": False,
            "start_minimized": False,
        },
        "cluster": {
            "cluster_mode": False,
            "cluster_auto_submit": True,
            "cluster_max_images": 5,
            "cluster_timeout": 5,
        },
    }


def get_effective_settings(settings_manager) -> dict:
    """Return settings with the current effective runtime AI config overlaid."""
    settings = settings_manager.get_all()
    effective = copy.deepcopy(settings)
    ai = effective.setdefault("ai", {})
    resolved = resolve_ai_configuration(settings_manager)

    ai["base_url"] = resolved["base_url"]
    ai["model"] = resolved["model"]
    ai["timeout"] = resolved["timeout"]

    # Never expose the env API key back to the frontend.
    ai["api_key"] = ""
    return effective


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get all application settings"""
    try:
        settings_manager = get_settings_manager()
        settings = get_effective_settings(settings_manager)
        return SettingsResponse(**settings)
    except Exception as e:
        # Return defaults if settings not available
        return SettingsResponse(**get_default_settings())


@router.put("")
async def update_settings(settings: SettingsUpdate):
    """Update application settings"""
    try:
        settings_manager = get_settings_manager()
        capture_manager = get_capture_manager()

        # Get current settings
        current = settings_manager.get_all()

        # Merge updates
        update_dict = settings.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                if key in current and isinstance(current[key], dict):
                    current[key].update(value)
                else:
                    current[key] = value

        # Save settings
        settings_manager.update(current)

        # Apply runtime settings
        if settings.screenshot:
            capture_manager.update_settings(settings.screenshot)

        if settings.ai is not None:
            configure_ai_client(get_ai_client(), settings_manager)

        if settings.hotkeys is not None:
            reload_global_hotkeys()

        return {"success": True, "message": "Settings updated"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/test", response_model=AITestResponse)
async def test_ai_connection(request: AITestRequest = None):
    """Test AI API connection"""
    try:
        ai_client = get_ai_client()
        settings_manager = get_settings_manager()
        effective_settings = get_effective_settings(settings_manager)
        effective_ai = effective_settings.get("ai", {})

        has_request_overrides = bool(
            request and any([request.api_key, request.base_url, request.model])
        )

        if has_request_overrides:
            api_key = request.api_key or getattr(ai_client, "_api_key", None)
            base_url = request.base_url or effective_ai.get("base_url", AIClient.DEFAULT_BASE_URL)
            model = request.model or effective_ai.get("model", AIClient.DEFAULT_MODEL)

            if not api_key:
                return AITestResponse(
                    success=False,
                    message="No API key available. Enter a key in settings or restart backend with .env configured.",
                )

            test_client = AIClient()
            configured = test_client.configure(
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            if not configured:
                return AITestResponse(success=False, message="Failed to configure AI client.")

            success, message = test_client.test_model_connection()
            if success:
                return AITestResponse(success=True, message=f"Connection successful: model={model}")
            return AITestResponse(success=False, message=f"Connection test failed: {message}")

        else:
            # Test current runtime configuration
            if not ai_client.is_configured():
                return AITestResponse(
                    success=False,
                    message="AI client not configured. Please set API key in settings.",
                )

            success, message = ai_client.test_model_connection()
            if success:
                active_model = getattr(ai_client, "_model", AIClient.DEFAULT_MODEL)
                return AITestResponse(
                    success=True,
                    message=f"Current configuration is working: model={active_model}",
                )
            return AITestResponse(success=False, message=f"Current AI configuration failed: {message}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_settings():
    """Reset settings to defaults"""
    try:
        settings_manager = get_settings_manager()
        settings_manager.reset()
        configure_ai_client(get_ai_client(), settings_manager)
        reload_global_hotkeys()
        return {"success": True, "message": "Settings reset to defaults"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
