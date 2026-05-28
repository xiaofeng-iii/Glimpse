"""
快捷键格式转换工具。

在 pynput 的 GlobalHotKeys 文本格式和 Qt 的 QKeySequence 文本格式之间转换。
"""

from __future__ import annotations

from typing import Iterable


_MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "cmd": "cmd",
    "command": "cmd",
    "meta": "cmd",
    "super": "cmd",
    "win": "cmd",
}

_MODIFIER_ORDER = ("ctrl", "shift", "alt", "cmd")
_SPECIAL_KEYS = {
    "escape": "escape",
    "esc": "escape",
    "enter": "enter",
    "return": "enter",
    "tab": "tab",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "del": "delete",
    "insert": "insert",
    "ins": "insert",
    "home": "home",
    "end": "end",
    "pageup": "page_up",
    "page up": "page_up",
    "page_up": "page_up",
    "pgup": "page_up",
    "pagedown": "page_down",
    "page down": "page_down",
    "page_down": "page_down",
    "pgdown": "page_down",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
}

_QT_MODIFIERS = {
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "cmd": "Meta",
}

_QT_SPECIAL_KEYS = {
    "escape": "Esc",
    "enter": "Return",
    "tab": "Tab",
    "space": "Space",
    "backspace": "Backspace",
    "delete": "Del",
    "insert": "Ins",
    "home": "Home",
    "end": "End",
    "page_up": "PgUp",
    "page_down": "PgDown",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
}

_QT_TO_PYNPUT = {value.lower(): key for key, value in _QT_SPECIAL_KEYS.items()}
_QT_TO_PYNPUT.update({"escape": "escape", "return": "enter"})


def normalize_pynput_hotkey(hotkey: str) -> str:
    """规范化 pynput GlobalHotKeys 快捷键文本。"""
    if not isinstance(hotkey, str):
        raise ValueError("hotkey must be a string")

    text = hotkey.strip()
    if not text:
        return ""
    if "," in text:
        raise ValueError("multi-sequence hotkeys are not supported")

    modifiers: list[str] = []
    key: str | None = None
    for raw_part in text.split("+"):
        part = raw_part.strip().lower()
        if not part:
            raise ValueError("empty hotkey component")

        if part.startswith("<") and part.endswith(">"):
            part = part[1:-1].strip().lower()

        if part in _MODIFIER_ALIASES:
            modifier = _MODIFIER_ALIASES[part]
            if modifier not in modifiers:
                modifiers.append(modifier)
            continue

        if key is not None:
            raise ValueError("hotkey must contain exactly one non-modifier key")

        if part in _SPECIAL_KEYS:
            key = f"<{_SPECIAL_KEYS[part]}>"
        elif _is_function_key(part):
            key = f"<{part}>"
        elif len(part) == 1 and part.isprintable():
            key = part
        else:
            raise ValueError(f"unsupported key: {part}")

    if key is None:
        raise ValueError("hotkey must contain a non-modifier key")

    ordered_modifiers = [modifier for modifier in _MODIFIER_ORDER if modifier in modifiers]
    return "+".join([f"<{modifier}>" for modifier in ordered_modifiers] + [key])


def is_valid_pynput_hotkey(hotkey: str, allow_empty: bool = True) -> bool:
    """判断 pynput 快捷键文本是否合法。"""
    try:
        normalized = normalize_pynput_hotkey(hotkey)
    except (TypeError, ValueError):
        return False
    return allow_empty or bool(normalized)


def pynput_to_qkeysequence(hotkey: str) -> str:
    """将 pynput 快捷键文本转换为 QKeySequence 可识别的 PortableText。"""
    normalized = normalize_pynput_hotkey(hotkey)
    if not normalized:
        return ""

    qt_parts: list[str] = []
    for part in _split_pynput_parts(normalized):
        if part in _MODIFIER_ALIASES:
            qt_parts.append(_QT_MODIFIERS[_MODIFIER_ALIASES[part]])
        elif part in _SPECIAL_KEYS:
            qt_parts.append(_QT_SPECIAL_KEYS[_SPECIAL_KEYS[part]])
        elif _is_function_key(part):
            qt_parts.append(part.upper())
        else:
            qt_parts.append(part.upper() if len(part) == 1 else part)
    return "+".join(qt_parts)


def qkeysequence_to_pynput(sequence_text: str) -> str:
    """将 QKeySequence PortableText 转换为 pynput 快捷键文本。"""
    if not isinstance(sequence_text, str):
        raise ValueError("sequence_text must be a string")

    text = sequence_text.strip()
    if not text:
        return ""
    if "," in text:
        return text

    parts = []
    for raw_part in text.split("+"):
        part = raw_part.strip()
        if not part:
            return text
        lower = part.lower()
        if lower in _MODIFIER_ALIASES:
            parts.append(f"<{_MODIFIER_ALIASES[lower]}>")
        elif lower in _QT_TO_PYNPUT:
            parts.append(f"<{_QT_TO_PYNPUT[lower]}>")
        elif _is_function_key(lower):
            parts.append(f"<{lower}>")
        elif len(part) == 1 and part.isprintable():
            parts.append(part.lower())
        else:
            return text

    return normalize_pynput_hotkey("+".join(parts))


def _split_pynput_parts(hotkey: str) -> Iterable[str]:
    for raw_part in hotkey.split("+"):
        part = raw_part.strip().lower()
        if part.startswith("<") and part.endswith(">"):
            part = part[1:-1]
        yield part


def _is_function_key(key: str) -> bool:
    return key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24
