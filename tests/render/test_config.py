from nolane_studio.render.config import normalize_render_config


def test_normalize_render_config_uses_recovered_defaults():
    cfg = normalize_render_config({})
    assert cfg["style"] == "whiteboard"
    assert cfg["visual_mode"] == "drawing"
    assert cfg["brush_mode"] == "lr"
    assert cfg["hand_style"] == "hand-1.png"
    assert cfg["outro_direction"] == "left"
    assert cfg["outro_duration"] == 0.3


def test_normalize_render_config_clamps_recovered_numeric_ranges_and_preserves_unknowns():
    cfg = normalize_render_config({
        "reveal_duration": -5,
        "hold_duration": 99999,
        "outro_duration": 99,
        "custom_future_field": {"x": 1},
    })
    assert cfg["reveal_duration"] == 0.0
    assert cfg["hold_duration"] == 3600.0
    assert cfg["outro_duration"] == 5.0
    assert cfg["extras"]["custom_future_field"] == {"x": 1}


def test_normalize_render_config_does_not_enable_expensive_features_by_default():
    cfg = normalize_render_config({})
    assert cfg["remove_background_enabled"] is False
    assert cfg["custom_camera_enabled"] is False
    assert cfg["auto_object_fx_enabled"] is False
