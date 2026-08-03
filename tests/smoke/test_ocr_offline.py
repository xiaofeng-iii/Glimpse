"""Real PP-OCRv6-small smoke test for the packaged Windows runtime."""

import importlib.util
import platform
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw, ImageFont


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="The release sidecar and fixed CJK font fixture target Windows",
)
def test_ppocrv6_small_runs_from_bundled_models_on_cpu(tmp_path):
    pytest.importorskip("rapidocr")
    rapidocr_spec = importlib.util.find_spec("rapidocr")
    assert rapidocr_spec and rapidocr_spec.origin
    package_dir = Path(rapidocr_spec.origin).parent
    model_dir = package_dir / "models"
    assert (model_dir / "PP-OCRv6_det_small.onnx").is_file()
    assert (model_dir / "PP-OCRv6_rec_small.onnx").is_file()
    assert (model_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx").is_file()

    font_path = Path(r"C:\Windows\Fonts\msyhbd.ttc")
    if not font_path.is_file():
        pytest.skip("Microsoft YaHei Bold is unavailable")

    image_path = tmp_path / "ocr-smoke.png"
    image = Image.new("RGB", (1400, 320), "white")
    draw = ImageDraw.Draw(image)
    draw.text(
        (50, 80),
        "Glimpse 本地记忆 2026",
        font=ImageFont.truetype(str(font_path), 72),
        fill="black",
    )
    image.save(image_path)

    from services.ocr_engine import RapidOCREngine

    engine = RapidOCREngine()
    with patch(
        "rapidocr.inference_engine.onnxruntime.main.DownloadFile.run",
        side_effect=AssertionError("runtime model download attempted"),
    ) as download_model:
        text = engine.extract_text(str(image_path))
    download_model.assert_not_called()
    raw_engine = engine._get_engine()

    assert text
    assert "Glimpse" in text
    assert "本地记忆" in text
    assert "2026" in text
    assert raw_engine.cfg.Det.engine_type.value == "onnxruntime"
    assert raw_engine.cfg.Det.ocr_version.value == "PP-OCRv6"
    assert raw_engine.cfg.Det.model_type.value == "small"
    assert raw_engine.cfg.Rec.engine_type.value == "onnxruntime"
    assert raw_engine.cfg.Rec.ocr_version.value == "PP-OCRv6"
    assert raw_engine.cfg.Rec.model_type.value == "small"
    assert Path(str(raw_engine.cfg.Det.model_path)).resolve() == (
        model_dir / "PP-OCRv6_det_small.onnx"
    ).resolve()
    assert Path(str(raw_engine.cfg.Cls.model_path)).resolve() == (
        model_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
    ).resolve()
    assert Path(str(raw_engine.cfg.Rec.model_path)).resolve() == (
        model_dir / "PP-OCRv6_rec_small.onnx"
    ).resolve()
    assert (
        raw_engine.text_det.session.session.get_providers()
        == ["CPUExecutionProvider"]
    )
