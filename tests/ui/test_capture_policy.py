import importlib.util
from pathlib import Path


MODULE = Path(__file__).parents[2] / "packaging" / "capture_ui.py"
spec = importlib.util.spec_from_file_location("nolane_capture_policy", MODULE)
capture_ui = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(capture_ui)


def test_windows_capture_does_not_override_native_platform():
    env = {"QT_QPA_PLATFORM": "windows"}
    capture_ui.configure_capture_environment(env, "Windows")
    assert env["QT_QPA_PLATFORM"] == "windows"
