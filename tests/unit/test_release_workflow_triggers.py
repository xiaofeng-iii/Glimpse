from pathlib import Path

import pytest


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


def test_preview_release_only_accepts_beta_tags():
    trigger = _trigger_block("preview-release.yml")

    assert '"v[0-9]+.[0-9]+.[0-9]+-beta.[0-9]+"' in trigger
    assert "-preview." not in trigger
    assert "workflow_dispatch:" not in trigger


def test_dev_release_is_manual_only():
    trigger = _trigger_block("dev-release.yml")

    assert "push:" not in trigger
    assert "workflow_dispatch:" in trigger


def test_release_build_selects_the_desktop_executable():
    package = (PROJECT_ROOT / "glimpse-frontend" / "package.json").read_text(encoding="utf-8")
    manifest = (PROJECT_ROOT / "glimpse-frontend" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    assert '"tauri:build": "npm run build:backend && tauri build"' in package
    assert 'default-run = "glimpse"' in manifest
    config = (PROJECT_ROOT / "glimpse-frontend" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    assert '"mainBinaryName": "glimpse"' in config


@pytest.mark.parametrize("workflow_name", ["release.yml", "preview-release.yml"])
def test_release_checks_packaged_main_executable(workflow_name):
    text = (WORKFLOWS_DIR / workflow_name).read_text(encoding="utf-8")
    assert "Verify packaged main executable" in text
    assert "target/release/glimpse.exe" in text

def test_updater_pages_rebuilds_when_a_release_is_edited():
    trigger = _trigger_block("updater-pages.yml")

    assert "release:" in trigger
    assert "types: [edited]" in trigger
