import os
from pathlib import Path
import subprocess
import sys
import textwrap


def test_packaged_backend_uses_file_logging_with_console_streams(
    tmp_path: Path,
):
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(tmp_path)
    env.pop("GLIMPSE_DATA_ROOT", None)
    script = textwrap.dedent(
        """
        import logging
        import sys

        # Match the packaged --console sidecar: streams are present. Python
        # must still use only its structured file handler when log_file is set.
        sys.frozen = True

        import main_api

        main_api.logger.info("packaged-log-probe")
        logging.shutdown()
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    log_path = tmp_path / "Glimpse" / "GlimpseData" / "logs" / "glimpse.log"
    legacy_log_path = tmp_path / "Glimpse" / "logs" / "glimpse-runtime.log"
    assert result.returncode == 0, result.stderr or result.stdout
    assert log_path.is_file()
    assert not legacy_log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert log_text.count("packaged-log-probe") == 1
    assert "packaged-log-probe" not in result.stdout
    assert "packaged-log-probe" not in result.stderr
    assert "--- Logging error ---" not in log_text
    assert "NoneType" not in log_text


def test_source_backend_uses_path_manager_log_file(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[2]
    data_root = tmp_path / "GlimpseData"
    env = os.environ.copy()
    env["GLIMPSE_DATA_ROOT"] = str(data_root)
    script = textwrap.dedent(
        """
        import logging

        import main_api

        main_api.logger.info("source-log-probe")
        logging.shutdown()
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    log_path = data_root / "logs" / "glimpse.log"
    assert result.returncode == 0, result.stderr or result.stdout
    assert log_path.is_file()
    log_text = log_path.read_text(encoding="utf-8")
    assert log_text.count("source-log-probe") == 1
    assert "source-log-probe" not in result.stdout
    assert "source-log-probe" not in result.stderr
