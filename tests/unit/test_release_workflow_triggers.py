from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"


def _trigger_block(workflow_name: str) -> str:
    text = (WORKFLOWS_DIR / workflow_name).read_text(encoding="utf-8")
    trigger_start = text.index("on:\n")
    trigger_end = text.index("\npermissions:", trigger_start)
    return text[trigger_start:trigger_end]


def test_formal_release_only_accepts_stable_semver_tags():
    trigger = _trigger_block("release.yml")

    assert '"v[0-9]+.[0-9]+.[0-9]+"' in trigger
    assert "workflow_dispatch:" not in trigger


def test_preview_release_only_accepts_preview_tags():
    trigger = _trigger_block("preview-release.yml")

    preview_prefix = '"v[0-9]+.[0-9]+.[0-9]+-preview.'
    preview_date = '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
    assert f'{preview_prefix}{preview_date}"' in trigger
    assert f'{preview_prefix}{preview_date}.[0-9]+"' in trigger
    assert "workflow_dispatch:" not in trigger


def test_dev_release_is_manual_only():
    trigger = _trigger_block("dev-release.yml")

    assert "push:" not in trigger
    assert "workflow_dispatch:" in trigger
