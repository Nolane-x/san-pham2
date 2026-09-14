import builtins

import pytest
import nolane_studio.ui


def test_ui_package_imports_without_pyside6():
    assert callable(nolane_studio.ui.run)


def test_run_explains_optional_ui_dependency_when_missing(monkeypatch):
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("simulated missing Qt")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(RuntimeError, match="PySide6"):
        nolane_studio.ui.run([])
