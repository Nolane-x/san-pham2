import importlib.util
from pathlib import Path


MODULE = Path(__file__).parents[2] / "packaging" / "capture_ui.py"
spec = importlib.util.spec_from_file_location("nolane_capture_ui", MODULE)
capture_ui = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(capture_ui)


def test_windows_capture_preserves_native_qt_platform():
    env = {}
    capture_ui.configure_capture_environment(env, "Windows")
    assert "QT_QPA_PLATFORM" not in env


def test_non_windows_capture_defaults_to_offscreen():
    env = {}
    capture_ui.configure_capture_environment(env, "Linux")
    assert env["QT_QPA_PLATFORM"] == "offscreen"
