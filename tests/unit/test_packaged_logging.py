import os
from pathlib import Path
import subprocess
import sys
import textwrap


def test_packaged_backend_initializes_logging_after_output_redirection(
    tmp_path: Path,
):
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(tmp_path)
    script = textwrap.dedent(
        """
        import logging
        import sys

        sys.stdout = None
        sys.stderr = None

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

    log_path = tmp_path / "Glimpse" / "logs" / "glimpse-runtime.log"
    assert result.returncode == 0
    assert log_path.is_file()
    log_text = log_path.read_text(encoding="utf-8")
    assert log_text.count("packaged-log-probe") == 1
    assert "--- Logging error ---" not in log_text
    assert "NoneType" not in log_text
