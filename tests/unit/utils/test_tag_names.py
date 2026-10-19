"""Unit tests for utils/tag_names.py"""

import pytest

from utils.tag_names import (
    MAX_TAG_NAME_LENGTH,
    MAX_TAGS_PER_MEMORY,
    normalize_tag_name,
    normalize_tag_names,
)


class TestNormalizeTagName:
    def test_strips_and_collapses_whitespace(self):
        assert normalize_tag_name("  工作 \t 笔记  ") == "工作 笔记"

    def test_rejects_blank_names(self):
        for raw in ("", "   ", "\t\n"):
            with pytest.raises(ValueError):
                normalize_tag_name(raw)

    def test_rejects_overlong_names(self):
        with pytest.raises(ValueError):
            normalize_tag_name("x" * (MAX_TAG_NAME_LENGTH + 1))
        assert normalize_tag_name("x" * MAX_TAG_NAME_LENGTH) == "x" * MAX_TAG_NAME_LENGTH

    def test_rejects_control_characters(self):
        with pytest.raises(ValueError):
            normalize_tag_name("bad\x00name")
        with pytest.raises(ValueError):
            normalize_tag_name("bad\x7fname")

    def test_rejects_non_string(self):
        with pytest.raises(ValueError):
            normalize_tag_name(123)

    def test_allows_sql_wildcards_and_quotes(self):
        # 这些字符不构成 SQL 风险：所有值都走参数绑定。
        assert normalize_tag_name("100%_\"'\\") == "100%_\"'\\"


class TestNormalizeTagNames:
    def test_empty_list_is_valid(self):
        assert normalize_tag_names([]) == []

    def test_dedupes_case_insensitively_keeping_first(self):
        assert normalize_tag_names(["Work", "work", "WORK", "灵感"]) == [
            "Work",
            "灵感",
        ]

    def test_rejects_more_than_max_tags(self):
        names = [f"tag-{index}" for index in range(MAX_TAGS_PER_MEMORY + 1)]
        with pytest.raises(ValueError):
            normalize_tag_names(names)
        assert len(normalize_tag_names(names[:MAX_TAGS_PER_MEMORY])) == MAX_TAGS_PER_MEMORY

    def test_count_limit_applies_after_dedupe(self):
        names = ["work"] * (MAX_TAGS_PER_MEMORY + 1)
        assert normalize_tag_names(names) == ["work"]

    def test_rejects_non_list(self):
        for raw in (None, "work", 42):
            with pytest.raises(ValueError):
                normalize_tag_names(raw)
