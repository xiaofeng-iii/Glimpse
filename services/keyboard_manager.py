"""
键盘管理器
负责全局快捷键监听和配置
"""
import traceback
from typing import Dict, Callable, Optional
from pynput import keyboard
from threading import Lock

from services.hotkey_utils import normalize_pynput_hotkey
from utils.logger import get_logger

logger = get_logger(__name__)


class KeyboardManager:
    """键盘管理器 - 单例模式"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._hotkeys: Dict[str, Callable] = {}
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._running = False
        self._listener_lock = Lock()
    
    def register_hotkey(self, hotkey: str, callback: Callable):
        """注册全局快捷键
        
        Args:
            hotkey: 快捷键字符串，如 "<ctrl>+<shift>+g"
            callback: 回调函数
        """
        normalized_hotkey = normalize_pynput_hotkey(hotkey)
        if not normalized_hotkey:
            raise ValueError("hotkey cannot be empty")

        with self._lock:
            self._hotkeys[normalized_hotkey] = callback
    
    def unregister_hotkey(self, hotkey: str):
        """注销全局快捷键
        
        Args:
            hotkey: 快捷键字符串
        """
        with self._lock:
            if hotkey in self._hotkeys:
                del self._hotkeys[hotkey]
    
    def clear_hotkeys(self):
        """清空所有已注册的快捷键"""
        with self._lock:
            self._hotkeys.clear()
    
    def _create_listener_locked(self) -> Optional[keyboard.GlobalHotKeys]:
        """在持有_lock的情况下创建热键监听器（内部方法）

        Returns:
            创建的监听器，失败返回 None
        """
        hotkey_dict = {hotkey: callback for hotkey, callback in self._hotkeys.items()}
        if not hotkey_dict:
            return None
        try:
            return keyboard.GlobalHotKeys(hotkey_dict)
        except Exception as e:
            logger.error("Failed to create GlobalHotKeys: %s", e, exc_info=True)
            return None

    def start_listening(self):
        """开始监听全局快捷键"""
        with self._listener_lock:
            if self._running:
                return
            with self._lock:
                listener = self._create_listener_locked()
                if listener:
                    try:
                        listener.start()
                        self._listener = listener
                        self._running = True
                    except Exception as e:
                        logger.error("Error starting listener: %s", e)
                        try:
                            listener.stop()
                        except Exception as e2:
                            logger.error("Error stopping listener after start failure: %s", e2)

    def stop_listening(self):
        """停止监听全局快捷键"""
        with self._listener_lock:
            if self._running and self._listener:
                try:
                    self._listener.stop()
                except Exception as e:
                    logger.error("Error stopping listener: %s", e)
                self._running = False
                self._listener = None

    def restart_listening(self):
        """重启键盘监听（用于热更新快捷键）

        锁顺序：统一先 _listener_lock，再 _lock
        异常处理：创建失败时保持停止状态，不半初始化
        """
        with self._listener_lock:
            old_listener = self._listener
            old_running = self._running

            self._listener = None
            self._running = False

            if old_running and old_listener:
                try:
                    old_listener.stop()
                except Exception as e:
                    logger.error("Error stopping old listener during restart: %s", e)

            with self._lock:
                new_listener = self._create_listener_locked()
                if new_listener:
                    try:
                        new_listener.start()
                        self._listener = new_listener
                        self._running = True
                    except Exception as e:
                        logger.error("Error starting new listener during restart: %s", e)
                        try:
                            new_listener.stop()
                        except Exception as e2:
                            logger.error("Error stopping new listener after restart failure: %s", e2)

    def is_running(self) -> bool:
        """检查是否正在监听"""
        return self._running

    def get_hotkeys(self) -> Dict[str, Callable]:
        """获取所有注册的快捷键"""
        with self._lock:
            return self._hotkeys.copy()

    def reload_hotkeys(self, hotkeys: Dict[str, Callable]) -> bool:
        """重新加载快捷键配置（原子操作）

        Args:
            hotkeys: 新的快捷键字典

        Returns:
            是否重载成功
        """
        try:
            normalized_hotkeys = {}
            for hotkey, callback in hotkeys.items():
                normalized_hotkey = normalize_pynput_hotkey(hotkey)
                if normalized_hotkey:
                    normalized_hotkeys[normalized_hotkey] = callback
        except ValueError:
            return False

        old_hotkeys = self._hotkeys.copy()
        old_listener = self._listener
        old_running = self._running

        new_listener = None
        new_running = False

        try:
            with self._listener_lock:
                if old_running and old_listener:
                    try:
                        old_listener.stop()
                    except Exception as e:
                        logger.error("Error stopping old listener during reload: %s", e)

                with self._lock:
                    self._hotkeys = normalized_hotkeys
                    self._listener = None
                    self._running = False

                    new_listener = self._create_listener_locked()
                    if new_listener:
                        try:
                            new_listener.start()
                            self._listener = new_listener
                            new_running = True
                            self._running = True
                        except Exception as e:
                            logger.error("Error starting new listener during reload: %s", e)
                            try:
                                new_listener.stop()
                            except Exception as e2:
                                logger.error("Error stopping new listener after reload failure: %s", e2)

                    return new_running or not normalized_hotkeys

        except Exception as e:
            logger.error("Reload hotkeys failed: %s", e, exc_info=True)
            with self._listener_lock:
                with self._lock:
                    if old_running and old_listener:
                        try:
                            old_listener.start()
                            self._listener = old_listener
                            self._running = old_running
                        except Exception as e2:
                            logger.error("Error rolling back listener during reload: %s", e2)
                            self._listener = None
                            self._running = False
                    else:
                        self._listener = None
                        self._running = False
                    self._hotkeys = old_hotkeys
            return False


keyboard_manager = KeyboardManager()
