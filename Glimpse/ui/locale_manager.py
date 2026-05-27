"""
Locale Manager - handles i18n translation loading and key resolution.
Inspired by Floral Notepaper's i18next + react-i18next pattern,
adapted for PySide6/Qt with a simple dict-based approach.

Usage:
    from ui.locale_manager import locale_manager, t
    label.setText(t("toolbar.screenshot"))
    window.setWindowTitle(t("app.title"))
"""
import json
import locale as _locale
from pathlib import Path
from typing import Any

_LOCALES_DIR = Path(__file__).parent / "locales"

SUPPORTED_LOCALES = ["zh-CN", "en-US"]
DEFAULT_LOCALE = "en-US"

_translations: dict[str, dict] = {}
_current_locale: str = DEFAULT_LOCALE


def _load_locale_file(locale_code: str) -> dict:
    """Load a locale JSON file."""
    path = _LOCALES_DIR / f"{locale_code}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _detect_system_locale() -> str:
    """Detect the system's preferred locale."""
    try:
        sys_locale, _ = _locale.getdefaultlocale()
        if sys_locale:
            if sys_locale.startswith("zh"):
                # Check for traditional Chinese
                if "hant" in sys_locale.lower() or "hk" in sys_locale.lower():
                    return "zh-CN"  # fallback for now
                return "zh-CN"
            if sys_locale.startswith("en"):
                return "en-US"
    except Exception:
        pass
    return DEFAULT_LOCALE


def _resolve_locale(preferred: str | None = None) -> str:
    """Resolve the preferred locale to a supported one.

    Priority:
    1. Explicit preferred value
    2. Saved config setting (passed by caller)
    3. System locale detection
    4. Default fallback (zh-CN)
    """
    if preferred and preferred in SUPPORTED_LOCALES:
        return preferred
    detected = _detect_system_locale()
    if detected in SUPPORTED_LOCALES:
        return detected
    return DEFAULT_LOCALE


class LocaleManager:
    """Singleton locale manager for the application."""

    def __init__(self):
        self._current = DEFAULT_LOCALE
        self._translations = {}

    def init(self, preferred_locale: str | None = None):
        """Initialize translations with the best matching locale."""
        self._current = _resolve_locale(preferred_locale)
        self._load_all()

    def _load_all(self):
        """Preload all locale files."""
        for code in SUPPORTED_LOCALES:
            self._translations[code] = _load_locale_file(code)

    @property
    def current_locale(self) -> str:
        return self._current

    def set_locale(self, locale_code: str):
        """Switch to a different locale."""
        if locale_code in SUPPORTED_LOCALES:
            self._current = locale_code

    def t(self, key: str, **kwargs) -> str:
        """Translate a dot-separated key to the current locale string.

        Args:
            key: Dot-separated key, e.g. 'toolbar.screenshot'
            **kwargs: Format parameters for the template string

        Returns:
            Translated string, or the key itself if not found
        """
        keys = key.split(".")
        value: Any = self._translations.get(self._current, {})

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    break
            else:
                break

        if isinstance(value, str):
            if kwargs:
                try:
                    return value.format(**kwargs)
                except (KeyError, ValueError):
                    pass
            return value

        # Fallback: try zh-CN
        value = self._translations.get(DEFAULT_LOCALE, {})
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return key
            else:
                return key
        if isinstance(value, str):
            if kwargs:
                try:
                    return value.format(**kwargs)
                except (KeyError, ValueError):
                    pass
            return value
        return key


# Global singleton instance
locale_manager = LocaleManager()


def t(key: str, **kwargs) -> str:
    """Shorthand translation function using the global locale manager."""
    return locale_manager.t(key, **kwargs)


def init_locale(preferred: str | None = None):
    """Initialize the global locale manager."""
    locale_manager.init(preferred)
