from PySide6.QtWidgets import QApplication

from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_studio_exposes_recovered_ai_analyze_and_voice_actions(tmp_path):
    _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    page = StudioPage(store)

    assert hasattr(page, "ai_analyze_button")
    assert hasattr(page, "analyze_all_button")
    assert hasattr(page, "generate_voice_button")
    assert hasattr(page, "voice_from_content_button")
    assert page.ai_analyze_button.text() == "AI Analyze"
    assert page.analyze_all_button.text() == "Analyze All"
    assert page.generate_voice_button.text() == "Generate voice"
    assert page.voice_from_content_button.text() == "Voice From Content"
