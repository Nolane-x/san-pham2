from __future__ import annotations

import math
from typing import Any, Mapping

_KNOWN = {
    "style", "visual_mode", "reveal_duration", "hold_duration", "brush_mode",
    "custom_draw_points", "large_object_push_enabled", "large_object_push_direction",
    "large_object_push_mode", "custom_object_push_config", "custom_object_effect_config",
    "custom_object_sound_config", "custom_camera_enabled", "custom_camera_config",
    "object_timing_mode", "custom_object_timing_config", "outro_enabled", "outro_direction",
    "outro_duration", "hand_style", "remove_background_enabled", "auto_object_fx_enabled",
    "auto_object_fx_config", "image_motion_config", "batch_voice_segments",
}


class InvalidSceneDuration(ValueError):
    """Raised when persisted scene timing cannot form a finite duration."""


class InvalidRenderConfig(ValueError):
    """Raised when persisted render configuration has an invalid shape."""


def _config_list(value: Any, *, field: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise InvalidRenderConfig(f"{field} must be a list")
    return list(value)


def _mapping_list(value: Any, *, field: str) -> list[Mapping[str, Any]]:
    items = _config_list(value, field=field)
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise InvalidRenderConfig(f"{field} entry {index} must be a mapping")
    return items


def _config_mapping(value: Any, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise InvalidRenderConfig(f"{field} must be a mapping")
    return dict(value)


def _float(
    value: Any,
    default: float,
    low: float,
    high: float,
    *,
    field: str,
    strict: bool = False,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        if strict:
            raise InvalidSceneDuration(f"{field} must be finite")
        number = float(default)
    if not math.isfinite(number):
        raise InvalidSceneDuration(f"{field} must be finite")
    return max(low, min(high, number))


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def normalize_render_config(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        incoming: dict[str, Any] = {}
    elif not isinstance(raw, Mapping):
        raise InvalidRenderConfig("render_config must be a mapping")
    else:
        incoming = dict(raw)
    visual_mode = str(incoming.get("visual_mode", "drawing") or "drawing").strip().lower()
    if visual_mode not in {"drawing", "camera_motion"}:
        raise InvalidRenderConfig("visual_mode must be drawing or camera_motion")
    style = str(incoming.get("style", "whiteboard") or "whiteboard").strip().lower()
    if style not in {"whiteboard", "color_reveal"}:
        raise InvalidRenderConfig("style must be whiteboard or color_reveal")

    config = {
        "style": style,
        "visual_mode": visual_mode,
        "reveal_duration": _float(
            incoming.get("reveal_duration", 8.0),
            8.0,
            0.0,
            3600.0,
            field="reveal_duration",
            strict="reveal_duration" in incoming,
        ),
        "hold_duration": _float(
            incoming.get("hold_duration", 1.0),
            1.0,
            0.0,
            3600.0,
            field="hold_duration",
            strict="hold_duration" in incoming,
        ),
        "brush_mode": str(incoming.get("brush_mode", "lr") or "lr"),
        "custom_draw_points": _config_list(
            incoming.get("custom_draw_points"),
            field="custom_draw_points",
        ),
        "large_object_push_enabled": _truthy(incoming.get("large_object_push_enabled", False)),
        "large_object_push_direction": str(incoming.get("large_object_push_direction", "from_left") or "from_left"),
        "large_object_push_mode": str(incoming.get("large_object_push_mode", "automatic") or "automatic"),
        "custom_object_push_config": _config_list(
            incoming.get("custom_object_push_config"),
            field="custom_object_push_config",
        ),
        "custom_object_effect_config": _config_list(
            incoming.get("custom_object_effect_config"),
            field="custom_object_effect_config",
        ),
        "custom_object_sound_config": _config_list(
            incoming.get("custom_object_sound_config"),
            field="custom_object_sound_config",
        ),
        "custom_camera_enabled": _truthy(incoming.get("custom_camera_enabled", False)),
        "custom_camera_config": _mapping_list(
            incoming.get("custom_camera_config"),
            field="custom_camera_config",
        ),
        "object_timing_mode": str(incoming.get("object_timing_mode", "fixed") or "fixed"),
        "custom_object_timing_config": _config_list(
            incoming.get("custom_object_timing_config"),
            field="custom_object_timing_config",
        ),
        "outro_enabled": _truthy(incoming.get("outro_enabled", False)),
        "outro_direction": str(incoming.get("outro_direction", "left") or "left"),
        "outro_duration": _float(
            incoming.get("outro_duration", 0.3),
            0.3,
            0.0,
            5.0,
            field="outro_duration",
            strict="outro_duration" in incoming,
        ),
        "hand_style": str(incoming.get("hand_style", "hand-1.png") or "hand-1.png"),
        "remove_background_enabled": _truthy(incoming.get("remove_background_enabled", False)),
        "auto_object_fx_enabled": _truthy(incoming.get("auto_object_fx_enabled", False)),
        "auto_object_fx_config": _config_mapping(
            incoming.get("auto_object_fx_config"),
            field="auto_object_fx_config",
        ),
        "image_motion_config": _config_mapping(
            incoming.get("image_motion_config"),
            field="image_motion_config",
        ),
        "batch_voice_segments": _config_list(
            incoming.get("batch_voice_segments"),
            field="batch_voice_segments",
        ),
        "extras": {k: v for k, v in incoming.items() if k not in _KNOWN},
    }
    return config
