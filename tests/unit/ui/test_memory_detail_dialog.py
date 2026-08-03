from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


def test_open_image_uses_application_modal(qtbot, tmp_path):
    from ui.memory_detail_dialog import MemoryDetailDialog

    image_path = tmp_path / "memory.png"
    pixmap = QPixmap(32, 24)
    pixmap.fill(Qt.GlobalColor.white)
    assert pixmap.save(str(image_path))

    dialog = MemoryDetailDialog(
        SimpleNamespace(
            id="memory-1",
            created_at="2026-01-01 12:00:00",
            image_path=str(image_path),
            ai_summary="summary",
            app_name="unknown",
        )
    )
    qtbot.addWidget(dialog)

    with patch("ui.memory_detail_dialog._ImagePreviewDialog") as preview_class:
        dialog._on_open_image()

    preview_class.assert_called_once_with(str(image_path), dialog)
    preview_class.return_value.exec.assert_called_once_with()


def test_open_image_ignores_missing_file(qtbot, tmp_path):
    from ui.memory_detail_dialog import MemoryDetailDialog

    dialog = MemoryDetailDialog(
        SimpleNamespace(
            id="memory-1",
            created_at="2026-01-01 12:00:00",
            image_path=str(tmp_path / "missing.png"),
            ai_summary="summary",
            app_name="unknown",
        )
    )
    qtbot.addWidget(dialog)

    with patch("ui.memory_detail_dialog._ImagePreviewDialog") as preview_class:
        dialog._on_open_image()

    preview_class.assert_not_called()
