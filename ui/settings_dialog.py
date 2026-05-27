"""
Settings Dialog - polished with QSS styling and i18n support.
Inspired by Floral Notepaper's SettingsPanel component.
"""
import copy
from typing import Dict, Any, Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QFormLayout, QLineEdit, QSpinBox,
    QDoubleSpinBox, QComboBox, QCheckBox, QPushButton,
    QLabel, QMessageBox, QGroupBox, QScrollArea, QFrame,
    QKeySequenceEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence

from ui.locale_manager import t
from ui.theme_manager import ThemeManager
from services.hotkey_utils import (
    is_valid_pynput_hotkey,
    pynput_to_qkeysequence,
    qkeysequence_to_pynput,
)


DEFAULT_HOTKEYS = {
    "screenshot": "<ctrl>+<shift>+g",
    "search": "<ctrl>+<f>",
}


class HotkeyRecorder(QKeySequenceEdit):
    """Capture a shortcut directly from keyboard input."""

    def __init__(self, parent=None):
        super().__init__(parent)
        if hasattr(self, "setMaximumSequenceLength"):
            self.setMaximumSequenceLength(1)

    def set_pynput_hotkey(self, hotkey: str) -> None:
        self.setKeySequence(QKeySequence(pynput_to_qkeysequence(hotkey)))

    def pynput_hotkey(self) -> str:
        portable_text = self.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        return qkeysequence_to_pynput(portable_text)


class SettingsDialog(QDialog):
    """Polished settings dialog with tabbed interface."""

    def __init__(
        self,
        settings_manager=None,
        keyboard_manager=None,
        capture_manager=None,
        task_queue=None,
        parent=None,
        ai_client=None,
        theme_manager: Optional[ThemeManager] = None,
    ):
        super().__init__(parent)
        self._settings_manager = settings_manager
        self._keyboard_manager = keyboard_manager
        self._capture_manager = capture_manager
        self._task_queue = task_queue
        self._ai_client = ai_client
        self._theme_manager = theme_manager

        # Load settings
        self._original_settings = self._safe_get_settings()
        self._pending_settings = copy.deepcopy(self._original_settings)
        self._degraded_services = []
        self._screenshot_callback: Optional[Callable] = None

        self.setWindowTitle(t("settings.title"))
        self.setMinimumSize(620, 520)
        self.resize(660, 560)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self._init_ui()
        self._load_current_settings()

    def _safe_get_settings(self) -> dict:
        """Safely load settings; return defaults if backend unavailable."""
        if self._settings_manager:
            try:
                return self._settings_manager.get_all()
            except Exception:
                pass
        return {
            "hotkeys": copy.deepcopy(DEFAULT_HOTKEYS),
            "screenshot": {
                "debounce_interval": 5.0,
                "cluster_threshold": 2.0,
                "max_captures_per_window": 10,
            },
            "ai": {"api_key": "", "model": "gpt-4o-mini", "timeout": 30},
            "ocr": {"engine": "rapidocr", "language": "ch"},
            "ui": {"theme": "light", "auto_hide": False, "start_minimized": False},
        }

    def _get_screenshot_callback(self) -> Callable:
        """Lazy-load screenshot callback."""
        if self._screenshot_callback is None:
            def on_screenshot():
                try:
                    from ui.signals import signals
                    signals.screenshot_requested.emit()
                except Exception:
                    pass
            self._screenshot_callback = on_screenshot
        return self._screenshot_callback

    def _init_ui(self):
        """Build the settings dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._tabs.addTab(self._create_hotkeys_tab(), t("settings.hotkeys"))
        self._tabs.addTab(self._create_screenshot_tab(), t("settings.screenshot"))
        self._tabs.addTab(self._create_ai_tab(), t("settings.ai_service"))
        self._tabs.addTab(self._create_ocr_tab(), t("settings.ocr"))
        self._tabs.addTab(self._create_ui_tab(), t("settings.ui"))

        layout.addWidget(self._tabs)

        # Button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._reset_btn = QPushButton(t("settings.reset_default"))
        self._reset_btn.setObjectName("ghostBtn")
        self._reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(self._reset_btn)

        btn_layout.addStretch()

        self._cancel_btn = QPushButton(t("settings.cancel"))
        self._cancel_btn.setObjectName("secondaryBtn")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._apply_btn = QPushButton(t("settings.apply"))
        self._apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._apply_btn)

        self._save_btn = QPushButton(t("settings.save"))
        self._save_btn.setObjectName("secondaryBtn")
        self._save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self._save_btn)

        layout.addLayout(btn_layout)

        # Degraded services warning
        self._degraded_label = QLabel()
        self._degraded_label.setObjectName("warningLabel")
        self._degraded_label.setVisible(False)
        self._degraded_label.setWordWrap(True)
        layout.addWidget(self._degraded_label)

    def _section_description(self, text: str) -> QLabel:
        """Create a styled section description label."""
        label = QLabel(text)
        label.setObjectName("subtitle")
        label.setWordWrap(True)
        return label

    def _create_hotkeys_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 20, 16, 16)

        desc = self._section_description(t("settings.hotkey_desc"))
        layout.addRow(desc)

        self._hotkey_screenshot = HotkeyRecorder()
        layout.addRow(t("settings.hotkey_screenshot"), self._hotkey_screenshot)

        self._hotkey_search = HotkeyRecorder()
        layout.addRow(t("settings.hotkey_search"), self._hotkey_search)

        self._restore_hotkeys_btn = QPushButton(t("settings.reset_default"))
        self._restore_hotkeys_btn.setObjectName("ghostBtn")
        self._restore_hotkeys_btn.clicked.connect(self._reset_hotkeys_to_defaults)
        layout.addRow("", self._restore_hotkeys_btn)

        return widget

    def _create_screenshot_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 20, 16, 16)

        self._debounce_interval = QDoubleSpinBox()
        self._debounce_interval.setRange(0.1, 60.0)
        self._debounce_interval.setSingleStep(0.5)
        self._debounce_interval.setSuffix(" s")
        layout.addRow(t("settings.debounce_interval"), self._debounce_interval)

        self._cluster_threshold = QDoubleSpinBox()
        self._cluster_threshold.setRange(0.1, 30.0)
        self._cluster_threshold.setSingleStep(0.5)
        self._cluster_threshold.setSuffix(" s")
        layout.addRow(t("settings.cluster_threshold"), self._cluster_threshold)

        self._max_captures = QSpinBox()
        self._max_captures.setRange(1, 100)
        layout.addRow(t("settings.max_captures"), self._max_captures)

        return widget

    def _create_ai_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 20, 16, 16)

        self._ai_api_key = QLineEdit()
        self._ai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._ai_api_key.setPlaceholderText("sk-...")
        layout.addRow(t("settings.api_key"), self._ai_api_key)

        self._ai_model = QComboBox()
        self._ai_model.addItems([
            "gpt-4o-mini", "gpt-4o", "gpt-4-turbo",
            "claude-3-opus", "claude-3-sonnet",
        ])
        layout.addRow(t("settings.model"), self._ai_model)

        self._ai_timeout = QSpinBox()
        self._ai_timeout.setRange(10, 300)
        self._ai_timeout.setSuffix(" s")
        layout.addRow(t("settings.timeout"), self._ai_timeout)

        return widget

    def _create_ocr_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 20, 16, 16)

        self._ocr_engine = QComboBox()
        self._ocr_engine.addItems(["rapidocr", "tesseract", "easyocr"])
        layout.addRow(t("settings.ocr_engine"), self._ocr_engine)

        self._ocr_language = QComboBox()
        self._ocr_language.addItems(["ch", "en", "ch+en"])
        layout.addRow(t("settings.language"), self._ocr_language)

        return widget

    def _create_ui_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 20, 16, 16)

        self._ui_theme = QComboBox()
        self._ui_theme.addItems(["light", "dark", "system"])
        layout.addRow(t("settings.theme"), self._ui_theme)

        self._ui_auto_hide = QCheckBox(t("settings.auto_hide"))
        layout.addRow("", self._ui_auto_hide)

        self._ui_start_minimized = QCheckBox(t("settings.start_minimized"))
        layout.addRow("", self._ui_start_minimized)

        # Preview theme immediately button
        self._preview_btn = QPushButton(t("settings.preview_theme"))
        self._preview_btn.setObjectName("secondaryBtn")
        self._preview_btn.clicked.connect(self._on_preview_theme)
        layout.addRow("", self._preview_btn)

        return widget

    def _load_current_settings(self):
        """Populate UI fields from current settings."""
        settings = self._safe_get_settings()
        merged = copy.deepcopy(self._original_settings)
        merged.update(settings)
        self._original_settings = merged
        self._pending_settings = copy.deepcopy(merged)

        hotkeys = merged.get("hotkeys", {})
        self._hotkey_screenshot.set_pynput_hotkey(
            hotkeys.get("screenshot", DEFAULT_HOTKEYS["screenshot"])
        )
        self._hotkey_search.set_pynput_hotkey(
            hotkeys.get("search", DEFAULT_HOTKEYS["search"])
        )

        screenshot = merged.get("screenshot", {})
        self._debounce_interval.setValue(screenshot.get("debounce_interval", 5.0))
        self._cluster_threshold.setValue(screenshot.get("cluster_threshold", 2.0))
        self._max_captures.setValue(screenshot.get("max_captures_per_window", 10))

        ai = merged.get("ai", {})
        self._ai_api_key.setText(ai.get("api_key", ""))
        idx = self._ai_model.findText(ai.get("model", "gpt-4o-mini"))
        if idx >= 0:
            self._ai_model.setCurrentIndex(idx)
        self._ai_timeout.setValue(ai.get("timeout", 30))

        ocr = merged.get("ocr", {})
        idx = self._ocr_engine.findText(ocr.get("engine", "rapidocr"))
        if idx >= 0:
            self._ocr_engine.setCurrentIndex(idx)
        idx = self._ocr_language.findText(ocr.get("language", "ch"))
        if idx >= 0:
            self._ocr_language.setCurrentIndex(idx)

        ui = merged.get("ui", {})
        idx = self._ui_theme.findText(ui.get("theme", "light"))
        if idx >= 0:
            self._ui_theme.setCurrentIndex(idx)
        self._ui_auto_hide.setChecked(ui.get("auto_hide", False))
        self._ui_start_minimized.setChecked(ui.get("start_minimized", False))
        self._original_settings = self._collect_settings_from_ui()
        self._pending_settings = copy.deepcopy(self._original_settings)

    def _collect_settings_from_ui(self) -> dict:
        return {
            "hotkeys": {
                "screenshot": self._hotkey_screenshot.pynput_hotkey(),
                "search": self._hotkey_search.pynput_hotkey(),
            },
            "screenshot": {
                "debounce_interval": self._debounce_interval.value(),
                "cluster_threshold": self._cluster_threshold.value(),
                "max_captures_per_window": self._max_captures.value(),
            },
            "ai": {
                "api_key": self._ai_api_key.text(),
                "model": self._ai_model.currentText(),
                "timeout": self._ai_timeout.value(),
            },
            "ocr": {
                "engine": self._ocr_engine.currentText(),
                "language": self._ocr_language.currentText(),
            },
            "ui": {
                "theme": self._ui_theme.currentText(),
                "auto_hide": self._ui_auto_hide.isChecked(),
                "start_minimized": self._ui_start_minimized.isChecked(),
            },
        }

    def _on_preview_theme(self):
        """Preview theme change immediately."""
        theme = self._ui_theme.currentText()
        if self._theme_manager:
            self._theme_manager.apply_theme(theme)

    def _reset_hotkeys_to_defaults(self):
        self._hotkey_screenshot.set_pynput_hotkey(DEFAULT_HOTKEYS["screenshot"])
        self._hotkey_search.set_pynput_hotkey(DEFAULT_HOTKEYS["search"])

    def _on_reset(self):
        reply = QMessageBox.question(
            self,
            t("settings.confirm_reset"),
            t("settings.confirm_reset_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._settings_manager:
                try:
                    self._settings_manager.reset()
                except Exception:
                    pass
            self._original_settings = self._safe_get_settings()
            self._pending_settings = copy.deepcopy(self._original_settings)
            self._load_current_settings()
            self._degraded_services = []
            self._update_degraded_label()

    def _on_save(self) -> bool:
        new_settings = self._collect_settings_from_ui()
        if not self._validate_input(new_settings):
            return False
        if new_settings == self._original_settings:
            return True
        if self._settings_manager:
            try:
                self._settings_manager.update(new_settings)
            except Exception:
                pass
        self._pending_settings = new_settings
        self._original_settings = new_settings
        return True

    def _detect_conflicts(self, new_settings: dict) -> list:
        """Detect setting conflicts. Returns list of conflict description strings.

        Currently no known conflicts exist. Add conflict detection rules here
        as new inter-dependent settings are introduced.
        """
        conflicts = []
        return conflicts

    def _on_apply(self) -> bool:
        new_settings = self._collect_settings_from_ui()
        if not self._validate_input(new_settings):
            return False

        if new_settings == self._original_settings:
            self.accept()
            return True

        conflicts = self._detect_conflicts(new_settings)
        if conflicts:
            conflict_text = "\n".join(f"  {c}" for c in conflicts)
            reply = QMessageBox.question(
                self,
                t("settings.conflict_title"),
                f"{conflict_text}\n\n{t('settings.conflict_proceed')}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        if self._theme_manager:
            self._theme_manager.apply_theme(
                new_settings.get("ui", {}).get("theme", "light")
            )

        if self._settings_manager:
            try:
                self._settings_manager.update(new_settings)
            except Exception:
                pass

        self._apply_runtime_settings(new_settings)
        self._pending_settings = new_settings
        self._original_settings = new_settings

        if self._degraded_services:
            QMessageBox.warning(
                self, t("settings.apply_partial"), self._degraded_label.text()
            )
        self.accept()
        return True

    def _validate_input(self, settings: dict) -> bool:
        hotkeys = settings.get("hotkeys", {})
        hotkey_labels = {
            "screenshot": t("settings.hotkey_screenshot").rstrip(":"),
            "search": t("settings.hotkey_search").rstrip(":"),
        }
        for key, value in hotkeys.items():
            if not is_valid_pynput_hotkey(value, allow_empty=False):
                QMessageBox.warning(
                    self,
                    t("settings.validation_input_error"),
                    f"{t('settings.validation_hotkey_format', hotkey_name=hotkey_labels.get(key, key))}\n{t('settings.validation_hotkey_hint')}"
                )
                return False

        ai = settings.get("ai", {})
        api_key = ai.get("api_key", "")
        if api_key and len(api_key.strip()) == 0:
            QMessageBox.warning(self, t("settings.validation_input_error"), t("settings.validation_api_key"))
            return False

        screenshot = settings.get("screenshot", {})
        if screenshot.get("debounce_interval", 1) <= 0:
            QMessageBox.warning(self, t("settings.validation_input_error"), t("settings.validation_debounce"))
            return False
        if screenshot.get("max_captures_per_window", 1) <= 0:
            QMessageBox.warning(self, t("settings.validation_input_error"), t("settings.validation_max_captures"))
            return False

        return True

    def _apply_runtime_settings(self, settings: dict) -> None:
        degraded = []

        if self._capture_manager:
            try:
                screenshot_settings = settings.get("screenshot", {})
                if not self._capture_manager.update_settings(screenshot_settings):
                    degraded.append("capture")
            except Exception:
                degraded.append("capture")

        self._degraded_services = degraded
        self._update_degraded_label()

    def _update_degraded_label(self):
        if self._degraded_services:
            self._degraded_label.setText(
                f"{t('settings.degraded_prefix')}{', '.join(self._degraded_services)}"
            )
            self._degraded_label.setVisible(True)
        else:
            self._degraded_label.setVisible(False)

    def get_degraded_services(self) -> list:
        return self._degraded_services.copy()

    def closeEvent(self, event):
        current_settings = self._collect_settings_from_ui()
        if current_settings != self._original_settings:
            reply = QMessageBox.question(
                self,
                t("settings.confirm_close"),
                t("settings.confirm_close_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()
