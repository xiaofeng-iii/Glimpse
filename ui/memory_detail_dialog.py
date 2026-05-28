"""
MemoryDetailDialog - polished detail view for a single memory record.
Inspired by Floral Notepaper's detail/card views.
"""
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QScrollArea, QFrame, QMessageBox,
    QApplication, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap, QIcon, QPainter, QColor, QPen

from ui.locale_manager import t


def _display_app_name(memory) -> str:
    """Return a displayable app name, hiding placeholder values."""
    app_name = (getattr(memory, "app_name", "") or "").strip()
    if not app_name or app_name.lower() == "unknown":
        return ""
    return app_name


def _make_placeholder_image(size: int = 160) -> QPixmap:
    """Generate a placeholder image when screenshot is unavailable."""
    pixmap = QPixmap(size, int(size * 0.6))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Card background
    painter.setBrush(QColor("#F1F5F9"))
    painter.setPen(QPen(QColor("#E2E8F0"), 1.5))
    painter.drawRoundedRect(2, 2, size - 4, int(size * 0.6) - 4, 10, 10)

    # Icon (mountain/sun)
    painter.setPen(QPen(QColor("#94A3B8"), 2))
    cx, cy = size // 2, int(size * 0.3)
    # Sun
    painter.setBrush(QColor("#CBD5E1"))
    painter.drawEllipse(cx - 14, cy - 18, 28, 28)
    # Mountains
    painter.setBrush(QColor("#94A3B8"))
    points_left = [
        (cx - 50, cy + 20),
        (cx - 25, cy - 10),
        (cx, cy + 20),
    ]
    points_right = [
        (cx - 10, cy + 20),
        (cx + 15, cy - 5),
        (cx + 45, cy + 20),
    ]
    from PySide6.QtGui import QPolygonF
    from PySide6.QtCore import QPointF
    painter.drawPolygon([QPointF(*p) for p in points_left])
    painter.drawPolygon([QPointF(*p) for p in points_right])

    # Text
    painter.setPen(QColor("#94A3B8"))
    font = QFont("Segoe UI", 11)
    painter.setFont(font)
    painter.drawText(2, int(size * 0.6) - 30, size - 4, 20,
                     Qt.AlignmentFlag.AlignCenter, "No Preview")

    painter.end()
    return pixmap


class MemoryDetailDialog(QDialog):
    """Polished detail dialog for a memory record."""

    def __init__(self, memory, parent=None):
        super().__init__(parent)
        self._memory = memory

        self.setWindowTitle(t("detail.title"))
        self.setMinimumSize(520, 560)
        self.resize(580, 620)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self._init_ui()
        self._populate()

    def _init_ui(self):
        """Build the dialog layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # --- Header: app name badge + time ---
        header = QHBoxLayout()
        header.setSpacing(10)

        app_name = _display_app_name(self._memory)
        if app_name:
            app_chip = QLabel(app_name)
            app_chip.setObjectName("appChip")
            app_chip.setProperty("appName", True)
            font = app_chip.font()
            font.setPointSize(12)
            app_chip.setFont(font)
            header.addWidget(app_chip)

        header.addStretch()

        time_str = getattr(self._memory, "created_at", "") or ""
        time_label = QLabel(time_str)
        time_label.setObjectName("subtitle")
        header.addWidget(time_label)

        layout.addLayout(header)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # --- Image preview ---
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setMinimumHeight(180)
        img_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        image_path = getattr(self._memory, "image_path", "")
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaledToWidth(500, Qt.TransformationMode.SmoothTransformation)
                img_label.setPixmap(scaled)
            else:
                img_label.setPixmap(_make_placeholder_image(400))
        else:
            img_label.setPixmap(_make_placeholder_image(400))

        layout.addWidget(img_label)

        # --- AI Summary ---
        summary_label = QLabel(t("detail.summary"))
        summary_label.setObjectName("sectionTitle")
        layout.addWidget(summary_label)

        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setMaximumHeight(120)
        self._summary_text.setObjectName("detailText")
        layout.addWidget(self._summary_text)

        # --- OCR Text ---
        ocr_label = QLabel(t("detail.ocr_text"))
        ocr_label.setObjectName("sectionTitle")
        layout.addWidget(ocr_label)

        self._ocr_text = QTextEdit()
        self._ocr_text.setReadOnly(True)
        self._ocr_text.setMaximumHeight(80)
        self._ocr_text.setObjectName("detailText")
        layout.addWidget(self._ocr_text)

        # --- Image path ---
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_title = QLabel(t("detail.image_path") + ":")
        path_title.setObjectName("subtitle")
        path_row.addWidget(path_title)
        self._path_label = QLabel(getattr(self._memory, "image_path", ""))
        self._path_label.setObjectName("subtitle")
        self._path_label.setWordWrap(True)
        path_row.addWidget(self._path_label, 1)
        layout.addLayout(path_row)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        copy_btn = QPushButton(t("detail.copy_text"))
        copy_btn.setObjectName("secondaryBtn")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._on_copy)
        btn_row.addWidget(copy_btn)

        open_img_btn = QPushButton(t("detail.open_image"))
        open_img_btn.setObjectName("secondaryBtn")
        open_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_img_btn.clicked.connect(self._on_open_image)
        btn_row.addWidget(open_img_btn)

        btn_row.addStretch()

        delete_btn = QPushButton(t("detail.delete"))
        delete_btn.setObjectName("dangerBtn")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(delete_btn)

        close_btn = QPushButton(t("settings.cancel"))
        close_btn.setObjectName("secondaryBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _populate(self):
        """Fill in memory data."""
        summary = getattr(self._memory, "ai_summary", "") or ""
        self._summary_text.setPlainText(summary)

        text_content = getattr(self._memory, "text_content", "") or ""
        if text_content:
            self._ocr_text.setPlainText(text_content)
        else:
            self._ocr_text.setPlainText("(No OCR text)")

    def _on_copy(self):
        """Copy memory summary to clipboard."""
        text = getattr(self._memory, "ai_summary", "") or ""
        QApplication.clipboard().setText(text)

    def _on_open_image(self):
        """Open the screenshot with the system viewer."""
        path = getattr(self._memory, "image_path", "")
        if path and os.path.exists(path):
            import subprocess
            import sys
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])

    def _on_delete(self):
        """Confirm and emit delete signal."""
        reply = QMessageBox.question(
            self,
            t("detail.confirm_delete_title"),
            t("detail.confirm_delete_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from ui.signals import signals
            mem_id = getattr(self._memory, "id", "")
            if mem_id:
                signals.memory_deleted.emit(mem_id)
            self.accept()
