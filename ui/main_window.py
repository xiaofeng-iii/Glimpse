"""
MainWindow - 主窗体与布局
Polished with QSS theming, i18n, and modern card-based layout.
Inspired by Floral Notepaper's MainWindow component.
"""
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QTextEdit, QSystemTrayIcon, QMenu, QApplication, QComboBox,
    QFrame, QSizePolicy, QSpacerItem, QStackedWidget, QMessageBox,
    QCheckBox
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import (
    QAction, QShortcut, QKeySequence, QPixmap, QFont, QColor, QPainter
)

from ui.signals import signals
from ui.settings_dialog import SettingsDialog
from ui.locale_manager import t, locale_manager
from ui.theme_manager import ThemeManager
from ui.memory_detail_dialog import MemoryDetailDialog
from ui.qt_event_bridge import QtEventBridge
from ui.widgets.loading_spinner import LoadingSpinner
from ui.widgets.segmented_filter import SegmentedFilterControl
from ui.app_icon import create_app_icon
from container import container


# ============================================================
# Empty State Widget
# ============================================================

class EmptyStateWidget(QWidget):
    """Placeholder shown when there are no memories."""

    def __init__(self, is_search: bool = False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(
            t("detail.no_memories") if not is_search else t("detail.no_results")
        )
        title_label.setObjectName("sectionTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        if not is_search:
            hint_label = QLabel("Ctrl+Shift+G")
            hint_label.setObjectName("subtitle")
            hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(hint_label)


# ============================================================
# Memory List Item Delegate
# ============================================================

def _make_thumbnail_placeholder() -> QPixmap:
    """Generate a tiny placeholder icon for memory list items."""
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#E2E8F0"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 40, 40, 6, 6)
    # Simple image icon
    painter.setPen(QColor("#94A3B8"))
    painter.drawRect(10, 10, 20, 16)
    painter.drawEllipse(15, 13, 4, 4)
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPolygonF
    painter.drawPolygon([QPointF(14, 26), QPointF(20, 20), QPointF(26, 26)])
    painter.end()
    return pixmap


def _display_app_name(memory) -> str:
    """Return a displayable app name, hiding placeholder values."""
    app_name = (getattr(memory, "app_name", "") or "").strip()
    if not app_name or app_name.lower() == "unknown":
        return ""
    return app_name


class MemoryListItemWidget(QWidget):
    """Custom widget for each memory list item with styled badges and thumbnail."""

    def __init__(self, memory, parent=None):
        super().__init__(parent)
        self.setObjectName("memoryListItem")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 12, 8)
        layout.setSpacing(10)

        # Thumbnail
        thumb_label = QLabel()
        thumb_label.setFixedSize(40, 40)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        image_path = getattr(memory, "image_path", "")
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                thumb_label.setPixmap(
                    pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
                )
            else:
                thumb_label.setPixmap(_make_thumbnail_placeholder())
        else:
            thumb_label.setPixmap(_make_thumbnail_placeholder())

        layout.addWidget(thumb_label)

        # Middle: badges + content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)

        # Top row: badges + time
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # Add styled badge labels
        match_sources = getattr(memory, "match_sources", [])
        if "精确" in match_sources:
            exact_badge = QLabel(t("badges.exact"))
            exact_badge.setObjectName("exactBadge")
            top_row.addWidget(exact_badge)
        if "语义" in match_sources:
            semantic_badge = QLabel(t("badges.semantic"))
            semantic_badge.setObjectName("semanticBadge")
            top_row.addWidget(semantic_badge)

        top_row.addStretch()

        # Time label
        time_str = memory.created_at[:19] if hasattr(memory, "created_at") else ""
        time_label = QLabel(time_str)
        time_label.setObjectName("subtitle")
        time_label.setFont(QFont(("Segoe UI"), 11))
        top_row.addWidget(time_label)

        content_layout.addLayout(top_row)

        # Bottom: summary text
        summary_text = (
            memory.ai_summary[:80] + "..."
            if hasattr(memory, "ai_summary") and memory.ai_summary
            else ""
        )
        summary_label = QLabel(summary_text)
        summary_label.setFont(QFont(("Segoe UI"), 13))
        summary_label.setWordWrap(True)
        content_layout.addWidget(summary_label)

        layout.addLayout(content_layout, 1)

        # Right: app name chip
        app_name = _display_app_name(memory)
        if app_name:
            app_chip = QLabel(app_name)
            app_chip.setObjectName("appChip")
            app_chip.setProperty("appName", True)
            layout.addWidget(app_chip, 0, Qt.AlignmentFlag.AlignTop)


# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow):
    """Main application window with modern styling."""

    def __init__(self, theme_manager: ThemeManager | None = None):
        super().__init__()
        self.setWindowTitle(t("app.title"))
        self._app_icon = create_app_icon()
        self.setWindowIcon(self._app_icon)
        self.setMinimumSize(960, 640)
        self.resize(1100, 720)

        self._current_memories = []
        self._theme_manager = theme_manager
        self._current_theme = "light"

        # Search debounce timer
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)

        self._setup_ui()
        self._setup_shortcuts()
        self._setup_tray_icon()
        self._setup_menu_bar()
        self._connect_signals()

        # Add loading spinner overlay
        self._loading_spinner = LoadingSpinner(self.centralWidget())
        self._loading_spinner.setVisible(False)

        # Apply initial theme from settings
        self._load_initial_theme()

        # Load initial data
        self._load_memories()

        # Update UI text from locale
        self._refresh_i18n()

    # ============================================================
    # UI Setup
    # ============================================================

    def _setup_ui(self):
        """Build the main window layout with card-style containers."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout with generous margins
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # --- Toolbar Card ---
        toolbar_card = QFrame()
        toolbar_card.setObjectName("toolbarWidget")
        toolbar_layout = QVBoxLayout(toolbar_card)
        toolbar_layout.setContentsMargins(16, 12, 16, 12)
        toolbar_layout.setSpacing(10)

        # Top row: title + screenshot button
        top_toolbar_row = QHBoxLayout()
        top_toolbar_row.setSpacing(12)

        # App title label
        title_label = QLabel("Glimpse")
        title_label.setObjectName("sectionTitle")
        title_label.setFont(QFont(("Segoe UI"), 18))
        top_toolbar_row.addWidget(title_label)

        top_toolbar_row.addStretch()

        # Screenshot button
        self.screenshot_btn = QPushButton(t('toolbar.screenshot'))
        self.screenshot_btn.setObjectName("screenshotBtn")
        self.screenshot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.screenshot_btn.setToolTip(t("tooltips.screenshot"))
        self.screenshot_btn.clicked.connect(self._on_screenshot)
        top_toolbar_row.addWidget(self.screenshot_btn)

        # Settings button (icon-style)
        self.settings_btn = QPushButton(t("menu.settings"))
        self.settings_btn.setObjectName("secondaryBtn")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setToolTip(t("tooltips.settings"))
        self.settings_btn.clicked.connect(self._on_open_settings)
        top_toolbar_row.addWidget(self.settings_btn)

        toolbar_layout.addLayout(top_toolbar_row)

        # Search bar row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.source_filter_group = SegmentedFilterControl()
        self.source_filter_group.set_labels(
            {
                "all": t("toolbar.source_all"),
                "exact": t("toolbar.source_exact"),
                "semantic": t("toolbar.source_semantic"),
            },
            {
                "all": t("tooltips.source_all"),
                "exact": t("tooltips.source_exact"),
                "semantic": t("tooltips.source_semantic"),
            },
        )
        self.source_filter_group.source_selected.connect(self._on_filter_clicked)

        search_row.addWidget(self.source_filter_group)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("toolbar.search_placeholder"))
        self.search_input.setObjectName("searchInput")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setToolTip(t("tooltips.search"))
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.search_input, 1)

        toolbar_layout.addLayout(search_row)
        main_layout.addWidget(toolbar_card)

        # --- Content Area (split: list + detail) ---
        content_split = QHBoxLayout()
        content_split.setSpacing(12)

        # Left: Memory list card
        list_card = QFrame()
        list_card.setObjectName("toolbarWidget")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(8, 8, 8, 8)

        # Stack: list or empty state
        self.list_stack = QStackedWidget()

        self.memory_list = QListWidget()
        self.memory_list.setObjectName("memoryList")
        self.memory_list.itemClicked.connect(self._on_memory_selected)
        self.memory_list.itemDoubleClicked.connect(self._on_memory_double_clicked)
        self.memory_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.memory_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.memory_list.setToolTip(t("tooltips.memory_item"))
        self.list_stack.addWidget(self.memory_list)  # index 0

        self.empty_state = EmptyStateWidget(is_search=False)
        self.list_stack.addWidget(self.empty_state)  # index 1

        self.empty_search_state = EmptyStateWidget(is_search=True)
        self.list_stack.addWidget(self.empty_search_state)  # index 2

        list_layout.addWidget(self.list_stack)

        # Count label
        self.list_count_label = QLabel("")
        self.list_count_label.setObjectName("subtitle")
        list_layout.addWidget(self.list_count_label)

        content_split.addWidget(list_card, 3)

        # Right: Detail panel card
        detail_card = QFrame()
        detail_card.setObjectName("toolbarWidget")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)

        detail_header = QLabel(t("detail.summary"))
        detail_header.setObjectName("sectionTitle")
        detail_header.setFont(QFont(("Segoe UI"), 14))
        detail_layout.addWidget(detail_header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        detail_layout.addWidget(sep)

        self.detail_panel = QTextEdit()
        self.detail_panel.setReadOnly(True)
        self.detail_panel.setObjectName("detailPanel")
        self.detail_panel.setFont(QFont(("Segoe UI"), 13))
        detail_layout.addWidget(self.detail_panel, 1)

        content_split.addWidget(detail_card, 2)
        main_layout.addLayout(content_split, 1)

        # --- Status Bar ---
        self.status_label = QLabel(t("status.ready"))
        self.status_label.setObjectName("subtitle")
        self.statusBar().addWidget(self.status_label)

        # Cluster buttons in status bar
        self._cluster_submit_btn = QPushButton(t("status.cluster_submit"))
        self._cluster_submit_btn.clicked.connect(self._on_cluster_submit)
        self._cluster_submit_btn.setVisible(False)
        self._cluster_submit_btn.setToolTip(t("tooltips.cluster_submit"))
        self.statusBar().addPermanentWidget(self._cluster_submit_btn)

        self._cluster_cancel_btn = QPushButton(t("status.cluster_cancel"))
        self._cluster_cancel_btn.setObjectName("clusterCancelBtn")
        self._cluster_cancel_btn.clicked.connect(self._on_cluster_cancel)
        self._cluster_cancel_btn.setToolTip(t("tooltips.cluster_cancel"))
        self._cluster_cancel_btn.setVisible(False)
        self.statusBar().addPermanentWidget(self._cluster_cancel_btn)

    def _setup_shortcuts(self):
        """Register keyboard shortcuts."""
        self.search_shortcut = QShortcut(QKeySequence(), self)
        self.search_shortcut.activated.connect(lambda: self.search_input.setFocus())

        self.screenshot_shortcut = QShortcut(QKeySequence(), self)
        self.screenshot_shortcut.activated.connect(self._on_screenshot)

        self.clear_shortcut = QShortcut(QKeySequence(), self)
        self.clear_shortcut.activated.connect(self._clear_search)

        self._update_shortcut_hints()

    def _update_shortcut_hints(self):
        """Update UI hints and shortcut bindings from settings."""
        try:
            settings_manager = container.get("settings_manager")
            screenshot_pynput = settings_manager.get("hotkeys.screenshot", "<ctrl>+<shift>+g")
            search_pynput = settings_manager.get("hotkeys.search", "<ctrl>+f")

            from services.hotkey_utils import pynput_to_qkeysequence
            screenshot_qt = pynput_to_qkeysequence(screenshot_pynput)
            search_qt = pynput_to_qkeysequence(search_pynput)

            self.screenshot_btn.setText(f"{t('toolbar.screenshot')} ({screenshot_qt})")
            self.search_input.setPlaceholderText(
                f"{t('toolbar.search_placeholder')} ({search_qt})"
            )

            if hasattr(self, "screenshot_shortcut"):
                self.screenshot_shortcut.setKey(QKeySequence(screenshot_qt))
            if hasattr(self, "search_shortcut"):
                self.search_shortcut.setKey(QKeySequence(search_qt))
            if hasattr(self, "clear_shortcut"):
                self.clear_shortcut.setKey(QKeySequence("Esc"))
        except Exception:
            pass  # Backend not wired yet; use defaults

    def _setup_tray_icon(self):
        """Initialize system tray with polished icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("Warning: System tray not available")
            self.tray_icon = None
            return

        icon = self._app_icon
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip(t("app.title"))
        self.tray_icon.activated.connect(self._on_tray_activated)

        tray_menu = QMenu()

        show_action = QAction(t("tray.show"), self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction(t("tray.quit"), self)
        quit_action.triggered.connect(self._on_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def _setup_menu_bar(self):
        """Build the menu bar."""
        file_menu = self.menuBar().addMenu(t("menu.file"))

        settings_action = QAction(t("menu.settings"), self)
        settings_action.triggered.connect(self._on_open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction(t("menu.quit"), self)
        quit_action.triggered.connect(self._on_quit)
        file_menu.addAction(quit_action)

    def _connect_signals(self):
        """Wire global signals to slots."""
        cluster_buffer = None
        try:
            cluster_buffer = container.get("cluster_buffer")
        except Exception:
            pass

        self._event_bridge = QtEventBridge(cluster_buffer=cluster_buffer, parent=self)
        self._event_bridge.screenshot_requested.connect(self._on_screenshot)
        self._event_bridge.screenshot_completed.connect(self._on_screenshot_complete)
        self._event_bridge.memory_saved.connect(self._on_memory_saved)
        self._event_bridge.search_completed.connect(self._on_search_completed)
        self._event_bridge.error_occurred.connect(self._on_error)
        self._event_bridge.status_updated.connect(self._on_status_updated)

        if cluster_buffer is not None:
            self._event_bridge.cluster_state_changed.connect(self._on_cluster_state_changed)
            self._event_bridge.cluster_countdown_changed.connect(self._on_cluster_countdown)
            self._event_bridge.cluster_flushed.connect(self._on_cluster_flushed)
            self._event_bridge.cluster_discarded.connect(self._on_cluster_discarded)

    # ============================================================
    # Theme
    # ============================================================

    def _load_initial_theme(self):
        """Load theme from settings and apply."""
        try:
            settings_manager = container.get("settings_manager")
            theme = settings_manager.get("ui.theme", "light")
            self._apply_theme(theme)
        except Exception:
            self._apply_theme("light")

    def _apply_theme(self, theme_name: str):
        """Apply QSS theme and update tray icon."""
        if self._theme_manager:
            actual = self._theme_manager.apply_theme(theme_name)
        else:
            from ui.theme_manager import apply_theme
            actual = apply_theme(QApplication.instance(), theme_name)
        self._current_theme = actual

        # Refresh tray icon for theme
        if self.tray_icon:
            self.tray_icon.setIcon(self._app_icon)

    # ============================================================
    # i18n
    # ============================================================

    def _refresh_i18n(self):
        """Refresh all UI strings after locale change."""
        self.setWindowTitle(t("app.title"))
        self.source_filter_group.set_labels(
            {
                "all": t("toolbar.source_all"),
                "exact": t("toolbar.source_exact"),
                "semantic": t("toolbar.source_semantic"),
            },
            {
                "all": t("tooltips.source_all"),
                "exact": t("tooltips.source_exact"),
                "semantic": t("tooltips.source_semantic"),
            },
        )
        self.status_label.setText(t("status.ready"))
        self.settings_btn.setText(t("menu.settings"))
        self._cluster_submit_btn.setText(t("status.cluster_submit"))
        self._cluster_cancel_btn.setText(t("status.cluster_cancel"))
        self._update_memory_list()
        self._update_shortcut_hints()

    # ============================================================
    # Memory List
    # ============================================================

    def _load_memories(self):
        try:
            search_service = container.get("search_service")
            self._current_memories = search_service.get_recent_memories(limit=100)
        except Exception:
            self._current_memories = []
        self._update_memory_list()

    def _update_memory_list(self):
        """Render memory items with custom styled widgets."""
        self.memory_list.clear()

        if not self._current_memories:
            # Show empty state
            has_search = bool(self.search_input.text().strip())
            self.list_stack.setCurrentIndex(2 if has_search else 1)
            self.list_count_label.setText("")
            return

        self.list_stack.setCurrentIndex(0)
        self.list_count_label.setText(t("detail.items_count", count=len(self._current_memories)))

        for memory in self._current_memories:
            item = QListWidgetItem()
            widget = MemoryListItemWidget(memory)
            item.setSizeHint(widget.sizeHint())
            self.memory_list.addItem(item)
            self.memory_list.setItemWidget(item, widget)

    def _on_memory_selected(self, item):
        index = self.memory_list.row(item)
        if 0 <= index < len(self._current_memories):
            memory = self._current_memories[index]
            app_name = _display_app_name(memory)
            app_row = (
                f"""
                <p style="color: #64748B; margin-bottom: 4px;">
                    <b>{t('detail.app')}:</b> {app_name}
                </p>
                """
                if app_name else ""
            )
            detail_html = f"""
            <div style="font-family: 'Segoe UI', 'PingFang SC', sans-serif;">
                <p style="color: #64748B; margin-bottom: 4px;">
                    <b>{t('detail.time')}:</b> {memory.created_at}
                </p>
                {app_row}
                <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 8px 0;">
                <p style="line-height: 1.8; margin-top: 8px;">
                    {memory.ai_summary}
                </p>
                <p style="color: #94A3B8; font-size: 12px; margin-top: 12px;">
                    <b>{t('detail.image')}:</b> {memory.image_path}
                </p>
            </div>
            """
            self.detail_panel.setHtml(detail_html)

    def _on_memory_double_clicked(self, item):
        """Open memory detail dialog on double-click."""
        index = self.memory_list.row(item)
        if 0 <= index < len(self._current_memories):
            dialog = MemoryDetailDialog(self._current_memories[index], self)
            if dialog.exec():
                # Dialog was accepted (e.g., delete), refresh list
                self._load_memories()

    # ============================================================
    # Loading
    # ============================================================

    def _show_loading(self, text: str = ""):
        """Show the loading spinner overlay."""
        if text:
            self._loading_spinner.set_text(text)
        self._loading_spinner.setGeometry(self.centralWidget().rect())
        self._loading_spinner.show()

    def _hide_loading(self):
        """Hide the loading spinner overlay."""
        self._loading_spinner.hide()

    # ============================================================
    # Search
    # ============================================================

    def _on_search_text_changed(self, text: str):
        self._search_timer.start(300)
        if text.strip():
            self._show_loading(t("status.searching"))

    def _on_filter_clicked(self, source: str):
        """Handle filter button toggle."""
        self._active_source_filter = source
        self._show_loading(t("status.searching"))
        self._do_search()

    def _do_search(self):
        query = self.search_input.text().strip()
        try:
            search_service = container.get("search_service")
            if not query:
                self._current_memories = search_service.get_recent_memories(limit=100)
            else:
                source_filter = self.source_filter_group.active_source()
                self._current_memories = search_service.search(query, source_filter=source_filter)
        except Exception:
            self._current_memories = []
        self._update_memory_list()
        self._hide_loading()

    def _clear_search(self):
        self.search_input.clear()
        self._do_search()

    # ============================================================
    # Screenshot
    # ============================================================

    def _on_screenshot(self):
        try:
            settings_manager = container.get("settings_manager")
            cluster_mode = settings_manager.get("cluster.cluster_mode", False)
            cluster_buffer = container.get("cluster_buffer")
            bypass_debounce = cluster_mode and cluster_buffer.is_collecting()
        except Exception:
            cluster_mode = False
            bypass_debounce = False

        self.status_label.setText(t("status.capturing"))
        was_visible = self.isVisible()
        if was_visible:
            self.hide()

        def do_capture():
            try:
                capture_manager = container.get("capture_manager")
                result = capture_manager.capture_fullscreen(force_bypass_debounce=bypass_debounce)
            except Exception as e:
                self.status_label.setText(f"{t('status.error_prefix')}: {e}")
                signals.error_occurred.emit(f"Screenshot error: {e}")
                if was_visible:
                    self.show()
                    self.activateWindow()
                return

            if was_visible:
                self.show()
                self.activateWindow()

            if result is None:
                self.status_label.setText(
                    t("status.cluster_max_rate") if bypass_debounce
                    else t("status.capture_too_fast")
                )
                return

            if cluster_mode:
                try:
                    container.get("cluster_buffer").add_image(result.image_path)
                except Exception:
                    self._process_single_screenshot(result)
            else:
                self._process_single_screenshot(result)

        QTimer.singleShot(250, do_capture)

    def _process_single_screenshot(self, result):
        self.status_label.setText(t("status.analyzing"))
        self._show_loading(t("status.analyzing"))
        signals.screenshot_completed.emit(result.image_path)

        try:
            memory_service = container.get("memory_service")

            def _on_complete(memory_id):
                self._hide_loading()
                if memory_id:
                    self.status_label.setText(f"{t('status.saved')}: {memory_id[:8]}...")
                    signals.memory_saved.emit(memory_id)
                else:
                    self.status_label.setText(t("status.save_failed"))

            def _on_error(error_msg):
                self._hide_loading()
                self.status_label.setText(f"{t('status.analysis_failed')}: {error_msg}")
                signals.error_occurred.emit(f"Memory creation error: {error_msg}")

            memory_service.create_memory_async(
                result.image_path,
                app_name=result.app_name or "unknown",
                on_complete=_on_complete,
                on_error=_on_error,
            )
        except Exception:
            self.status_label.setText(t("status.save_failed"))

    # ============================================================
    # Signal Handlers
    # ============================================================

    def _on_screenshot_complete(self, image_path: str):
        self.status_label.setText(f"{t('status.saved')}: {image_path}")

    def _on_memory_saved(self, memory_id: str):
        self.status_label.setText(f"{t('status.saved')}: {memory_id}")
        self._load_memories()

    def _on_search_completed(self, results: list):
        self._current_memories = results
        self._update_memory_list()

    def _on_error(self, error_msg: str):
        self.status_label.setText(f"{t('status.error_prefix')}: {error_msg}")

    def _on_status_updated(self, status: str):
        self.status_label.setText(status)

    # ============================================================
    # Cluster Mode
    # ============================================================

    def _on_cluster_state_changed(self, state: str, count: int, max_count: int):
        if state == "COLLECTING":
            self._cluster_submit_btn.setVisible(True)
            self._cluster_cancel_btn.setVisible(True)
            self.status_label.setText(
                t("status.cluster_collecting", count=count, max=max_count)
            )
        else:
            self._cluster_submit_btn.setVisible(False)
            self._cluster_cancel_btn.setVisible(False)

    def _on_cluster_countdown(self, seconds: int):
        try:
            settings_manager = container.get("settings_manager")
            auto_submit = settings_manager.get("cluster.cluster_auto_submit", True)
            if not auto_submit:
                return
            if seconds > 0:
                self.status_label.setText(
                    self.status_label.text().split("(")[0].strip()
                    + f" ({seconds}s {t('status.cluster_countdown', seconds=seconds).rsplit('(', 1)[-1]}"
                )
        except Exception:
            pass

    def _on_cluster_flushed(self, image_paths: list):
        self.status_label.setText(t("status.cluster_analyzing"))
        try:
            memory_service = container.get("memory_service")

            def _on_complete(memory_id):
                if memory_id:
                    self.status_label.setText(f"{t('status.cluster_saved')}: {memory_id[:8]}...")
                    signals.memory_saved.emit(memory_id)
                else:
                    self.status_label.setText(t("status.save_failed"))

            def _on_error(error_msg):
                self.status_label.setText(f"{t('status.analysis_failed')}: {error_msg}")
                signals.error_occurred.emit(f"Cluster memory error: {error_msg}")

            memory_service.create_cluster_memory_async(
                image_paths,
                app_name="unknown",
                on_complete=_on_complete,
                on_error=_on_error,
            )
        except Exception:
            self.status_label.setText(t("status.save_failed"))

    def _on_cluster_discarded(self):
        self.status_label.setText(t("status.cluster_cancelled"))

    def _on_cluster_submit(self):
        try:
            container.get("cluster_buffer").flush()
        except Exception:
            pass

    def _on_cluster_cancel(self):
        try:
            container.get("cluster_buffer").discard()
        except Exception:
            pass

    # ============================================================
    # Settings
    # ============================================================

    def _on_open_settings(self):
        keyboard_manager = None
        try:
            keyboard_manager = container.get("keyboard_manager")
            keyboard_manager.stop_listening()
        except Exception:
            pass

        try:
            dialog = SettingsDialog(
                container.get("settings_manager"),
                keyboard_manager,
                container.get("capture_manager"),
                container.get("task_queue"),
                self,
                ai_client=container.get("ai_client"),
                theme_manager=self._theme_manager,
            )
        except Exception:
            dialog = SettingsDialog(
                None, None, None, None, self,
                theme_manager=self._theme_manager,
            )
        try:
            dialog.exec()
        finally:
            self._reload_global_screenshot_hotkey(keyboard_manager)
            self._refresh_i18n()

        # Reload theme from settings
        try:
            settings_manager = container.get("settings_manager")
            theme = settings_manager.get("ui.theme", "light")
            self._apply_theme(theme)
        except Exception:
            pass

    def _reload_global_screenshot_hotkey(self, keyboard_manager=None):
        try:
            if keyboard_manager is None:
                keyboard_manager = container.get("keyboard_manager")
            settings_manager = container.get("settings_manager")
            screenshot_hotkey = settings_manager.get("hotkeys.screenshot", "<ctrl>+<shift>+g")

            def on_screenshot():
                signals.screenshot_requested.emit()

            keyboard_manager.reload_hotkeys({screenshot_hotkey: on_screenshot})
        except Exception:
            pass

    # ============================================================
    # Window & Tray
    # ============================================================

    def _on_tray_activated(self, reason):
        if self.tray_icon is None:
            return
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()
            self.activateWindow()

    def _on_quit(self):
        if self.tray_icon is not None:
            self.tray_icon.hide()
        try:
            container.get("keyboard_manager").stop_listening()
            container.get("task_queue").shutdown()
            container.get("capture_manager").close()
        except Exception:
            pass
        QApplication.instance().quit()

    def _get_close_action(self) -> str:
        try:
            settings_manager = container.get("settings_manager")
            action = settings_manager.get("ui.close_action", "ask")
        except Exception:
            action = "ask"
        return action if action in {"ask", "minimize", "exit"} else "ask"

    def _save_close_action(self, action: str) -> None:
        if action not in {"ask", "minimize", "exit"}:
            return
        try:
            settings_manager = container.get("settings_manager")
            settings_manager.set("ui.close_action", action)
        except Exception:
            pass

    def _minimize_to_tray(self) -> None:
        self.hide()
        if self.tray_icon is not None:
            self.tray_icon.showMessage(
                t("tray.minimized_title"),
                t("tray.minimized_msg"),
                self._app_icon,
                2000,
            )

    def resizeEvent(self, event):
        """Keep loading spinner sized to the central widget."""
        super().resizeEvent(event)
        if hasattr(self, "_loading_spinner") and self._loading_spinner.isVisible():
            self._loading_spinner.setGeometry(self.centralWidget().rect())

    def closeEvent(self, event):
        if self.tray_icon is None:
            self._on_quit()
            return

        close_action = self._get_close_action()
        if close_action == "exit":
            event.accept()
            self._on_quit()
            return

        if close_action == "minimize":
            event.ignore()
            self._minimize_to_tray()
            return

        event.ignore()
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle(t("close.title"))
        dialog.setText(t("close.message"))
        dialog.setInformativeText(t("close.detail"))

        minimize_btn = dialog.addButton(
            t("close.minimize"), QMessageBox.ButtonRole.AcceptRole
        )
        exit_btn = dialog.addButton(
            t("close.exit"), QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_btn = dialog.addButton(
            t("settings.cancel"), QMessageBox.ButtonRole.RejectRole
        )
        dialog.setDefaultButton(minimize_btn)

        remember_checkbox = QCheckBox(t("close.remember"))
        dialog.setCheckBox(remember_checkbox)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked == minimize_btn:
            if remember_checkbox.isChecked():
                self._save_close_action("minimize")
            self._minimize_to_tray()
        elif clicked == exit_btn:
            if remember_checkbox.isChecked():
                self._save_close_action("exit")
            self._on_quit()
        elif clicked == cancel_btn:
            return
