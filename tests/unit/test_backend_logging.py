import logging
import sys
from pathlib import Path

import pytest

from utils import logger as logger_module


@pytest.fixture()
def reset_logging():
    """Isolate each test from the auto-configured root logger."""
    root = logging.getLogger()
    handlers = root.handlers[:]
    yield root
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)


def _write_probe(log_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(logger_module, "MAX_LOG_BYTES", 4096)
    monkeypatch.setattr(logger_module, "LOG_BACKUP_COUNT", 3)
    logger_module.setup_logging(log_file=log_path)
    probe = logger_module.get_logger("probe")

    for index in range(200):
        probe.info("rotation-probe-%03d %s", index, "x" * 64)
    logging.shutdown()


def test_rotates_glimpse_log_by_size(tmp_path, reset_logging, monkeypatch):
    monkeypatch.setenv("GLIMPSE_SESSION_ID", "session-rotation")
    log_path = tmp_path / "logs" / "glimpse.log"
    _write_probe(log_path, monkeypatch)

    backups = sorted(path.name for path in log_path.parent.glob("glimpse.log.*"))
    assert log_path.is_file()
    assert log_path.stat().st_size <= 4096 + 4096  # active file + one overshoot record
    assert 0 < len(backups) <= 3
    assert backups == [f"glimpse.log.{index + 1}" for index in range(len(backups))]

    oldest = (log_path.parent / backups[0]).read_text(encoding="utf-8").splitlines()
    assert oldest
    assert "[session:session-rotation]" in oldest[0]


def test_formatted_parameters_and_tracebacks_are_redacted(tmp_path, reset_logging):
    log_path = tmp_path / 'glimpse.log'
    logger_module.setup_logging(log_file=log_path)
    probe = logger_module.get_logger('probe')
    probe.info('request %s api_key=%s', 'https://alice:pass-secret@host/v1?token=query-secret&model=demo', 'key-secret')
    try:
        raise RuntimeError('Authorization: Bearer traceback-secret')
    except RuntimeError:
        probe.exception('failed token=%s', 'param-secret')
    for handler in reset_logging.handlers:
        handler.flush()
    output = log_path.read_text(encoding='utf-8')
    for secret in ['alice', 'pass-secret', 'query-secret', 'key-secret', 'traceback-secret', 'param-secret']:
        assert secret not in output
    assert 'host/v1' in output
    assert 'model=demo' in output
    assert 'RuntimeError' in output


def test_session_id_defaults_to_placeholder(tmp_path, reset_logging, monkeypatch):
    monkeypatch.delenv("GLIMPSE_SESSION_ID", raising=False)
    log_path = tmp_path / "logs" / "glimpse.log"
    _write_probe(log_path, monkeypatch)

    assert "[session:-]" in log_path.read_text(encoding="utf-8")
