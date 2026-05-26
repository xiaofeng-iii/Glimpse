"""
UI module - Glimpse polished frontend
"""
from ui.signals import signals
from ui.theme_manager import ThemeManager, apply_theme, resolve_theme
from ui.locale_manager import locale_manager, t, init_locale

__all__ = ["signals", "ThemeManager", "apply_theme", "resolve_theme", "locale_manager", "t", "init_locale"]
