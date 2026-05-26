"""
Theme Manager - handles theme loading, dynamic switching, and system theme detection.
Inspired by Floral Notepaper's theme system (features/settings/theme.ts).
"""
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal


# Theme directory relative to this file
_STYLES_DIR = Path(__file__).parent / "styles"

# Cache loaded QSS content
_qss_cache: dict[str, str] = {}


def _load_qss(theme_name: str) -> str:
    """Load QSS file content with caching."""
    if theme_name in _qss_cache:
        return _qss_cache[theme_name]

    qss_path = _STYLES_DIR / f"{theme_name}.qss"
    if not qss_path.exists():
        # Fallback to light theme
        qss_path = _STYLES_DIR / "light.qss"

    with open(qss_path, "r", encoding="utf-8") as f:
        content = f.read()

    _qss_cache[theme_name] = content
    return content


def _detect_system_theme() -> str:
    """Detect the OS-level dark/light mode preference.

    On Windows, reads the system registry.
    On macOS, checks the AppleInterfaceStyle.
    On Linux, checks the GTK theme.
    """
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "dark" if value == 0 else "light"
        except Exception:
            return "light"
    elif os.name == "posix":
        # Check macOS
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True
            )
            if "Dark" in result.stdout:
                return "dark"
        except Exception:
            pass
        # Check Linux GTK
        try:
            import subprocess
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True
            )
            if "dark" in result.stdout.lower():
                return "dark"
        except Exception:
            pass
    return "light"


def resolve_theme(theme_setting: str) -> str:
    """Resolve 'system' to actual theme name.

    Args:
        theme_setting: One of 'light', 'dark', 'system'

    Returns:
        'light' or 'dark'
    """
    if theme_setting == "system":
        return _detect_system_theme()
    return theme_setting


def apply_theme(app: QApplication, theme_name: str) -> str:
    """Apply a QSS theme to the entire application.

    Args:
        app: The QApplication instance
        theme_name: 'light', 'dark', or 'system'

    Returns:
        The actual theme applied ('light' or 'dark')
    """
    actual_theme = resolve_theme(theme_name)
    qss = _load_qss(actual_theme)
    app.setStyleSheet(qss)
    return actual_theme


class ThemeManager(QObject):
    """Observable theme manager that emits signals on theme change.

    Usage:
        manager = ThemeManager(app)
        manager.apply_theme("light")
        manager.theme_changed.connect(my_handler)
    """

    theme_changed = Signal(str)

    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent)
        self._app = app
        self._current_theme = "light"

    @property
    def current_theme(self) -> str:
        return self._current_theme

    def apply_theme(self, theme_name: str) -> str:
        """Apply and broadcast theme change."""
        actual = apply_theme(self._app, theme_name)
        if actual != self._current_theme:
            self._current_theme = actual
            self.theme_changed.emit(actual)
        return actual

    def reload(self):
        """Reload the current theme (clears cache)."""
        _qss_cache.clear()
        self.apply_theme(self._current_theme)
