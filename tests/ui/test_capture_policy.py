from pathlib import Path


def test_windows_capture_does_not_force_offscreen_platform():
    source = Path("packaging/capture_ui.py").read_text(encoding="utf-8")
    assert 'if os.name != "nt"' in source
    assert 'os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")' in source
