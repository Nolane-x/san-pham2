from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ("dra" + "wai", "img" + "draw")


def _tracked_text_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    paths: list[Path] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8")
        if not path.is_file():
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        paths.append(path)
    return paths


def test_repository_contains_no_legacy_product_branding():
    violations: list[str] = []
    for path in _tracked_text_files():
        text = path.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN:
            if term in text:
                violations.append(f"{path.relative_to(ROOT)} contains {term}")
    assert violations == []


def test_python_distribution_and_cli_use_new_brand():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "nolane-studio"
    assert "nolane-studio" in data["project"]["scripts"]
