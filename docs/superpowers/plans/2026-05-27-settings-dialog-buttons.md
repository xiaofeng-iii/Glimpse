# Settings Dialog Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign settings dialog button behavior: silent when no changes, "Save & Apply" closes dialog, conflict framework for future use.

**Architecture:** Modify `_on_save`, `_on_apply`, `closeEvent` in `ui/settings_dialog.py`. Add `_detect_conflicts` method. Update i18n keys in locale JSONs. No UI layout changes.

**Tech Stack:** PySide6, existing `QMessageBox`, existing `locale_manager.t()` i18n

---

### Task 1: Add conflict i18n keys

**Files:**
- Modify: `ui/locales/zh-CN.json`
- Modify: `ui/locales/en-US.json`

- [ ] **Step 1: Add keys to zh-CN.json**

Inside the `"settings"` object, add two new keys after the existing `"confirm_close_msg"` key:

```json
    "confirm_close_msg": "有未保存的修改，确定要关闭吗？",
    "conflict_title": "设置冲突",
    "conflict_proceed": "仍然应用"
```

- [ ] **Step 2: Add keys to en-US.json**

Inside the `"settings"` object, add two new keys after the existing `"confirm_close_msg"` key:

```json
    "confirm_close_msg": "You have unsaved changes. Are you sure you want to close?",
    "conflict_title": "Settings Conflict",
    "conflict_proceed": "Apply Anyway"
```

- [ ] **Step 3: Commit i18n keys**

```bash
git add ui/locales/zh-CN.json ui/locales/en-US.json
git commit -m "feat: 添加设置对话框冲突检测国际化键"
```

---

### Task 2: Refactor `_on_save` — silent when no changes

**Files:**
- Modify: `ui/settings_dialog.py` lines 387-407

- [ ] **Step 1: Write the failing test**

Create `tests/unit/ui/test_settings_dialog_buttons.py`:

```python
import copy
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt


class FakeSettingsManager:
    def __init__(self, settings=None):
        self._settings = settings or {
            "hotkeys": {"screenshot": "<ctrl>+<shift>+g", "search": "<ctrl>+<f>"},
            "screenshot": {"debounce_interval": 5.0, "cluster_threshold": 2.0, "max_captures_per_window": 10},
            "ai": {"api_key": "sk-test", "model": "gpt-4o-mini", "timeout": 30},
            "ocr": {"engine": "rapidocr", "language": "ch"},
            "ui": {"theme": "light", "auto_hide": False, "start_minimized": False},
        }

    def get_all(self):
        return copy.deepcopy(self._settings)

    def update(self, settings):
        self._settings = copy.deepcopy(settings)
        return True

    def get(self, key, default=None):
        keys = key.split(".")
        val = self._settings
        for k in keys:
            val = val.get(k, {})
        return val if val != {} else default


@pytest.fixture
def settings_dialog(qtbot):
    from ui.settings_dialog import SettingsDialog
    sm = FakeSettingsManager()
    with patch("ui.settings_dialog.ThemeManager"):
        dlg = SettingsDialog(settings_manager=sm)
    qtbot.addWidget(dlg)
    return dlg


class TestOnSave:
    def test_save_no_changes_silent(self, settings_dialog, qtbot, mocker):
        """When no settings changed, _on_save returns True silently (no QMessageBox)."""
        mocker.patch.object(QMessageBox, "information")
        result = settings_dialog._on_save()
        assert result is True
        QMessageBox.information.assert_not_called()

    def test_save_with_changes_succeeds(self, settings_dialog, qtbot, mocker):
        """When settings changed, _on_save saves and returns True silently (no popup)."""
        settings_dialog._debounce_interval.setValue(10.0)
        mocker.patch.object(QMessageBox, "information")
        result = settings_dialog._on_save()
        assert result is True
        QMessageBox.information.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit/ui/test_settings_dialog_buttons.py -v`
Expected: FAIL — `_on_save` currently always shows `QMessageBox.information`

- [ ] **Step 3: Modify `_on_save` method**

In `ui/settings_dialog.py`, replace the `_on_save` method (lines 387-407) with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit/ui/test_settings_dialog_buttons.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/settings_dialog.py tests/unit/ui/test_settings_dialog_buttons.py
git commit -m "feat: 保存按钮无修改时静默返回，有修改时静默保存不弹窗"
```

---

### Task 3: Refactor `_on_apply` — close on success, conflict framework

**Files:**
- Modify: `ui/settings_dialog.py` lines 409-452

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/ui/test_settings_dialog_buttons.py`:

```python
class TestOnApply:
    def test_apply_no_changes_closes_silently(self, settings_dialog, qtbot, mocker):
        """No changes → accept() called, no popup."""
        mocker.patch.object(QMessageBox, "information")
        mocker.patch.object(QMessageBox, "question")
        mocker.patch.object(QMessageBox, "warning")
        settings_dialog._on_apply()
        assert settings_dialog.result() == 1  # Accepted
        QMessageBox.information.assert_not_called()
        QMessageBox.question.assert_not_called()

    def test_apply_with_changes_closes(self, settings_dialog, qtbot, mocker):
        """Changes + no conflicts → accept() called, no confirmation popup."""
        settings_dialog._debounce_interval.setValue(10.0)
        mocker.patch.object(QMessageBox, "information")
        mocker.patch.object(QMessageBox, "question")
        mocker.patch.object(QMessageBox, "warning")
        settings_dialog._on_apply()
        assert settings_dialog.result() == 1
        QMessageBox.question.assert_not_called()

    def test_apply_with_conflict_shows_dialog(self, settings_dialog, qtbot, mocker):
        """Changes + conflict → show conflict dialog, user confirms → accept()."""
        settings_dialog._debounce_interval.setValue(10.0)
        mocker.patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes
        )
        mocker.patch.object(settings_dialog, "_detect_conflicts", return_value=["Test conflict"])
        settings_dialog._on_apply()
        assert settings_dialog.result() == 1
        QMessageBox.question.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit/ui/test_settings_dialog_buttons.py -v`
Expected: FAIL — current `_on_apply` does not call `accept()`

- [ ] **Step 3: Add `_detect_conflicts` method and refactor `_on_apply`**

Add the `_detect_conflicts` method and replace `_on_apply` (lines 409-452) with:

```python
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
            conflict_text = "\n".join(f"• {c}" for c in conflicts)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit/ui/test_settings_dialog_buttons.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/settings_dialog.py tests/unit/ui/test_settings_dialog_buttons.py
git commit -m "feat: 保存并应用无修改时静默关闭，有冲突弹冲突框，无冲突直接退出"
```

---

### Task 4: Remove `closeEvent` dirty check

**Files:**
- Modify: `ui/settings_dialog.py` lines 511-523

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/ui/test_settings_dialog_buttons.py`:

```python
class TestCloseEvent:
    def test_close_with_changes_no_prompt(self, settings_dialog, qtbot, mocker):
        """Closing with unsaved changes should NOT prompt (no dirty check)."""
        settings_dialog._debounce_interval.setValue(99.0)
        mocker.patch.object(QMessageBox, "question")
        settings_dialog.close()
        QMessageBox.question.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit/ui/test_settings_dialog_buttons.py::TestCloseEvent -v`
Expected: FAIL — `closeEvent` currently calls `QMessageBox.question`

- [ ] **Step 3: Remove dirty check from `closeEvent`**

Replace `closeEvent` (lines 511-523) with:

```python
    def closeEvent(self, event):
        event.accept()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit/ui/test_settings_dialog_buttons.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/settings_dialog.py tests/unit/ui/test_settings_dialog_buttons.py
git commit -m "feat: 移除设置对话框关闭时的脏数据检查"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

Run: `& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 2: Manual smoke test**

Launch the app, open settings, verify:
- No changes → "保存" does nothing silent → "保存并应用" closes dialog
- Make changes → "保存" saves silently, dialog stays → "保存并应用" saves and closes
- Cancel always closes without prompt

- [ ] **Step 3: Final commit if any fixes needed**