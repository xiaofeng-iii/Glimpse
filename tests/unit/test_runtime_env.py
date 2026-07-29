from pathlib import Path

from runtime_env import get_app_version


def test_get_app_version_prefers_environment_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GLIMPSE_APP_VERSION", "9.8.7")

    assert get_app_version(tmp_path) == "9.8.7"


def test_get_app_version_reads_cargo_package_version(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GLIMPSE_APP_VERSION", raising=False)
    manifest = tmp_path / "glimpse-frontend" / "src-tauri" / "Cargo.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '[package]\nname = "glimpse"\nversion = "0.1.4"\n\n[dependencies]\n',
        encoding="utf-8",
    )

    assert get_app_version(tmp_path) == "0.1.4"


def test_get_app_version_uses_development_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GLIMPSE_APP_VERSION", raising=False)

    assert get_app_version(tmp_path) == "development"
