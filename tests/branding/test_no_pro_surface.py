from pathlib import Path


def test_source_tree_has_no_pro_paywall_or_license_gate_terms():
    root = Path(__file__).resolve().parents[2] / "src" / "nolane_studio"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    lowered = text.lower()
    for forbidden in (
        "require_pro",
        "upgrade to pro",
        "pro badge",
        "license_core",
        "require_login",
    ):
        assert forbidden not in lowered
