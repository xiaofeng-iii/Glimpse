"""
hotkey_utils 单元测试

测试服务模块 services/hotkey_utils.py
覆盖: normalize_pynput_hotkey, qkeysequence_to_pynput,
       pynput_to_qkeysequence, is_valid_pynput_hotkey
"""
import pytest

from services.hotkey_utils import (
    normalize_pynput_hotkey,
    qkeysequence_to_pynput,
    pynput_to_qkeysequence,
    is_valid_pynput_hotkey,
)


class TestNormalizePynputHotkey:
    """normalize_pynput_hotkey 规范化测试"""

    def test_ctrl_shift_g(self):
        assert normalize_pynput_hotkey("<ctrl>+<shift>+g") == "<ctrl>+<shift>+g"

    def test_ctrl_f(self):
        assert normalize_pynput_hotkey("<ctrl>+<f>") == "<ctrl>+f"

    def test_escape(self):
        assert normalize_pynput_hotkey("<escape>") == "<escape>"

    def test_single_letter(self):
        assert normalize_pynput_hotkey("a") == "a"

    def test_modifiers_ordered(self):
        result = normalize_pynput_hotkey("<shift>+<ctrl>+g")
        assert result == "<ctrl>+<shift>+g"

    def test_alt_key(self):
        assert normalize_pynput_hotkey("<alt>+<f4>") == "<alt>+<f4>"

    def test_multi_sequence_raises(self):
        with pytest.raises(ValueError, match="multi-sequence"):
            normalize_pynput_hotkey("a, b")

    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="must be a string"):
            normalize_pynput_hotkey(123)

    def test_empty_string_returns_empty(self):
        assert normalize_pynput_hotkey("") == ""

    def test_bad_key_raises(self):
        with pytest.raises(ValueError):
            normalize_pynput_hotkey("<ctrl>+badkey")


class TestQKeySequenceToPynput:
    """qkeysequence_to_pynput 转换测试"""

    def test_ctrl_shift_g(self):
        assert qkeysequence_to_pynput("Ctrl+Shift+G") == "<ctrl>+<shift>+g"

    def test_ctrl_f(self):
        assert qkeysequence_to_pynput("Ctrl+F") == "<ctrl>+f"

    def test_esc(self):
        assert qkeysequence_to_pynput("Esc") == "<escape>"

    def test_alt_f4(self):
        assert qkeysequence_to_pynput("Alt+F4") == "<alt>+<f4>"

    def test_comma_returns_unchanged(self):
        assert qkeysequence_to_pynput("Ctrl+K, Ctrl+C") == "Ctrl+K, Ctrl+C"

    def test_empty_string_returns_empty(self):
        assert qkeysequence_to_pynput("") == ""

    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="must be a string"):
            qkeysequence_to_pynput(123)


class TestPynputToQKeySequence:
    """pynput_to_qkeysequence 转换测试"""

    def test_ctrl_shift_g(self):
        assert pynput_to_qkeysequence("<ctrl>+<shift>+g") == "Ctrl+Shift+G"

    def test_ctrl_f(self):
        assert pynput_to_qkeysequence("<ctrl>+f") == "Ctrl+F"

    def test_escape(self):
        assert pynput_to_qkeysequence("<escape>") == "Esc"

    def test_alt_f4(self):
        assert pynput_to_qkeysequence("<alt>+<f4>") == "Alt+F4"

    def test_empty_string_returns_empty(self):
        assert pynput_to_qkeysequence("") == ""


class TestIsValidPynputHotkey:
    """is_valid_pynput_hotkey 合法性检验测试"""

    def test_valid_simple_hotkey(self):
        assert is_valid_pynput_hotkey("<ctrl>+g") is True

    def test_multi_sequence_is_false(self):
        assert is_valid_pynput_hotkey("Ctrl+K, Ctrl+C") is False

    def test_bad_key_is_false(self):
        assert is_valid_pynput_hotkey("<ctrl>+badkey") is False

    def test_empty_string_allow_empty_true(self):
        assert is_valid_pynput_hotkey("", allow_empty=True) is True

    def test_empty_string_allow_empty_false(self):
        assert is_valid_pynput_hotkey("", allow_empty=False) is False
