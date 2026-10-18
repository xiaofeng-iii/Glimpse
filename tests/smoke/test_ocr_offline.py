"""Real PP-OCRv5-mobile smoke test for the packaged Windows runtime."""

import importlib.util
import platform
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCR_MODEL_DIR = PROJECT_ROOT / "assets" / "ocr"


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="The release sidecar and fixed CJK font fixture target Windows",
)
def test_ppocrv5_mobile_runs_from_bundled_models_on_cpu(tmp_path):
    pytest.importorskip("rapidocr")
    rapidocr_spec = importlib.util.find_spec("rapidocr")
    assert rapidocr_spec and rapidocr_spec.origin
    package_dir = Path(rapidocr_spec.origin).parent
    model_dir = package_dir / "models"
    assert (model_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx").is_file()
    if not (OCR_MODEL_DIR / "ch_PP-OCRv5_det_mobile.onnx").is_file():
        pytest.skip("PP-OCRv5-mobile models are not fetched; run scripts/fetch_ocr_models.py")
    assert (OCR_MODEL_DIR / "ch_PP-OCRv5_rec_mobile.onnx").is_file()

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

    engine = RapidOCREngine(model_dir=OCR_MODEL_DIR)
    with patch(
        "rapidocr.inference_engine.onnxruntime.main.DownloadFile.run",
        side_effect=AssertionError("runtime model download attempted"),
    ) as download_model:
        text = engine.extract_text(str(image_path))
    download_model.assert_not_called()
    raw_engine = engine._get_engine()

    assert text
    assert "Glimpse" in text
    assert "记忆" in text
    assert "2026" in text
    assert raw_engine.cfg.Det.engine_type.value == "onnxruntime"
    assert raw_engine.cfg.Det.ocr_version.value == "PP-OCRv5"
    assert raw_engine.cfg.Det.model_type.value == "mobile"
    assert raw_engine.cfg.Rec.engine_type.value == "onnxruntime"
    assert raw_engine.cfg.Rec.ocr_version.value == "PP-OCRv5"
    assert raw_engine.cfg.Rec.model_type.value == "mobile"
    assert raw_engine.cfg.Global.max_side_len == 4000
    assert raw_engine.cfg.Det.limit_side_len == 1280
    assert Path(str(raw_engine.cfg.Det.model_path)).resolve() == (
        OCR_MODEL_DIR / "ch_PP-OCRv5_det_mobile.onnx"
    ).resolve()
    assert Path(str(raw_engine.cfg.Cls.model_path)).resolve() == (
        model_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
    ).resolve()
    assert Path(str(raw_engine.cfg.Rec.model_path)).resolve() == (
        OCR_MODEL_DIR / "ch_PP-OCRv5_rec_mobile.onnx"
    ).resolve()
    assert (
        raw_engine.text_det.session.session.get_providers()
        == ["CPUExecutionProvider"]
    )
