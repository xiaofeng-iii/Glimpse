"""Build GitHub Pages updater manifests from published signed releases."""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path


OWNER = "xiaofeng-iii"
REPO = "Glimpse"
VERSION_RE = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?P<preview>-preview\.(?P<date>\d{8})(?:\.(?P<sequence>0|[1-9]\d*))?)?$"
)


def request(url: str, token: str) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Glimpse-updater-feed",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return response.read()


def version_key(match: re.Match[str]) -> tuple[int, ...]:
    base = tuple(int(match.group(part)) for part in ("major", "minor", "patch"))
    if not match.group("preview"):
        return (*base, 1, 0, 0)
    return (*base, 0, int(match.group("date")), int(match.group("sequence") or 0))


def signed_releases(token: str) -> list[tuple[tuple[int, ...], bool, dict]]:
    releases = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases?per_page=100&page={page}"
        batch = json.loads(request(url, token))
        if not isinstance(batch, list):
            raise ValueError("GitHub releases response was not a list")
        for release in batch:
            match = VERSION_RE.fullmatch(release["tag_name"])
            if release["draft"] or not match or release["prerelease"] != bool(match.group("preview")):
                continue
            assets = release["assets"]
            installers = [asset for asset in assets if asset["name"].endswith("-setup.exe")]
            if len(installers) != 1:
                continue
            installer = installers[0]
            signatures = [asset for asset in assets if asset["name"] == installer["name"] + ".sig"]
            if len(signatures) != 1:
                continue
            signature = request(signatures[0]["browser_download_url"], "").decode("utf-8").strip()
            if not signature:
                raise ValueError(f"Empty update signature: {release['tag_name']}")
            manifest = {
                "version": release["tag_name"][1:],
                "notes": release["body"] or "",
                "platforms": {
                    "windows-x86_64": {
                        "url": installer["browser_download_url"],
                        "signature": signature,
                    }
                },
            }
            releases.append((version_key(match), bool(match.group("preview")), manifest))
        if len(batch) < 100:
            break
        page += 1
    return releases


def write_feeds(output: Path, releases: list[tuple[tuple[int, ...], bool, dict]]) -> None:
    index_path = output / "updates" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index = {
        "schemaVersion": 1,
        "releases": [
            {"version": manifest["version"], "preview": preview,
             "notes": manifest.get("notes", ""), "sortKey": list(key)}
            for key, preview, manifest in sorted(releases, key=lambda release: release[0], reverse=True)
        ],
    }
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stable = [release for release in releases if not release[1]]
    preview = releases
    for channel, eligible in (("stable", stable), ("preview", preview)):
        if not eligible:
            continue
        manifest = max(eligible, key=lambda release: release[0])[2]
        path = output / "updates" / f"{channel}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{channel}: {manifest['version']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: build_update_feed.py OUTPUT_DIRECTORY")
    write_feeds(Path(sys.argv[1]), signed_releases(os.environ.get("GITHUB_TOKEN", "")))
