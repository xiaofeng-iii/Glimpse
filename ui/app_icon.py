"""
Application icon utilities.

Keeps the window, tray, taskbar, and notification icon loading consistent.
"""
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


APP_USER_MODEL_ID = "Glimpse.MemoryAssistant"
ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"
ICON_PATH = ICON_DIR / "glimpse.ico"
PNG_ICON_PATH = ICON_DIR / "glimpse_256.png"


def set_windows_app_user_model_id() -> None:
    """Set the Windows app id so notifications do not show as Python."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def create_app_icon() -> QIcon:
    """Load the bundled app icon, with a small drawn fallback."""
    for path in (ICON_PATH, PNG_ICON_PATH):
        if path.exists():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    return _fallback_icon()


def _fallback_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2563EB"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, 14, 14)

    font = QFont("Segoe UI", int(size * 0.48))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "G")
    painter.end()

    return QIcon(pixmap)
