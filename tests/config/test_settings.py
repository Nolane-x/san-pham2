from nolane_studio.config import ProviderSettings, SettingsStore


def test_settings_round_trip_without_secret(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    expected = ProviderSettings(
        analysis_base_url="https://a.example/v1",
        analysis_model="analysis-model",
        tts_base_url="https://tts.example/v1",
        tts_model="voice-model",
    )
    store.save(expected)
    assert store.load() == expected
    text = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "api_key" not in text


def test_missing_settings_returns_safe_defaults(tmp_path):
    store = SettingsStore(tmp_path / "missing.json")
    assert store.load() == ProviderSettings()
