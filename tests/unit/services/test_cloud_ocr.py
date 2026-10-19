"""Unit tests for the optional Baidu OCR adapter."""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.cloud_ocr import (
    OCR_URL,
    TOKEN_URL,
    BaiduOCREngine,
    CloudOCRError,
)


def response(payload):
    value = MagicMock()
    value.json.return_value = payload
    return value


def make_image(tmp_path: Path, data: bytes = b"fake-image") -> Path:
    path = tmp_path / "shot.png"
    path.write_bytes(data)
    return path


def test_extract_text_requests_token_then_ocr(tmp_path):
    engine = BaiduOCREngine("api-key", "secret-key", 15)
    image = make_image(tmp_path)

    with patch("services.cloud_ocr.requests.post") as post:
        post.side_effect = [
            response({"access_token": "token-1", "expires_in": 3600}),
            response({"words_result": [{"words": "你好"}, {"words": "世界"}]}),
        ]
        assert engine.extract_text(str(image)) == "你好\n世界"

    assert post.call_count == 2
    token_call, ocr_call = post.call_args_list
    assert token_call.args[0] == TOKEN_URL
    assert token_call.kwargs["params"]["client_id"] == "api-key"
    assert token_call.kwargs["params"]["client_secret"] == "secret-key"
    assert ocr_call.args[0] == OCR_URL
    assert ocr_call.kwargs["params"] == {"access_token": "token-1"}
    assert ocr_call.kwargs["data"]["detect_direction"] == "true"
    assert base64.b64decode(ocr_call.kwargs["data"]["image"]) == b"fake-image"


def test_access_token_is_cached_between_images(tmp_path):
    engine = BaiduOCREngine("api-key", "secret-key")
    image = make_image(tmp_path)

    with patch("services.cloud_ocr.requests.post") as post:
        post.side_effect = [
            response({"access_token": "token-1", "expires_in": 3600}),
            response({"words_result": [{"words": "first"}]}),
            response({"words_result": [{"words": "second"}]}),
        ]
        assert engine.extract_text(str(image)) == "first"
        assert engine.extract_text(str(image)) == "second"

    assert post.call_count == 3
    assert post.call_args_list[0].args[0] == TOKEN_URL
    assert post.call_args_list[1].args[0] == OCR_URL
    assert post.call_args_list[2].args[0] == OCR_URL


def test_expired_token_is_refreshed_once(tmp_path):
    engine = BaiduOCREngine("api-key", "secret-key")
    image = make_image(tmp_path)

    with patch("services.cloud_ocr.requests.post") as post:
        post.side_effect = [
            response({"access_token": "token-old", "expires_in": 3600}),
            response({"error_code": 110, "error_msg": "token invalid"}),
            response({"access_token": "token-new", "expires_in": 3600}),
            response({"words_result": [{"words": "ok"}]}),
        ]
        assert engine.extract_text(str(image)) == "ok"

    assert post.call_count == 4
    assert post.call_args_list[2].args[0] == TOKEN_URL
    assert post.call_args_list[3].kwargs["params"] == {"access_token": "token-new"}


@pytest.mark.parametrize(
    ("code", "flag"),
    [(17, "quota"), (19, "quota"), (18, "rate")],
)
def test_quota_and_rate_errors_are_classified(tmp_path, code, flag):
    engine = BaiduOCREngine("api-key", "secret-key")
    image = make_image(tmp_path)

    with patch("services.cloud_ocr.requests.post") as post:
        post.side_effect = [
            response({"access_token": "token-1", "expires_in": 3600}),
            response({"error_code": code, "error_msg": "limit"}),
        ]
        with pytest.raises(CloudOCRError) as error:
            engine.extract_text(str(image))

    assert getattr(error.value, flag) is True
    assert error.value.code == str(code)


def test_missing_credentials_fail_without_network(tmp_path):
    engine = BaiduOCREngine("", "")
    image = make_image(tmp_path)

    with patch("services.cloud_ocr.requests.post") as post:
        with pytest.raises(CloudOCRError, match="API Key"):
            engine.extract_text(str(image))

    post.assert_not_called()


def test_test_connection_success_and_failure():
    engine = BaiduOCREngine("api-key", "secret-key")
    with patch("services.cloud_ocr.requests.post") as post:
        post.side_effect = [
            response({"access_token": "token-1", "expires_in": 3600}),
            response({"words_result": [{"words": "TEST 123"}]}),
        ]
        assert engine.test_connection() == (True, "百度 OCR 连接成功")
    assert post.call_count == 2
    assert post.call_args_list[1].args[0] == OCR_URL

    failing = BaiduOCREngine("api-key", "secret-key")
    with patch("services.cloud_ocr.requests.post", side_effect=requests.RequestException("offline")):
        success, message = failing.test_connection()
    assert success is False
    assert "offline" in message


def test_test_connection_reports_unavailable_ocr_service():
    engine = BaiduOCREngine("api-key", "secret-key")
    with patch("services.cloud_ocr.requests.post") as post:
        post.side_effect = [
            response({"access_token": "token-1", "expires_in": 3600}),
            response({"error_code": 6, "error_msg": "No permission to access data"}),
        ]
        success, message = engine.test_connection()

    assert success is False
    assert "No permission" in message


def test_extract_text_boxes_returns_empty_list():
    engine = BaiduOCREngine("api-key", "secret-key")
    assert engine.extract_text_boxes("ignored.png") == []
