# Settings Dialog Button Behavior Redesign

## Problem

Current settings dialog has inconsistent button behavior:

- **Save**: Always pops "设置已保存" even when nothing changed; never closes the dialog
- **Apply**: Pops "设置没有变化" when nothing changed but doesn't close; pops confirm dialog when there are changes; never closes
- **Cancel**: Checks dirty state on close with a confirmation dialog

User expects:
1. No prompts when nothing was modified
2. "Save & Apply" should close the dialog after saving
3. Conflict detection framework for future use

## Decision

**Approach A: Minimal logic change, no UI layout change**

Only modify `_on_save`, `_on_apply`, and `closeEvent` logic. Button labels and layout stay the same.

## Button Behavior Matrix

| Button | No changes | Changes, no conflicts | Conflicts detected |
|---------|------------|----------------------|-------------------|
| **Save** | Silent, do nothing | Save to disk, no popup, no exit | Save to disk, no popup, no exit |
| **Save & Apply** | Silent close dialog | Save + apply runtime + **close dialog**, no confirmation popup | Show conflict dialog; on confirm → close dialog |
| **Cancel** | Close dialog | Close dialog (no dirty check) | — |
| **Reset Defaults** | Unchanged: confirm → reset | Unchanged | Unchanged |

## Conflict Detection Framework

### `_detect_conflicts(self, new_settings: dict) -> list[str]`

Returns empty list when no conflicts, non-empty list of conflict description strings otherwise.

Currently no known conflicts exist (all settings are independent). Future conflicts will be added here.

Example future usage:
```python
def _detect_conflicts(self, new_settings: dict) -> list[str]:
    conflicts = []
    # Example: if cluster_mode requires debounce < 3
    # cluster = new_settings.get("cluster", {})
    # screenshot = new_settings.get("screenshot", {})
    # if cluster.get("cluster_mode") and screenshot.get("debounce_interval", 5) < 3:
    #     conflicts.append(t("settings.conflict.cluster_debounce"))
    return conflicts
```

### Conflict Dialog

- Title + content from `_detect_conflicts()` return value
- Top-right X button = cancel (return to settings dialog)
- Bottom-right "Confirm" button = acknowledge conflict, proceed with save & exit
- Built with `QMessageBox` using Yes/No buttons

## Cancel Button Change

Remove `closeEvent` dirty check entirely. Cancel button calls `self.reject()` directly without confirmation.

Rationale: The "Save" button already provides save-without-exit capability, so users who want to preserve changes can click Save first. No data loss risk.

## Implementation Scope

Files to modify:

1. `ui/settings_dialog.py` — `_on_save`, `_on_apply`, `closeEvent`, add `_detect_conflicts`
2. `ui/locales/zh-CN.json` — Add `settings.conflict_title` key
3. `ui/locales/en-US.json` — Add `settings.conflict_title` key

No new files, no UI layout changes, no new dependencies.

## i18n Keys to Add

```json
// zh-CN
"settings": {
  "conflict_title": "设置冲突",
  "conflict_proceed": "仍然应用"
}

// en-US  
"settings": {
  "conflict_title": "Settings Conflict",
  "conflict_proceed": "Apply Anyway"
}
```