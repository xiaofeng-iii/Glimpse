from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_nltk_is_pinned_to_pyinstaller_compatible_version():
    """NLTK 3.10.x ships an inisec import hook that breaks the packaged sidecar."""
    requirements = (
        PROJECT_ROOT / "requirements.txt"
    ).read_text(encoding="utf-8")
    pyproject = (
        PROJECT_ROOT / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert "nltk==3.9.4" in requirements
    assert '"nltk==3.9.4"' in pyproject
