"""
Glimpse Frontend Preview - standalone entry point (no backend required).

Usage:
    python main.py           # light theme
    python main.py dark      # dark theme
    python main.py system    # follow OS theme

This launches the complete styled frontend with demo memory data.
No backend services required.
"""
import sys
from pathlib import Path

# Ensure project root is importable
project_root = Path(__file__).parent / "Glimpse"
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def main():
    # Parse theme argument
    initial_theme = "light"
    if len(sys.argv) > 1:
        initial_theme = sys.argv[1]
    print(f"Starting Glimpse Frontend Preview (theme: {initial_theme})...")

    # Bootstrap: init locale manager
    from ui.locale_manager import init_locale
    import locale
    try:
        sys_locale, _ = locale.getdefaultlocale()
        if sys_locale and sys_locale.startswith("en"):
            init_locale("en-US")
        else:
            init_locale("zh-CN")
    except Exception:
        init_locale("zh-CN")

    # Initialize DI container in preview mode (mock services)
    from container import container
    container.initialize_preview_mode()

    # Create QApplication (with High-DPI support)
    app = QApplication(sys.argv)
    app.setApplicationName("Glimpse")
    app.setOrganizationName("Glimpse")

    # Init theme manager
    from ui.theme_manager import ThemeManager
    theme_manager = ThemeManager(app)

    # Build main window with theme manager
    from ui.main_window import MainWindow
    window = MainWindow(theme_manager=theme_manager)

    # Apply theme
    theme_manager.apply_theme(initial_theme)
    window._current_theme = initial_theme

    # Show window
    window.show()

    print("Frontend preview running. Close the window to exit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
