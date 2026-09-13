from nolane_studio.ai.prompts import build_image_prompt
from nolane_studio.domain import Scene


def test_whiteboard_prompt_hardens_background_and_readable_text_policy():
    prompt = build_image_prompt(Scene(0, "Lợi nhuận tăng 25% trong quý này"), "whiteboard")
    lower = prompt.lower()
    assert "pure white background" in lower
    assert "simple 2d" in lower
    assert "do not render long text" in lower
    assert "25%" not in prompt


def test_non_whiteboard_prompt_preserves_scene_semantics_and_extra_direction():
    scene = Scene(0, "A farmer watches rain clouds over a rice field")
    prompt = build_image_prompt(scene, "cinematic", "soft morning light")
    assert "farmer" in prompt.lower()
    assert "cinematic" in prompt.lower()
    assert "soft morning light" in prompt.lower()
