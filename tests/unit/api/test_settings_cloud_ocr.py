"""Tests for the Baidu Cloud OCR settings test endpoint."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from api.routes.settings import test_cloud_ocr as cloud_ocr_test_endpoint
from api.schemas import OCRCloudTestRequest


def test_cloud_ocr_test_uses_draft_credentials():
    engine = MagicMock()
    engine.test_connection.return_value = (True, "ok")
    settings_manager = MagicMock()
    with (
        patch("api.routes.settings.get_settings_manager", return_value=settings_manager),
        patch(
            "api.routes.settings.get_effective_settings",
            return_value={"ocr": {"timeout": 30}},
        ),
        patch("api.routes.settings.BaiduOCREngine", return_value=engine) as factory,
    ):
        response = asyncio.run(
            cloud_ocr_test_endpoint(OCRCloudTestRequest(api_key="api", secret_key="secret"))
        )

    assert response.success is True
    assert response.message == "ok"
    factory.assert_called_once_with("api", "secret", 30)
    engine.test_connection.assert_called_once()


def test_cloud_ocr_test_rejects_missing_credentials():
    settings_manager = MagicMock()
    with (
        patch("api.routes.settings.get_settings_manager", return_value=settings_manager),
        patch(
            "api.routes.settings.get_effective_settings",
            return_value={"ocr": {"api_key": "", "secret_key": "", "timeout": 30}},
        ),
        patch("api.routes.settings.BaiduOCREngine") as factory,
    ):
        response = asyncio.run(cloud_ocr_test_endpoint(OCRCloudTestRequest()))

    assert response.success is False
    assert "API Key" in response.message
    factory.assert_not_called()


def test_cloud_ocr_test_reports_auth_failure():
    engine = MagicMock()
    engine.test_connection.return_value = (False, "鉴权失败")
    with (
        patch("api.routes.settings.get_settings_manager", return_value=MagicMock()),
        patch(
            "api.routes.settings.get_effective_settings",
            return_value={"ocr": {"timeout": 30}},
        ),
        patch("api.routes.settings.BaiduOCREngine", return_value=engine),
    ):
        response = asyncio.run(
            cloud_ocr_test_endpoint(OCRCloudTestRequest(api_key="api", secret_key="secret"))
        )

    assert response.success is False
    assert response.message == "鉴权失败"
