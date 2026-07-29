#!/usr/bin/env python
"""Synchronize and validate Glimpse application version metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

CARGO_MANIFEST = Path("glimpse-frontend/src-tauri/Cargo.toml")
CARGO_LOCK = Path("glimpse-frontend/src-tauri/Cargo.lock")
PYPROJECT = Path("pyproject.toml")


class VersionSyncError(ValueError):
    """Raised when version metadata is missing, duplicated, or inconsistent."""


def validate_version(version: str) -> str:
    version = version.strip()
    if not SEMVER_PATTERN.fullmatch(version):
        raise VersionSyncError(
            f"Invalid version {version!r}; expected stable SemVer MAJOR.MINOR.PATCH "
            "(for example 0.1.5)."
        )
    return version


def _read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except FileNotFoundError as exc:
        raise VersionSyncError(f"Required version file is missing: {path}") from exc
    except UnicodeDecodeError as exc:
        raise VersionSyncError(f"Version file is not valid UTF-8: {path}") from exc


def _table_matches(text: str, header: str) -> list[re.Match[str]]:
    pattern = re.compile(
        rf"(?ms)^{re.escape(header)}[ \t]*(?:\r?\n|$).*?(?=^\[|\Z)"
    )
    return list(pattern.finditer(text))


def _read_assignment(table: str, key: str, source: Path) -> str:
    pattern = re.compile(
        rf'(?m)^[ \t]*{re.escape(key)}[ \t]*=[ \t]*"(?P<value>[^"]+)"'
        r"[ \t]*(?:#[^\r\n]*)?\r?$"
    )
    matches = list(pattern.finditer(table))
    if len(matches) != 1:
        raise VersionSyncError(
            f"Expected exactly one {key!r} assignment in {source}, found {len(matches)}."
        )
    return matches[0].group("value")


def _replace_assignment(table: str, key: str, value: str, source: Path) -> str:
    pattern = re.compile(
        rf'(?m)^(?P<prefix>[ \t]*{re.escape(key)}[ \t]*=[ \t]*)'
        r'"[^"]+"(?P<suffix>[ \t]*(?:#[^\r\n]*)?)(?P<cr>\r?)$'
    )
    matches = list(pattern.finditer(table))
    if len(matches) != 1:
        raise VersionSyncError(
            f"Expected exactly one {key!r} assignment in {source}, found {len(matches)}."
        )
    return pattern.sub(
        lambda match: (
            f'{match.group("prefix")}"{value}"'
            f'{match.group("suffix")}{match.group("cr")}'
        ),
        table,
        count=1,
    )


def _read_table_version(text: str, header: str, source: Path) -> str:
    matches = _table_matches(text, header)
    if len(matches) != 1:
        raise VersionSyncError(
            f"Expected exactly one {header} table in {source}, found {len(matches)}."
        )
    return _read_assignment(matches[0].group(0), "version", source)


def _replace_table_version(text: str, header: str, version: str, source: Path) -> str:
    matches = _table_matches(text, header)
    if len(matches) != 1:
        raise VersionSyncError(
            f"Expected exactly one {header} table in {source}, found {len(matches)}."
        )

    match = matches[0]
    replacement = _replace_assignment(match.group(0), "version", version, source)
    return f"{text[:match.start()]}{replacement}{text[match.end():]}"


def _find_cargo_lock_package(text: str, package_name: str, source: Path) -> re.Match[str]:
    matches = [
        match
        for match in _table_matches(text, "[[package]]")
        if _read_assignment(match.group(0), "name", source) == package_name
    ]
    if len(matches) != 1:
        raise VersionSyncError(
            f"Expected exactly one Cargo.lock package named {package_name!r}, "
            f"found {len(matches)}."
        )
    return matches[0]


def _read_cargo_lock_version(text: str, source: Path) -> str:
    package = _find_cargo_lock_package(text, "glimpse", source)
    return _read_assignment(package.group(0), "version", source)


def _replace_cargo_lock_version(text: str, version: str, source: Path) -> str:
    package = _find_cargo_lock_package(text, "glimpse", source)
    replacement = _replace_assignment(package.group(0), "version", version, source)
    return f"{text[:package.start()]}{replacement}{text[package.end():]}"


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise VersionSyncError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VersionSyncError(f"Expected a JSON object in {path}.")
    return value


def _validate_removed_version_fields(project_root: Path) -> None:
    package_json_path = project_root / "glimpse-frontend" / "package.json"
    package_lock_path = project_root / "glimpse-frontend" / "package-lock.json"
    tauri_config_path = project_root / "glimpse-frontend" / "src-tauri" / "tauri.conf.json"

    if package_json_path.exists() and "version" in _load_json(package_json_path):
        raise VersionSyncError(
            f"Remove the redundant top-level 'version' field from {package_json_path}."
        )

    if tauri_config_path.exists() and "version" in _load_json(tauri_config_path):
        raise VersionSyncError(
            f"Remove the redundant top-level 'version' field from {tauri_config_path}."
        )

    if package_lock_path.exists():
        package_lock = _load_json(package_lock_path)
        root_package = package_lock.get("packages", {}).get("", {})
        if "version" in package_lock or (
            isinstance(root_package, dict) and "version" in root_package
        ):
            raise VersionSyncError(
                f"Remove the redundant root package version fields from {package_lock_path}."
            )


def get_versions(project_root: Path = PROJECT_ROOT) -> dict[Path, str]:
    cargo_manifest = project_root / CARGO_MANIFEST
    pyproject = project_root / PYPROJECT
    cargo_lock = project_root / CARGO_LOCK

    return {
        CARGO_MANIFEST: _read_table_version(
            _read_text(cargo_manifest), "[package]", cargo_manifest
        ),
        PYPROJECT: _read_table_version(_read_text(pyproject), "[project]", pyproject),
        CARGO_LOCK: _read_cargo_lock_version(_read_text(cargo_lock), cargo_lock),
    }


def check_versions(project_root: Path = PROJECT_ROOT, expected: str | None = None) -> str:
    versions = get_versions(project_root)
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        details = ", ".join(f"{path}={version}" for path, version in versions.items())
        raise VersionSyncError(f"Version metadata is inconsistent: {details}")

    version = validate_version(unique_versions.pop())
    if expected is not None and version != validate_version(expected):
        raise VersionSyncError(
            f"Version metadata is {version}, but the expected version is {expected}."
        )

    _validate_removed_version_fields(project_root)
    return version


def sync_versions(
    version: str,
    project_root: Path = PROJECT_ROOT,
    *,
    dry_run: bool = False,
) -> list[Path]:
    version = validate_version(version)
    cargo_manifest = project_root / CARGO_MANIFEST
    pyproject = project_root / PYPROJECT
    cargo_lock = project_root / CARGO_LOCK

    current = {
        CARGO_MANIFEST: _read_text(cargo_manifest),
        PYPROJECT: _read_text(pyproject),
        CARGO_LOCK: _read_text(cargo_lock),
    }
    rendered = {
        CARGO_MANIFEST: _replace_table_version(
            current[CARGO_MANIFEST], "[package]", version, cargo_manifest
        ),
        PYPROJECT: _replace_table_version(
            current[PYPROJECT], "[project]", version, pyproject
        ),
        CARGO_LOCK: _replace_cargo_lock_version(
            current[CARGO_LOCK], version, cargo_lock
        ),
    }

    changed = [
        relative_path
        for relative_path in rendered
        if rendered[relative_path] != current[relative_path]
    ]
    _validate_removed_version_fields(project_root)

    if not dry_run:
        for relative_path in changed:
            (project_root / relative_path).write_bytes(rendered[relative_path].encode("utf-8"))
        check_versions(project_root, expected=version)

    return changed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize Glimpse version metadata from one version argument."
    )
    parser.add_argument("version", nargs="?", help="Target stable SemVer, such as 0.1.5")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that all version metadata is synchronized without changing files.",
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="Print the current synchronized version without changing files.",
    )
    parser.add_argument(
        "--expected",
        help="With --check, require this exact stable SemVer.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would change without writing them.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=PROJECT_ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    selected_actions = sum((args.version is not None, args.check, args.current))
    if selected_actions != 1:
        parser.error("choose exactly one action: VERSION, --check, or --current")
    if args.expected and not args.check:
        parser.error("--expected can only be used with --check")
    if args.dry_run and args.version is None:
        parser.error("--dry-run can only be used with VERSION")

    project_root = args.repo_root.resolve()
    try:
        if args.version is not None:
            changed = sync_versions(args.version, project_root, dry_run=args.dry_run)
            action = "Would update" if args.dry_run else "Updated"
            if changed:
                for path in changed:
                    print(f"{action}: {path}")
            else:
                print(f"Version metadata is already {args.version}; no files changed.")
            return 0

        version = check_versions(project_root, expected=args.expected)
        if args.current:
            print(version)
        else:
            print(f"Version metadata is synchronized: {version}")
        return 0
    except VersionSyncError as exc:
        print(f"Version synchronization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
