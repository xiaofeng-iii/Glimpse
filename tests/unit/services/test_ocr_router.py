"""Tests for the local/cloud OCR routing engine."""
from __future__ import annotations

from unittest.mock import MagicMock

from services.ocr_router import ConfiguredOCREngine


class FakeSettingsManager:
    def __init__(self, ocr):
        self.ocr = ocr

    def get_all(self):
        return {"ocr": self.ocr}


def make_router(ocr, *, cloud=None):
    local = MagicMock()
    local.extract_text.return_value = "local-text"
    local.extract_text_boxes.return_value = [("local", (1, 2, 3, 4))]
    cloud = cloud or MagicMock()
    factory = MagicMock(return_value=cloud)
    router = ConfiguredOCREngine(
        FakeSettingsManager(ocr),
        local_engine=local,
        cloud_factory=factory,
    )
    return router, local, cloud, factory


def test_local_mode_uses_local_engine():
    router, local, cloud, factory = make_router({"mode": "local"})

    assert router.extract_text("shot.png") == "local-text"

    local.extract_text.assert_called_once_with("shot.png")
    cloud.extract_text.assert_not_called()
    factory.assert_not_called()


def test_cloud_mode_uses_cloud_engine_when_credentials_exist():
    ocr = {
        "mode": "cloud",
        "provider": "baidu",
        "api_key": "key",
        "secret_key": "secret",
        "timeout": 20,
    }
    router, local, cloud, factory = make_router(ocr)
    cloud.extract_text.return_value = "cloud-text"

    assert router.extract_text("shot.png") == "cloud-text"

    factory.assert_called_once_with("key", "secret", 20)
    cloud.extract_text.assert_called_once_with("shot.png")
    local.extract_text.assert_not_called()


def test_cloud_engine_is_cached_by_credentials():
    ocr = {
        "mode": "cloud",
        "provider": "baidu",
        "api_key": "key",
        "secret_key": "secret",
        "timeout": 20,
    }
    router, local, cloud, factory = make_router(ocr)
    cloud.extract_text.return_value = "cloud-text"

    router.extract_text("one.png")
    router.extract_text("two.png")

    factory.assert_called_once()
    assert cloud.extract_text.call_count == 2
    local.extract_text.assert_not_called()


def test_cloud_text_missing_falls_back_to_local():
    ocr = {
        "mode": "cloud",
        "provider": "baidu",
        "api_key": "key",
        "secret_key": "secret",
        "timeout": 20,
    }
    router, local, cloud, _ = make_router(ocr)
    cloud.extract_text.return_value = None

    assert router.extract_text("shot.png") == "local-text"

    local.extract_text.assert_called_once_with("shot.png")


def test_cloud_exception_falls_back_to_local():
    ocr = {
        "mode": "cloud",
        "provider": "baidu",
        "api_key": "key",
        "secret_key": "secret",
        "timeout": 20,
    }
    router, local, cloud, _ = make_router(ocr)
    cloud.extract_text.side_effect = RuntimeError("quota exceeded")

    assert router.extract_text("shot.png") == "local-text"

    local.extract_text.assert_called_once_with("shot.png")


def test_cloud_mode_without_credentials_uses_local():
    router, local, cloud, factory = make_router(
        {"mode": "cloud", "provider": "baidu", "api_key": "", "secret_key": ""}
    )

    assert router.extract_text("shot.png") == "local-text"

    factory.assert_not_called()
    cloud.extract_text.assert_not_called()
    local.extract_text.assert_called_once_with("shot.png")


def test_text_boxes_always_use_local_engine():
    router, local, _, _ = make_router({"mode": "local"})

    assert router.extract_text_boxes("shot.png") == [("local", (1, 2, 3, 4))]
    local.extract_text_boxes.assert_called_once_with("shot.png")
