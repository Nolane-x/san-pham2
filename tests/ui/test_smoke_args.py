from nolane_studio.ui import main_window


def test_runtime_args_extract_smoke_flag():
    qt_args, smoke = main_window._runtime_args(["NolaneStudio.exe", "--smoke-test"])
    assert qt_args == ["NolaneStudio.exe"]
    assert smoke is True


def test_runtime_args_keep_normal_args():
    qt_args, smoke = main_window._runtime_args(["NolaneStudio.exe", "--style", "Fusion"])
    assert qt_args == ["NolaneStudio.exe", "--style", "Fusion"]
    assert smoke is False
