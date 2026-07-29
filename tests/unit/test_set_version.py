import json
from pathlib import Path

import pytest

from scripts.set_version import (
    CARGO_LOCK,
    CARGO_MANIFEST,
    PYPROJECT,
    VersionSyncError,
    check_versions,
    sync_versions,
    validate_version,
)


def _write_version_fixture(
    root: Path,
    *,
    cargo_version: str = "0.1.4",
    python_version: str = "0.1.4",
    lock_version: str = "0.1.4",
) -> None:
    cargo_manifest = root / CARGO_MANIFEST
    cargo_manifest.parent.mkdir(parents=True)
    cargo_manifest.write_bytes(
        (
            "[package]\r\n"
            'name = "glimpse"\r\n'
            f'version = "{cargo_version}"\r\n'
            "\r\n"
            "[dependencies]\r\n"
            'serde = "1"\r\n'
        ).encode()
    )

    (root / PYPROJECT).write_text(
        (
            "[build-system]\n"
            'requires = ["setuptools"]\n'
            "\n"
            "[project]\n"
            'name = "glimpse"\n'
            f'version = "{python_version}"\n'
        ),
        encoding="utf-8",
    )

    (root / CARGO_LOCK).write_text(
        (
            "[[package]]\n"
            'name = "dependency"\n'
            'version = "9.9.9"\n'
            "\n"
            "[[package]]\n"
            'name = "glimpse"\n'
            f'version = "{lock_version}"\n'
            "dependencies = []\n"
        ),
        encoding="utf-8",
    )

    frontend = root / "glimpse-frontend"
    (frontend / "package.json").write_text(
        json.dumps({"name": "glimpse-frontend", "private": True}),
        encoding="utf-8",
    )
    (frontend / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "glimpse-frontend",
                "lockfileVersion": 3,
                "packages": {"": {"name": "glimpse-frontend"}},
            }
        ),
        encoding="utf-8",
    )
    (cargo_manifest.parent / "tauri.conf.json").write_text(
        json.dumps({"productName": "Glimpse"}),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "version",
    ["v0.1.5", "0.1", "0.1.5-beta.1", "01.2.3", "1.2.3.4"],
)
def test_validate_version_rejects_non_stable_semver(version: str):
    with pytest.raises(VersionSyncError):
        validate_version(version)


def test_sync_versions_updates_sources_and_cargo_lock(tmp_path: Path):
    _write_version_fixture(tmp_path)

    changed = sync_versions("0.1.5", tmp_path)

    assert set(changed) == {CARGO_MANIFEST, PYPROJECT, CARGO_LOCK}
    assert check_versions(tmp_path, expected="0.1.5") == "0.1.5"
    assert b"\r\n" in (tmp_path / CARGO_MANIFEST).read_bytes()
    cargo_lock = (tmp_path / CARGO_LOCK).read_text(encoding="utf-8")
    assert 'name = "dependency"\nversion = "9.9.9"' in cargo_lock


def test_sync_versions_dry_run_does_not_write_files(tmp_path: Path):
    _write_version_fixture(tmp_path)
    before = (tmp_path / CARGO_MANIFEST).read_bytes()

    changed = sync_versions("0.1.5", tmp_path, dry_run=True)

    assert changed
    assert (tmp_path / CARGO_MANIFEST).read_bytes() == before
    assert check_versions(tmp_path, expected="0.1.4") == "0.1.4"


def test_check_versions_reports_metadata_drift(tmp_path: Path):
    _write_version_fixture(tmp_path, python_version="0.1.3")

    with pytest.raises(VersionSyncError, match="inconsistent"):
        check_versions(tmp_path)


def test_check_versions_rejects_reintroduced_duplicate_version(tmp_path: Path):
    _write_version_fixture(tmp_path)
    package_json = tmp_path / "glimpse-frontend" / "package.json"
    package_json.write_text(
        json.dumps(
            {"name": "glimpse-frontend", "version": "0.1.4", "private": True}
        ),
        encoding="utf-8",
    )

    with pytest.raises(VersionSyncError, match="redundant"):
        check_versions(tmp_path)
