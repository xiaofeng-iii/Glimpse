import json
import re

from scripts import build_update_feed
from scripts.build_update_feed import VERSION_RE, version_key, write_feeds


def candidate(version, preview):
    match = VERSION_RE.fullmatch("v" + version)
    assert match
    return version_key(match), preview, {
        "version": version,
        "platforms": {"windows-x86_64": {"url": "https://example.com/setup.exe", "signature": "signed"}},
    }


def test_preview_channel_accepts_newer_stable_release(tmp_path):
    releases = [
        candidate("0.3.3-preview.20261003", True),
        candidate("0.3.3", False),
        candidate("0.3.2", False),
    ]
    write_feeds(tmp_path, releases)

    stable = json.loads((tmp_path / "updates/stable.json").read_text(encoding="utf-8"))
    preview = json.loads((tmp_path / "updates/preview.json").read_text(encoding="utf-8"))
    assert stable["version"] == preview["version"] == "0.3.3"


def test_preview_channel_can_lead_stable_and_orders_numeric_sequence(tmp_path):
    releases = [
        candidate("0.3.3", False),
        candidate("0.3.4-preview.20261003.2", True),
        candidate("0.3.4-preview.20261003.10", True),
    ]
    write_feeds(tmp_path, releases)

    stable = json.loads((tmp_path / "updates/stable.json").read_text(encoding="utf-8"))
    preview = json.loads((tmp_path / "updates/preview.json").read_text(encoding="utf-8"))
    assert stable["version"] == "0.3.3"
    assert preview["version"] == "0.3.4-preview.20261003.10"


def test_signed_releases_skips_unsigned_and_uses_signature_contents(monkeypatch):
    requests = []
    release = {
        "tag_name": "v0.3.4-preview.20261003",
        "draft": False,
        "prerelease": True,
        "body": "更新说明",
        "assets": [
            {"name": "Glimpse_0.3.4_x64-setup.exe", "browser_download_url": "https://example.com/setup.exe"},
            {"name": "Glimpse_0.3.4_x64-setup.exe.sig", "browser_download_url": "https://example.com/setup.exe.sig"},
        ],
    }

    def fake_request(url, token):
        requests.append((url, token))
        if url.endswith(".sig"):
            return b"signed contents\n"
        return json.dumps([release]).encode("utf-8")

    monkeypatch.setattr(build_update_feed, "request", fake_request)
    result = build_update_feed.signed_releases("api-token")
    assert len(result) == 1
    assert result[0][2]["platforms"]["windows-x86_64"]["signature"] == "signed contents"
    assert requests[1] == ("https://example.com/setup.exe.sig", "")

    release["assets"] = release["assets"][:1]
    assert build_update_feed.signed_releases("api-token") == []


def test_feed_skips_versions_outside_published_channels():
    assert VERSION_RE.fullmatch("v0.3.4-dev.20261003") is None
    assert VERSION_RE.fullmatch("v0.3.4-preview.20261003.01") is None
    assert re.fullmatch(r"\d{8}", VERSION_RE.fullmatch("v0.3.4-preview.20261003").group("date"))
