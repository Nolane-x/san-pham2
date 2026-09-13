import pytest
from nolane_studio.domain.models import ProjectSpec, RenderConfig, Scene, TransitionSpec, VoiceRequest


def test_project_defaults_match_recovered_reference_canvas():
    project = ProjectSpec(project_id="p1", title="Demo")
    assert (project.output_w, project.output_h, project.fps) == (1280, 720, 24)


def test_render_config_rejects_negative_durations():
    with pytest.raises(ValueError, match="reveal_duration"):
        RenderConfig(reveal_duration=-0.1)


def test_scene_requires_non_blank_text():
    with pytest.raises(ValueError, match="text"):
        Scene(index=0, text="   ")


def test_transition_duration_uses_recovered_01_to_10_second_bounds():
    assert TransitionSpec("a", "b", "fade", 0.1).duration == 0.1
    assert TransitionSpec("a", "b", "fade", 10.0).duration == 10.0
    with pytest.raises(ValueError, match="0.1..10"):
        TransitionSpec("a", "b", "fade", 0.09)
    with pytest.raises(ValueError, match="0.1..10"):
        TransitionSpec("a", "b", "fade", 10.01)


def test_voice_request_normalizes_language_and_keeps_optional_clone_fields():
    req = VoiceRequest(
        text="Xin chào",
        language=" vi-VN ",
        voice="sample-1",
        reference_audio="voice.wav",
        reference_text="Xin chào",
    )
    assert req.language == "vi-VN"
    assert req.reference_audio == "voice.wav"
