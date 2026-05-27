"""
Mock hotkey utilities for standalone frontend preview.
"""
def pynput_to_qkeysequence(pynput_str: str) -> str:
    """Convert pynput hotkey format to QKeySequence format."""
    mapping = {
        "<ctrl>": "Ctrl",
        "<shift>": "Shift",
        "<alt>": "Alt",
        "<escape>": "Esc",
        "<cmd>": "Meta",
        "<super>": "Meta",
    }
    result = pynput_str
    for k, v in mapping.items():
        result = result.replace(k, v)
    return result
