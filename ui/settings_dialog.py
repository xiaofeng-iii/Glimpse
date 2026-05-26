"""
Settings Dialog - polished with QSS styling and i18n support.
Inspired by Floral Notepaper's SettingsPanel component.
"""
import copy
import re
from typing import Dict, Any, Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QFormLayout, QLineEdit, QSpinBox,
    QDoubleSpinBox, QComboBox, QCheckBox, QPushButton,
    QLabel, QMessageBox, QGroupBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.locale_manager import t
from ui.theme_manager import ThemeManager


class SettingsDialog(QDialog):
    """Polished settings dialog with tabbed interface."""

    HOTKEY_PATTERN = re.compile(r'^(<[^>]+>(\+<[^>]+>)*|\w+)$')

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
            "hotkeys": {"screenshot": "", "search": "", "clear": ""},
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
                    from core.capture import capture_manager
                    capture_manager.capture_fullscreen()
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

        self._hotkey_screenshot = QLineEdit()
        self._hotkey_screenshot.setPlaceholderText("<ctrl>+<shift>+g")
        layout.addRow(t("settings.hotkey_screenshot"), self._hotkey_screenshot)

        self._hotkey_search = QLineEdit()
        self._hotkey_search.setPlaceholderText("<ctrl>+f")
        layout.addRow(t("settings.hotkey_search"), self._hotkey_search)

        self._hotkey_clear = QLineEdit()
        self._hotkey_clear.setPlaceholderText("<escape>")
        layout.addRow(t("settings.hotkey_clear"), self._hotkey_clear)

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
        self._hotkey_screenshot.setText(hotkeys.get("screenshot", ""))
        self._hotkey_search.setText(hotkeys.get("search", ""))
        self._hotkey_clear.setText(hotkeys.get("clear", ""))

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

    def _collect_settings_from_ui(self) -> dict:
        return {
            "hotkeys": {
                "screenshot": self._hotkey_screenshot.text(),
                "search": self._hotkey_search.text(),
                "clear": self._hotkey_clear.text(),
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
        if self._settings_manager:
            try:
                if self._settings_manager.update(new_settings):
                    self._pending_settings = new_settings
                    self._original_settings = new_settings
                    QMessageBox.information(
                        self, t("settings.save_success"), t("settings.save_success_msg")
                    )
                    return True
            except Exception:
                pass
        self._pending_settings = new_settings
        self._original_settings = new_settings
        QMessageBox.information(
            self, t("settings.save_success"), t("settings.save_success_msg")
        )
        return True

    def _on_apply(self) -> bool:
        new_settings = self._collect_settings_from_ui()
        if not self._validate_input(new_settings):
            return False

        if new_settings == self._original_settings:
            QMessageBox.information(
                self, t("settings.no_changes"), t("settings.no_changes_msg")
            )
            return True

        reply = QMessageBox.question(
            self,
            t("settings.confirm_apply"),
            t("settings.confirm_apply_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False

        # Apply theme immediately
        if self._theme_manager:
            self._theme_manager.apply_theme(
                new_settings.get("ui", {}).get("theme", "light")
            )

        if self._settings_manager:
            try:
                self._settings_manager.update(new_settings)
            except Exception:
                pass

        self._pending_settings = new_settings
        self._original_settings = new_settings
        QMessageBox.information(
            self, t("settings.apply_success"), t("settings.apply_success_msg")
        )
        return True

    def _validate_input(self, settings: dict) -> bool:
        hotkeys = settings.get("hotkeys", {})
        for key, value in hotkeys.items():
            if value and not self.HOTKEY_PATTERN.match(value):
                QMessageBox.warning(
                    self,
                    t("settings.validation_input_error"),
                    f"{t('settings.validation_hotkey_format', hotkey_name=key)}\n{t('settings.validation_hotkey_hint')}"
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
