"""
Main Window - 主窗体与布局
"""
import sys
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QListWidget, QTextEdit, QSystemTrayIcon, QMenu, QApplication, QComboBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QShortcut, QKeySequence, QIcon, QPixmap

from ui.signals import signals
from ui.settings_dialog import SettingsDialog
from container import container


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Glimpse - AI 桌面记忆助手")
        self.setMinimumSize(900, 600)

        self._current_memories = []
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)

        self._setup_ui()
        self._setup_shortcuts()
        self._setup_tray_icon()
        self._setup_menu_bar()
        self._connect_signals()
        self._load_memories()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        toolbar = QWidget()
        toolbar_layout = QVBoxLayout(toolbar)

        self.screenshot_btn = QPushButton("截图 (Ctrl+Shift+G)")
        self.screenshot_btn.clicked.connect(self._on_screenshot)
        toolbar_layout.addWidget(self.screenshot_btn)

        search_layout = QHBoxLayout()
        
        self.source_filter_combo = QComboBox()
        self.source_filter_combo.addItem("综合结果", "all")
        self.source_filter_combo.addItem("仅看 OCR", "ocr")
        self.source_filter_combo.addItem("仅看语义", "semantic")
        self.source_filter_combo.currentIndexChanged.connect(self._on_source_filter_changed)
        search_layout.addWidget(self.source_filter_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索记忆... (Ctrl+F)")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_input)
        
        toolbar_layout.addLayout(search_layout)

        layout.addWidget(toolbar)

        self.memory_list = QListWidget()
        self.memory_list.itemClicked.connect(self._on_memory_selected)
        layout.addWidget(self.memory_list)

        self.detail_panel = QTextEdit()
        self.detail_panel.setReadOnly(True)
        layout.addWidget(self.detail_panel)

        self.status_bar = QLabel("就绪")
        self.statusBar().addWidget(self.status_bar)

        # 集群截图按钮（初始隐藏）
        self._cluster_submit_btn = QPushButton("立即提交")
        self._cluster_submit_btn.clicked.connect(self._on_cluster_submit)
        self._cluster_submit_btn.setVisible(False)
        self.statusBar().addPermanentWidget(self._cluster_submit_btn)

        self._cluster_cancel_btn = QPushButton("取消")
        self._cluster_cancel_btn.clicked.connect(self._on_cluster_cancel)
        self._cluster_cancel_btn.setVisible(False)
        self.statusBar().addPermanentWidget(self._cluster_cancel_btn)

    def _setup_shortcuts(self):
        self.search_shortcut = QShortcut(QKeySequence(), self)
        self.search_shortcut.activated.connect(lambda: self.search_input.setFocus())

        self.screenshot_shortcut = QShortcut(QKeySequence(), self)
        self.screenshot_shortcut.activated.connect(self._on_screenshot)

        self.clear_shortcut = QShortcut(QKeySequence(), self)
        self.clear_shortcut.activated.connect(self._clear_search)

        self._update_shortcut_hints()

    def _update_shortcut_hints(self):
        """从 settings_manager 更新 UI 文本和快捷键"""
        settings_manager = container.get("settings_manager")
        
        # 读取快捷键配置
        screenshot_pynput = settings_manager.get("hotkeys.screenshot", "<ctrl>+<shift>+g")
        search_pynput = settings_manager.get("hotkeys.search", "<ctrl>+f")
        clear_pynput = settings_manager.get("hotkeys.clear", "<escape>")
        
        # 转换为 QKeySequence 格式
        from services.hotkey_utils import pynput_to_qkeysequence
        screenshot_qt = pynput_to_qkeysequence(screenshot_pynput)
        search_qt = pynput_to_qkeysequence(search_pynput)
        clear_qt = pynput_to_qkeysequence(clear_pynput)
        
        # 更新 UI 文本
        self.screenshot_btn.setText(f"截图 ({screenshot_qt})")
        self.search_input.setPlaceholderText(f"搜索记忆... ({search_qt})")
        
        # 更新 QShortcut
        if hasattr(self, "screenshot_shortcut"):
            self.screenshot_shortcut.setKey(QKeySequence(screenshot_qt))
        if hasattr(self, "search_shortcut"):
            self.search_shortcut.setKey(QKeySequence(search_qt))
        if hasattr(self, "clear_shortcut"):
            self.clear_shortcut.setKey(QKeySequence(clear_qt))

    def _setup_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("警告: 系统不支持托盘图标，功能受限")
            self.tray_icon = None
            return

        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.blue)
        icon = QIcon(pixmap)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.activated.connect(self._on_tray_activated)

        tray_menu = QMenu()
        show_action = QAction("显示", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._on_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def _setup_menu_bar(self):
        menu = self.menuBar().addMenu("文件")

        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._on_open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

    def _on_open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(
            container.get("settings_manager"),
            container.get("keyboard_manager"),
            container.get("capture_manager"),
            container.get("task_queue"),
            self,
            ai_client=container.get("ai_client")
        )
        dialog.exec()
        self._update_shortcut_hints()

    def _connect_signals(self):
        signals.screenshot_requested.connect(self._on_screenshot)
        signals.screenshot_completed.connect(self._on_screenshot_complete)
        signals.memory_saved.connect(self._on_memory_saved)
        signals.search_completed.connect(self._on_search_completed)
        signals.error_occurred.connect(self._on_error)
        signals.status_updated.connect(self._on_status_updated)

        # 集群截图信号
        cluster_buffer = container.get("cluster_buffer")
        cluster_buffer.state_changed.connect(self._on_cluster_state_changed)
        cluster_buffer.countdown_changed.connect(self._on_cluster_countdown)
        cluster_buffer.flushed.connect(self._on_cluster_flushed)
        cluster_buffer.discarded.connect(self._on_cluster_discarded)

    def _load_memories(self):
        search_service = container.get("search_service")
        self._current_memories = search_service.get_recent_memories(limit=100)
        self._update_memory_list()

    def _update_memory_list(self):
        self.memory_list.clear()
        for memory in self._current_memories:
            badges = ""
            match_sources = getattr(memory, "match_sources", [])
            if "OCR" in match_sources:
                badges += "[OCR]"
            if "语义" in match_sources:
                badges += "[语义]"
            
            prefix = f"{badges} " if badges else ""
            self.memory_list.addItem(f"{prefix}{memory.created_at[:19]} - {memory.ai_summary[:50]}...")

    def _on_thumbnail_loaded(self, memory_id, pixmap):
        pass

    def _on_screenshot(self):
        settings_manager = container.get("settings_manager")
        cluster_mode = settings_manager.get("cluster.cluster_mode", False)
        cluster_buffer = container.get("cluster_buffer")

        bypass_debounce = cluster_mode and cluster_buffer.is_collecting()

        self.status_bar.setText("正在截图...")
        was_visible = self.isVisible()
        if was_visible:
            self.hide()

        def do_capture():
            try:
                capture_manager = container.get("capture_manager")
                result = capture_manager.capture_fullscreen(force_bypass_debounce=bypass_debounce)
            except Exception as e:
                self.status_bar.setText(f"截图失败: {e}")
                signals.error_occurred.emit(f"Screenshot error: {e}")
                if was_visible:
                    self.show()
                    self.activateWindow()
                return

            if was_visible:
                self.show()
                self.activateWindow()

            if result is None:
                if bypass_debounce:
                    self.status_bar.setText("已达到最大截图频率限制")
                else:
                    self.status_bar.setText("截图频率过快，请稍候...")
                return

            if cluster_mode:
                cluster_buffer.add_image(result.image_path)
            else:
                self._process_single_screenshot(result)

        QTimer.singleShot(250, do_capture)

    def _process_single_screenshot(self, result):
        """处理单张截图（非集群模式）"""
        self.status_bar.setText(f"截图完成，正在分析...")
        signals.screenshot_completed.emit(result.image_path)

        memory_service = container.get("memory_service")

        def _on_complete(memory_id):
            if memory_id:
                self.status_bar.setText(f"记忆已保存: {memory_id[:8]}...")
                signals.memory_saved.emit(memory_id)
            else:
                self.status_bar.setText("记忆创建失败")

        def _on_error(error_msg):
            self.status_bar.setText(f"分析失败: {error_msg}")
            signals.error_occurred.emit(f"Memory creation error: {error_msg}")

        memory_service.create_memory_async(
            result.image_path,
            app_name=result.app_name or "unknown",
            on_complete=_on_complete,
            on_error=_on_error,
        )

    def _on_screenshot_complete(self, image_path: str):
        self.status_bar.setText(f"截图完成: {image_path}")

    def _on_search_text_changed(self, text: str):
        self._search_timer.start(300)

    def _on_source_filter_changed(self, index: int):
        self._do_search()

    def _do_search(self):
        query = self.search_input.text().strip()
        search_service = container.get("search_service")
        if not query:
            self._current_memories = search_service.get_recent_memories(limit=100)
        else:
            source_filter = self.source_filter_combo.currentData()
            self._current_memories = search_service.search(query, source_filter=source_filter)
        self._update_memory_list()

    def _clear_search(self):
        self.search_input.clear()
        self._do_search()

    def _on_memory_selected(self, item):
        index = self.memory_list.row(item)
        if 0 <= index < len(self._current_memories):
            memory = self._current_memories[index]
            self.detail_panel.setText(
                f"时间: {memory.created_at}\n"
                f"应用: {memory.app_name}\n"
                f"摘要: {memory.ai_summary}\n"
                f"图片: {memory.image_path}"
            )

    def _on_memory_saved(self, memory_id: str):
        self.status_bar.setText(f"记忆已保存: {memory_id}")
        self._load_memories()

    def _on_search_completed(self, results: list):
        self._current_memories = results
        self._update_memory_list()

    def _on_error(self, error_msg: str):
        self.status_bar.setText(f"错误: {error_msg}")

    def _on_status_updated(self, status: str):
        self.status_bar.setText(status)

    def _on_cluster_state_changed(self, state: str, count: int, max_count: int):
        if state == "COLLECTING":
            self._cluster_submit_btn.setVisible(True)
            self._cluster_cancel_btn.setVisible(True)
            self.status_bar.setText(f"已收集 {count}/{max_count} 张截图")
        else:
            self._cluster_submit_btn.setVisible(False)
            self._cluster_cancel_btn.setVisible(False)

    def _on_cluster_countdown(self, seconds: int):
        settings_manager = container.get("settings_manager")
        auto_submit = settings_manager.get("cluster.cluster_auto_submit", True)
        if not auto_submit:
            return  # 手动模式下不显示倒计时后缀
        if seconds > 0:
            self.status_bar.setText(f"{self.status_bar.text().split('(')[0].strip()} ({seconds}s后自动提交)")

    def _on_cluster_flushed(self, image_paths: list):
        self.status_bar.setText("正在分析集群截图...")
        memory_service = container.get("memory_service")

        def _on_complete(memory_id):
            if memory_id:
                self.status_bar.setText(f"集群记忆已保存: {memory_id[:8]}...")
                signals.memory_saved.emit(memory_id)
            else:
                self.status_bar.setText("集群记忆创建失败")

        def _on_error(error_msg):
            self.status_bar.setText(f"分析失败: {error_msg}")
            signals.error_occurred.emit(f"Cluster memory error: {error_msg}")

        memory_service.create_cluster_memory_async(
            image_paths,
            app_name="unknown",
            on_complete=_on_complete,
            on_error=_on_error,
        )

    def _on_cluster_discarded(self):
        self.status_bar.setText("集群截图已取消")

    def _on_cluster_submit(self):
        cluster_buffer = container.get("cluster_buffer")
        cluster_buffer.flush()

    def _on_cluster_cancel(self):
        cluster_buffer = container.get("cluster_buffer")
        cluster_buffer.discard()

    def _on_tray_activated(self, reason):
        if self.tray_icon is None:
            return
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()
            self.activateWindow()

    def _on_quit(self):
        """完全退出应用"""
        if self.tray_icon is not None:
            self.tray_icon.hide()
        container.get("keyboard_manager").stop_listening()
        container.get("task_queue").shutdown()
        container.get("capture_manager").close()
        QApplication.instance().quit()

    def closeEvent(self, event):
        """窗口关闭时隐藏到托盘而不是退出"""
        if self.tray_icon is None:
            self._on_quit()
            return
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Glimpse",
            "应用已最小化到托盘，点击托盘图标可重新打开",
            QSystemTrayIcon.Information,
            2000
        )
