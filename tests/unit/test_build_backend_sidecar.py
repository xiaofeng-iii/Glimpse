from pathlib import Path

import pytest

from scripts import build_backend_sidecar as sidecar


def _write_manifest(path: Path, version: str = "1.2.3") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "[package]\n"
            'name = "glimpse"\n'
            f'version = "{version}"\n'
            "\n"
            "[dependencies]\n"
            'serde = "1"\n'
        ),
        encoding="utf-8",
    )


def test_sidecar_uses_branded_name_and_cache_inputs():
    assert sidecar.BUILD_NAME == "GlimpseRuntime"
    assert sidecar.sidecar_output_dir().name == "GlimpseRuntime"
    assert sidecar.sidecar_exe_path().name == "GlimpseRuntime.exe"
    assert "assets/icons/glimpse.ico" in sidecar.HASH_INPUTS
    assert "glimpse-frontend/src-tauri/Cargo.toml" in sidecar.HASH_INPUTS
    assert "utils" in sidecar.HASH_INPUTS


def test_sidecar_collects_rapidocr_code_models_metadata_and_onnx_runtime():
    assert "rapidocr" in sidecar.PYINSTALLER_DYNAMIC_PACKAGES
    assert "rapidocr" in sidecar.PYINSTALLER_DATA_PACKAGES
    assert "rapidocr" in sidecar.PYINSTALLER_METADATA_PACKAGES
    assert "onnxruntime" in sidecar.PYINSTALLER_DYNAMIC_PACKAGES
    assert "onnxruntime" in sidecar.PYINSTALLER_DATA_PACKAGES
    assert "onnxruntime" in sidecar.PYINSTALLER_METADATA_PACKAGES


def test_read_package_version_reads_canonical_cargo_version(tmp_path: Path):
    manifest = tmp_path / "Cargo.toml"
    _write_manifest(manifest, "3.4.5")

    assert sidecar.read_package_version(manifest) == "3.4.5"


def test_read_package_version_rejects_non_stable_version(tmp_path: Path):
    manifest = tmp_path / "Cargo.toml"
    _write_manifest(manifest, "3.4.5-beta.1")

    with pytest.raises(RuntimeError, match="stable x.y.z"):
        sidecar.read_package_version(manifest)


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "1.2.3.4", "65536.1.1"])
def test_windows_version_tuple_rejects_invalid_version(version: str):
    with pytest.raises(ValueError):
        sidecar.windows_version_tuple(version)


def test_write_windows_version_file_contains_branded_metadata(tmp_path: Path):
    output = tmp_path / "version-info.txt"

    result = sidecar.write_windows_version_file("1.2.3", output)

    assert result == output
    text = output.read_text(encoding="utf-8")
    assert "filevers=(1, 2, 3, 0)" in text
    assert "prodvers=(1, 2, 3, 0)" in text
    assert "StringStruct(u'CompanyName', u'Glimpse Team')" in text
    assert "StringStruct(u'FileDescription', u'Glimpse 核心服务')" in text
    assert "StringStruct(u'InternalName', u'GlimpseRuntime')" in text
    assert "StringStruct(u'OriginalFilename', u'GlimpseRuntime.exe')" in text
    assert "StringStruct(u'ProductName', u'Glimpse')" in text
    assert "StringStruct(u'ProductVersion', u'1.2.3')" in text
    assert "VarStruct(u'Translation', [2052, 1200])" in text


def test_build_pyinstaller_args_include_windows_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    icon = tmp_path / "glimpse.ico"
    icon.write_bytes(b"icon")
    version_file = tmp_path / "version-info.txt"
    version_file.write_text("version", encoding="utf-8")
    monkeypatch.setattr(sidecar, "APP_ICON", icon)
    monkeypatch.setattr(sidecar, "read_package_version", lambda: "1.2.3")
    monkeypatch.setattr(
        sidecar,
        "write_windows_version_file",
        lambda _version: version_file,
    )

    args = sidecar.build_pyinstaller_args(
        sidecar.BUILD_NAME,
        ["hidden.module"],
        [("data-source", "data-destination")],
        [("binary-source", "binary-destination")],
        is_windows=True,
    )

    assert "--name=GlimpseRuntime" in args
    assert "--onedir" in args
    assert "--console" in args
    assert "--noconsole" not in args
    assert f"--icon={icon}" in args
    assert f"--version-file={version_file}" in args
    assert "--hidden-import=hidden.module" in args


def test_non_windows_args_skip_windows_metadata(monkeypatch: pytest.MonkeyPatch):
    def fail_if_called():
        raise AssertionError("Windows metadata must not be generated")

    monkeypatch.setattr(sidecar, "read_package_version", fail_if_called)

    args = sidecar.build_pyinstaller_args(
        sidecar.BUILD_NAME,
        [],
        [],
        [],
        is_windows=False,
    )

    assert not any(arg.startswith("--icon=") for arg in args)
    assert not any(arg.startswith("--version-file=") for arg in args)


def test_desktop_bundle_uses_runtime_name_and_cleans_legacy_sidecars():
    project_root = Path(__file__).resolve().parents[2]
    tauri_config = (
        project_root / "glimpse-frontend" / "src-tauri" / "tauri.conf.json"
    ).read_text(encoding="utf-8")
    rust_main = (
        project_root / "glimpse-frontend" / "src-tauri" / "src" / "main.rs"
    ).read_text(encoding="utf-8")
    installer_hooks = (
        project_root / "glimpse-frontend" / "src-tauri" / "installer-hooks.nsh"
    ).read_text(encoding="utf-8")

    assert '"binaries/GlimpseRuntime/"' in tauri_config
    assert 'const BACKEND_BUNDLE_NAME: &str = "GlimpseRuntime";' in rust_main
    assert 'const BACKEND_PROCESS_NAME: &str = "GlimpseRuntime.exe";' in rust_main
    assert "const CREATE_NO_WINDOW: u32 = 0x08000000;" in rust_main
    assert "command.creation_flags(CREATE_NO_WINDOW);" in rust_main
    assert 'command.stdout(Stdio::from(stdout_log));' in rust_main
    assert 'command.stderr(Stdio::from(stderr_log));' in rust_main
    assert '.join("GlimpseData")' in rust_main
    assert '.join("logs")' in rust_main
    assert '.join("glimpse-sidecar.out.log")' in rust_main
    assert '("glimpse-backend", "glimpse-backend.exe")' in rust_main
    assert '("python-backend", "python-backend.exe")' in rust_main
    assert "GlimpseRuntime.exe" in installer_hooks
    assert "glimpse-backend.exe" in installer_hooks
    assert "python-backend.exe" in installer_hooks
    assert 'binaries\\GlimpseRuntime"' in installer_hooks
    assert 'binaries\\glimpse-backend"' in installer_hooks
    assert 'binaries\\python-backend"' in installer_hooks
