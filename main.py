"""
Glimpse - AI 驱动的桌面级记忆检索系统
程序唯一入口，初始化 UI、数据库与全局路径

启动顺序：
1. 加载环境变量（.env）
2. 初始化容器（container）
3. 初始化路径（path_manager）
4. 初始化数据库（sqlite + chroma）
5. 初始化服务（embedding、ai）
6. 配置 AI 客户端
7. 初始化任务队列
8. 启动 UI
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 加载 .env 环境变量
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env from {env_path}")
except ImportError:
    pass

from PySide6.QtWidgets import QApplication, QMessageBox


def main():
    from container import container
    from services.bootstrap import configure_ai_client
    from ui.app_icon import create_app_icon, set_windows_app_user_model_id

    print("Initializing container...")
    container.initialize_defaults()

    print("Initializing path manager...")
    path_manager = container.get("path_manager")
    settings_manager = container.get("settings_manager")

    print("Initializing databases...")
    sqlite_manager = container.get("sqlite_manager")
    chroma_manager = container.get("chroma_manager")

    print("Initializing services...")
    ai_client = container.get("ai_client")

    # 配置 AI 客户端
    configure_ai_client(ai_client, settings_manager)

    print("Initializing task queue...")
    task_queue = container.get("task_queue")

    print("Initializing keyboard manager...")
    keyboard_manager = container.get("keyboard_manager")

    from ui.locale_manager import init_locale
    init_locale()

    screenshot_hotkey = settings_manager.get("hotkeys.screenshot", "<ctrl>+<shift>+g")

    def on_screenshot():
        from ui.signals import signals
        print("Global screenshot shortcut pressed!")
        signals.screenshot_requested.emit()

    print("Starting UI...")
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName("Glimpse")
    app.setOrganizationName("Glimpse")
    app.setWindowIcon(create_app_icon())

    from ui.main_window import MainWindow
    from ui.theme_manager import ThemeManager

    try:
        theme_manager = ThemeManager(app)
        window = MainWindow(theme_manager=theme_manager)
        window.show()

        # 在 Qt 消息泵启动后注册全局热键，避免 Windows 钩子初始化冲突
        keyboard_manager.register_hotkey(screenshot_hotkey, on_screenshot)
        keyboard_manager.start_listening()
        print(f"Global hotkey registered: {screenshot_hotkey}")

        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(
            None,
            "启动失败",
            f"应用启动时发生错误：\n{str(e)}",
            QMessageBox.Ok
        )
        raise
    finally:
        container.shutdown()


if __name__ == "__main__":
    main()
