"""Unit tests for the RapidOCR 3.x adapter."""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.ocr_engine import (
    NativeOCREngine,
    OCREngine,
    RapidOCREngine,
    create_ocr_engine,
    ocr_engine,
)


def make_fake_rapidocr_module(tmp_path, rapid_ocr):
    package_dir = tmp_path / "rapidocr"
    package_dir.mkdir()
    package_file = package_dir / "__init__.py"
    package_file.write_text("", encoding="utf-8")
    return SimpleNamespace(
        __file__=str(package_file),
        RapidOCR=rapid_ocr,
        EngineType=SimpleNamespace(ONNXRUNTIME="onnxruntime"),
        LangDet=SimpleNamespace(CH="ch"),
        LangRec=SimpleNamespace(CH="ch"),
        ModelType=SimpleNamespace(SMALL="small"),
        OCRVersion=SimpleNamespace(PPOCRV6="PP-OCRv6"),
    )


def write_bundled_models(module):
    model_dir = Path(module.__file__).parent / "models"
    model_dir.mkdir()
    for filename in RapidOCREngine._MODEL_FILENAMES.values():
        (model_dir / filename).write_bytes(b"model")
    return model_dir.resolve()


class TestOCREngineABC:
    def test_abstract_class_cannot_instantiate(self):
        with pytest.raises(TypeError):
            OCREngine()

    def test_subclass_must_implement_abstracts(self):
        class IncompleteEngine(OCREngine):
            pass

        with pytest.raises(TypeError):
            IncompleteEngine()


class TestNativeOCREngine:
    def test_extract_text_delegates_to_fallback(self):
        fallback = MagicMock()
        fallback.extract_text.return_value = "文字"
        engine = NativeOCREngine()
        engine._fallback = fallback

        assert engine.extract_text("test.png") == "文字"
        fallback.extract_text.assert_called_once_with("test.png")

    def test_extract_text_boxes_delegates_to_fallback(self):
        fallback = MagicMock()
        fallback.extract_text_boxes.return_value = [("文字", (1, 2, 3, 4))]
        engine = NativeOCREngine()
        engine._fallback = fallback

        assert engine.extract_text_boxes("test.png") == [("文字", (1, 2, 3, 4))]


class TestRapidOCREngine:
    @pytest.fixture
    def engine(self):
        return RapidOCREngine()

    def test_extract_text_engine_not_available(self, engine):
        with patch.object(engine, "_get_engine", return_value=None):
            assert engine.extract_text("test.png") is None

    def test_extract_text_reads_dataclass_output(self, engine):
        mock_ocr = MagicMock()
        mock_ocr.return_value = SimpleNamespace(
            txts=(" Hello ", "World", " "),
            boxes=None,
        )

        with patch.object(engine, "_get_engine", return_value=mock_ocr):
            assert engine.extract_text("test.png") == "Hello\nWorld"

    def test_extract_text_empty_result(self, engine):
        mock_ocr = MagicMock()
        mock_ocr.return_value = SimpleNamespace(txts=None, boxes=None)

        with patch.object(engine, "_get_engine", return_value=mock_ocr):
            assert engine.extract_text("test.png") is None

    def test_extract_text_boxes_converts_four_points_to_rectangle(self, engine):
        mock_ocr = MagicMock()
        mock_ocr.return_value = SimpleNamespace(
            txts=("Hello",),
            boxes=(
                (
                    (10.8, 9.2),
                    (101.2, 11.0),
                    (99.7, 31.9),
                    (9.5, 29.1),
                ),
            ),
        )

        with patch.object(engine, "_get_engine", return_value=mock_ocr):
            assert engine.extract_text_boxes("test.png") == [
                ("Hello", (9, 9, 102, 32))
            ]

    def test_extract_text_boxes_ignores_malformed_boxes(self, engine):
        mock_ocr = MagicMock()
        mock_ocr.return_value = SimpleNamespace(
            txts=("bad", "good"),
            boxes=(("invalid",), ((1, 2), (3, 2), (3, 4), (1, 4))),
        )

        with patch.object(engine, "_get_engine", return_value=mock_ocr):
            assert engine.extract_text_boxes("test.png") == [
                ("good", (1, 2, 3, 4))
            ]

    def test_inference_exception_is_a_soft_failure(self, engine):
        mock_ocr = MagicMock(side_effect=RuntimeError("bad image"))

        with patch.object(engine, "_get_engine", return_value=mock_ocr):
            assert engine.extract_text("test.png") is None
            assert engine.extract_text_boxes("test.png") == []

    def test_inference_is_serialized_for_a_single_engine(self, engine):
        state_lock = Lock()
        active = 0
        max_active = 0

        def infer(_image_path):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.03)
            with state_lock:
                active -= 1
            return SimpleNamespace(txts=("text",), boxes=None)

        with patch.object(engine, "_get_engine", return_value=infer):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(engine.extract_text, ("one.png", "two.png")))

        assert results == ["text", "text"]
        assert max_active == 1

    def test_engine_is_lazy_and_uses_fixed_ppocrv6_cpu_configuration(
        self,
        engine,
        tmp_path,
    ):
        rapid_ocr = MagicMock(return_value=MagicMock())
        module = make_fake_rapidocr_module(tmp_path, rapid_ocr)
        model_dir = write_bundled_models(module)

        assert engine._engine is None
        with patch.dict("sys.modules", {"rapidocr": module}):
            loaded = engine._get_engine()

        assert loaded is rapid_ocr.return_value
        params = rapid_ocr.call_args.kwargs["params"]
        assert params["Det.engine_type"] == "onnxruntime"
        assert params["Det.model_type"] == "small"
        assert params["Det.ocr_version"] == "PP-OCRv6"
        assert params["Rec.engine_type"] == "onnxruntime"
        assert params["Rec.model_type"] == "small"
        assert params["Rec.ocr_version"] == "PP-OCRv6"
        assert params["Det.model_path"] == str(
            model_dir / "PP-OCRv6_det_small.onnx"
        )
        assert params["Cls.model_path"] == str(
            model_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
        )
        assert params["Rec.model_path"] == str(
            model_dir / "PP-OCRv6_rec_small.onnx"
        )
        assert all(
            Path(params[key]).is_absolute()
            for key in RapidOCREngine._MODEL_FILENAMES
        )
        assert params["EngineConfig.onnxruntime.use_cuda"] is False
        assert params["EngineConfig.onnxruntime.use_dml"] is False

    def test_missing_bundled_model_soft_fails_before_any_network_call(
        self,
        engine,
        tmp_path,
    ):
        rapid_ocr = MagicMock()
        module = make_fake_rapidocr_module(tmp_path, rapid_ocr)
        model_dir = Path(module.__file__).parent / "models"
        model_dir.mkdir()
        (model_dir / "PP-OCRv6_det_small.onnx").write_bytes(b"model")

        with (
            patch.dict("sys.modules", {"rapidocr": module}),
            patch("socket.create_connection") as create_connection,
            patch("urllib.request.urlopen") as urlopen,
        ):
            assert engine._get_engine() is None

        rapid_ocr.assert_not_called()
        create_connection.assert_not_called()
        urlopen.assert_not_called()

    def test_import_error_is_cached_as_unavailable(self, engine):
        with patch.dict("sys.modules", {"rapidocr": None}):
            assert engine._get_engine() is None
            assert engine._initialization_attempted is True
            assert engine._get_engine() is None


class TestCreateOCREngine:
    def test_create_rapidocr_default(self):
        assert isinstance(create_ocr_engine(), RapidOCREngine)

    def test_create_rapidocr_explicit(self):
        assert isinstance(create_ocr_engine("rapidocr"), RapidOCREngine)

    def test_create_native(self):
        assert isinstance(create_ocr_engine("native"), NativeOCREngine)

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown OCR engine type"):
            create_ocr_engine("unknown_engine")


def test_global_ocr_engine_is_rapidocr():
    assert isinstance(ocr_engine, RapidOCREngine)
