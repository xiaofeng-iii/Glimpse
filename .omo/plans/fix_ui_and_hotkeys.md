# Glimpse UI & Hotkey Fix Plan

## Goal
Resolve three UI and hotkey interaction bugs:
1. SettingsDialog hotkey change doesn't trigger the full memory pipeline.
2. MainWindow shortcut hints (buttons/placeholders) don't update after settings change.
3. MainWindow doesn't hide when taking a screenshot.

## Context & Approach
- `ui/settings_dialog.py` and `main.py` currently have duplicated and broken `on_screenshot` callbacks. We will centralize by making them simply emit `signals.screenshot_requested.emit()`.
- `ui/main_window.py` will connect to `screenshot_requested` and handle the full screenshot + memory pipeline.
- `ui/main_window.py` will update its UI elements by re-reading `settings_manager` after the settings dialog closes.
- `ui/main_window.py`'s `_on_screenshot` will hide the window, use `QTimer.singleShot(250, ...)` to wait for the OS to hide it, perform capture, and then restore the window.

## TODOs

1. [ ] Edit `ui/settings_dialog.py`: Modify `_get_screenshot_callback` to emit `signals.screenshot_requested`.
2. [ ] Edit `main.py`: Modify `on_screenshot` to only emit `signals.screenshot_requested`, removing the duplicate capture pipeline.
3. [ ] Edit `ui/main_window.py`: Add `signals.screenshot_requested.connect(self._on_screenshot)` in `_connect_signals()`.
4. [ ] Edit `ui/main_window.py`: Add `_update_shortcut_hints(self)` method to update UI text from `settings_manager`. Call it in `_setup_shortcuts()` and after `dialog.exec()` in `_on_open_settings()`.
5. [ ] Edit `ui/main_window.py`: Rewrite `_on_screenshot(self)` to hide the window, wait 250ms with `QTimer.singleShot`, capture, and restore.

## Final Verification Wave

F1. [ ] Manual QA: Start the app. Press Ctrl+Shift+G. Observe main window hides, screenshot is taken, and memory pipeline starts.
F2. [ ] Manual QA: Open settings, change screenshot hotkey to Shift+Z, save. Observe main window button updates to "截图 (Shift+Z)".
F3. [ ] Manual QA: Press Shift+Z. Observe screenshot is taken and memory pipeline starts.