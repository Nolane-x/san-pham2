from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .config import InvalidRenderConfig, InvalidSceneDuration, normalize_render_config
from .effects import (
    InvalidObjectTiming,
    ObjectTimingEntry,
    RenderProfile,
    build_render_timing_plan,
    estimate_object_timeline_seconds,
    render_profile_from_config,
)


class ScenePlanStore(Protocol):
    def list_scenes(self, project_id: str) -> list[dict[str, Any]]: ...

    def get_scene_render_settings(self, scene_id: str) -> dict[str, Any]: ...

    def list_visual_objects(self, scene_id: str) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class SceneRenderPlan:
    scene_id: str
    position: int
    text: str
    objects: tuple[Mapping[str, Any], ...]
    profile: RenderProfile
    object_timing: tuple[ObjectTimingEntry, ...]
    total_duration: float
    media_sources: tuple[str, ...]
    render_config: Mapping[str, Any] = field(default_factory=dict)


def _outro_seconds(settings: Mapping[str, Any]) -> float:
    if not bool(settings.get("outro_enabled", False)):
        return 0.0
    try:
        return max(0.0, float(settings.get("outro_duration", 0.0)))
    except (TypeError, ValueError):
        return 0.0


def build_scene_render_plan(store: ScenePlanStore, project_id: str) -> list[SceneRenderPlan]:
    """Build the authoritative, lossless render plan for a persisted project.

    This stage deliberately does not flatten the canvas to a single media
    layer. Every visible object remains in z-order so later whiteboard,
    drawing, text, shape and media compositors can reproduce the editor state
    without silently dropping layers. The normalized render configuration is
    retained on the plan so specialized renderers can consume recovered
    behavior settings without re-reading storage or depending on Qt.
    """
    plans: list[SceneRenderPlan] = []
    for scene in store.list_scenes(project_id):
        scene_id = str(scene["id"])
        try:
            settings = store.get_scene_render_settings(scene_id)
            render_config = normalize_render_config(settings)
            profile = render_profile_from_config(render_config)
        except InvalidRenderConfig as exc:
            raise InvalidRenderConfig(f"scene {scene_id} {exc}") from exc
        except InvalidSceneDuration as exc:
            raise InvalidSceneDuration(f"scene {scene_id} {exc}") from exc
        objects = tuple(
            dict(obj)
            for obj in store.list_visual_objects(scene_id)
            if bool(obj.get("visible", True))
        )
        try:
            timing = tuple(build_render_timing_plan(objects, render_config))
        except InvalidObjectTiming as exc:
            raise InvalidObjectTiming(f"scene {scene_id} {exc}") from exc
        outro = _outro_seconds(render_config)

        try:
            if timing:
                total = estimate_object_timeline_seconds(
                    timing,
                    hold_duration=profile.hold_duration,
                    outro_duration=outro,
                )
            else:
                # A scene with no canvas objects still has a real scene duration;
                # preserve reveal+hold instead of collapsing it to hold only.
                total = profile.total_duration + outro
        except InvalidSceneDuration as exc:
            raise InvalidSceneDuration(f"scene {scene_id} {exc}") from exc

        media_sources = tuple(
            str(obj.get("source", ""))
            for obj in objects
            if str(obj.get("kind", "")).lower() in {"image", "video"}
            and str(obj.get("source", "")).strip()
        )
        plans.append(
            SceneRenderPlan(
                scene_id=scene_id,
                position=int(scene.get("position", len(plans))),
                text=str(scene.get("text", "")),
                objects=objects,
                profile=profile,
                object_timing=timing,
                total_duration=float(total),
                media_sources=media_sources,
                render_config=render_config,
            )
        )
    return plans
