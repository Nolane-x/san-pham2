from __future__ import annotations

import math
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from nolane_studio.domain import TransitionSpec

from .compositor import CompositionError, render_scene_snapshot, validate_supported_static_visual_state
from .effects import normalize_ffmpeg_render_geometry
from .exporter import ExportClip, MediaExporter
from .scene_plan import ScenePlanStore, SceneRenderPlan, build_scene_render_plan
from .timeline import build_transition_gaps
from .video_compositor import SceneVideoCompositor, validate_supported_video_composition
from .whiteboard_compositor import (
    UnsupportedWhiteboardMotion,
    WhiteboardSceneCompositor,
    validate_supported_whiteboard_motion,
)


SnapshotRenderer = Callable[[SceneRenderPlan, str | Path], Path]
VideoRenderer = Callable[..., Path]
WhiteboardRenderer = Callable[..., Path]


class UnsupportedProjectTimeline(ValueError):
    """Raised when persisted editor timeline state cannot be exported faithfully."""


class UnsupportedSceneRenderState(ValueError):
    """Raised when persisted scene behavior has no faithful renderer yet."""


class MissingSceneMedia(FileNotFoundError):
    """Raised when a visible persisted image/video source is unavailable."""


class MissingSceneNarration(FileNotFoundError):
    """Raised when persisted per-scene narration cannot be read for export."""


_UNSUPPORTED_RENDER_STATE_FIELDS = (
    "remove_background_enabled",
    "auto_object_fx_enabled",
    "custom_object_effect_config",
    "custom_object_sound_config",
    "custom_draw_points",
    "batch_voice_segments",
)


def validate_supported_scene_render_state(plan: SceneRenderPlan) -> None:
    """Reject persisted behavior that the current renderers would silently drop."""
    for field in _UNSUPPORTED_RENDER_STATE_FIELDS:
        if plan.render_config.get(field):
            raise UnsupportedSceneRenderState(
                f"scene {plan.scene_id} uses unsupported persisted render state: {field}"
            )

    hand_style = str(plan.render_config.get("hand_style", "hand-1.png") or "hand-1.png").strip()
    if plan.profile.style == "whiteboard" and hand_style != "hand-1.png":
        raise UnsupportedSceneRenderState(
            f"scene {plan.scene_id} uses unsupported persisted render state: hand_style"
        )

    has_video = any(
        str(obj.get("kind", "")).strip().lower() == "video"
        and bool(obj.get("visible", True))
        for obj in plan.objects
    )
    if bool(plan.render_config.get("outro_enabled", False)) and (
        plan.profile.style != "whiteboard" or has_video
    ):
        raise UnsupportedSceneRenderState(
            f"scene {plan.scene_id} uses unsupported persisted render state: outro_enabled"
        )

    if has_video and plan.profile.camera != "static":
        raise UnsupportedSceneRenderState(
            f"scene {plan.scene_id} uses unsupported persisted render state: visual_mode"
        )

    if plan.render_config.get("custom_object_push_config"):
        raise UnsupportedSceneRenderState(
            f"scene {plan.scene_id} uses unsupported persisted render state: custom_object_push_config"
        )

    push_mode = str(
        plan.render_config.get("large_object_push_mode", "automatic") or "automatic"
    ).strip().lower().replace("-", "_")
    if push_mode != "automatic":
        raise UnsupportedSceneRenderState(
            f"scene {plan.scene_id} uses unsupported persisted render state: large_object_push_mode"
        )

    push_enabled = bool(plan.render_config.get("large_object_push_enabled", False))
    has_positive_push = any(entry.push > 0 for entry in plan.object_timing)
    if has_video and has_positive_push:
        raise UnsupportedSceneRenderState(
            f"scene {plan.scene_id} uses unsupported persisted render state: large_object_push_enabled"
        )
    if push_enabled != has_positive_push:
        raise UnsupportedSceneRenderState(
            f"scene {plan.scene_id} uses unsupported persisted render state: large_object_push_enabled"
        )


def validate_project_scene_ordering(plans: Sequence[SceneRenderPlan]) -> None:
    """Reject ambiguous persisted scene ordering before any renderer starts."""
    seen: set[int] = set()
    for plan in plans:
        scene_id = str(plan.scene_id)
        if not scene_id.strip():
            raise UnsupportedProjectTimeline("scene id must not be blank")
        if scene_id != scene_id.strip():
            raise UnsupportedProjectTimeline(
                "scene id must not contain surrounding whitespace"
            )
        if plan.position in seen:
            raise UnsupportedProjectTimeline(
                f"scene position {plan.position} must be unique"
            )
        seen.add(plan.position)


def validate_project_scene_media(plans: Sequence[SceneRenderPlan]) -> None:
    """Preflight every visible image/video source before any scene render starts."""
    for plan in plans:
        for obj in plan.objects:
            kind = str(obj.get("kind", "")).strip().lower()
            if kind not in {"image", "video"}:
                continue
            object_id = str(obj.get("id", "")).strip()
            source = str(obj.get("source") or "").strip()
            if not source or not Path(source).is_file():
                rendered_source = source or "<blank>"
                raise MissingSceneMedia(
                    f"scene {plan.scene_id} object {object_id} missing {kind} source: {rendered_source}"
                )
            if kind == "image":
                from PySide6.QtGui import QImage

                if QImage(source).isNull():
                    raise CompositionError(
                        f"scene {plan.scene_id} object {object_id} "
                        f"unable to decode scene image: {source}"
                    )


def persisted_scene_narration(plan: SceneRenderPlan) -> str | None:
    """Return the persisted scene narration path, failing closed on stale state."""
    metadata = plan.metadata
    raw_path = metadata.get("voice_path")
    media_id = str(metadata.get("voice_media_id") or "").strip()
    if raw_path is None or not str(raw_path).strip():
        if media_id:
            raise MissingSceneNarration(
                f"scene {plan.scene_id} persisted narration {media_id} has no voice_path"
            )
        return None

    path = str(raw_path).strip()
    if not Path(path).is_file():
        raise MissingSceneNarration(
            f"scene {plan.scene_id} missing persisted narration source: {path}"
        )
    return path


def validate_project_scene_narration(plans: Sequence[SceneRenderPlan]) -> None:
    """Preflight every persisted narration path before any scene renderer starts."""
    for plan in plans:
        persisted_scene_narration(plan)


def validate_project_scene_render_state(plans: Sequence[SceneRenderPlan]) -> None:
    """Preflight unsupported persisted render state before any scene render starts."""
    for plan in plans:
        validate_supported_scene_render_state(plan)


def validate_project_scene_composition(plans: Sequence[SceneRenderPlan]) -> None:
    """Preflight scene compositions and recovered motion before any renderer starts."""
    for plan in plans:
        validate_supported_static_visual_state(plan)
        has_video = any(
            str(obj.get("kind", "")).strip().lower() == "video"
            and bool(obj.get("visible", True))
            for obj in plan.objects
        )
        has_non_video = any(
            str(obj.get("kind", "")).strip().lower() != "video"
            and bool(obj.get("visible", True))
            for obj in plan.objects
        )
        if has_video and has_non_video and plan.profile.style == "whiteboard":
            raise UnsupportedWhiteboardMotion(
                "whiteboard source-video composition is not yet supported"
            )
        if has_video:
            validate_supported_video_composition(plan)
        validate_supported_whiteboard_motion(plan)


def validate_persisted_timeline_state(
    clip_ids: Sequence[str],
    state: Mapping[str, Any] | None,
) -> None:
    """Reject persisted timeline semantics that cannot be exported faithfully."""
    raw = dict(state or {})

    clips = raw.get("clips", {})
    if not isinstance(clips, Mapping):
        raise UnsupportedProjectTimeline("clips must be a mapping")
    if clips:
        raise UnsupportedProjectTimeline(
            "clips timeline payload is not yet recovered strongly enough for faithful export"
        )

    for field in ("videoClips", "audioClips"):
        value = raw.get(field, [])
        if not isinstance(value, list):
            raise UnsupportedProjectTimeline(f"{field} must be a list")
        if value:
            raise UnsupportedProjectTimeline(
                f"{field} timeline payload is not yet recovered strongly enough for faithful export"
            )

    media_order = raw.get("mediaOrder", [])
    if not isinstance(media_order, list):
        raise UnsupportedProjectTimeline("mediaOrder must be a list")
    if not media_order:
        return

    normalized_order = [str(item).strip() for item in media_order]
    normalized_clip_ids = [str(clip_id) for clip_id in clip_ids]
    if (
        any(not item for item in normalized_order)
        or len(normalized_order) != len(normalized_clip_ids)
        or len(set(normalized_order)) != len(normalized_order)
        or set(normalized_order) != set(normalized_clip_ids)
    ):
        raise UnsupportedProjectTimeline(
            "mediaOrder must be an exact permutation of rendered scene clip ids"
        )


_PERSISTED_TRANSITION_EFFECTS = {
    "fade",
    "wipeleft",
    "wiperight",
    "slideleft",
    "slideright",
    "smoothleft",
    "smoothright",
}


def persisted_transition_specs(
    clip_ids: Sequence[str],
    state: Mapping[str, Any] | None,
) -> list[TransitionSpec]:
    """Decode only the explicit rebuild transition field and fail closed on ambiguity."""
    raw = dict(state or {}).get("transitions", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise UnsupportedProjectTimeline("transitions must be a list")

    specs: list[TransitionSpec] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise UnsupportedProjectTimeline(
                f"transition entry {index} must be a mapping"
            )
        effect = str(item.get("effect", "")).strip().lower()
        if effect not in _PERSISTED_TRANSITION_EFFECTS:
            raise UnsupportedProjectTimeline(
                f"transition entry {index} uses unsupported effect: {effect or '<blank>'}"
            )
        try:
            spec = TransitionSpec(
                str(item.get("from_id", "")),
                str(item.get("to_id", "")),
                effect,
                item.get("duration"),
            )
        except (TypeError, ValueError) as exc:
            raise UnsupportedProjectTimeline(
                f"transition entry {index} is invalid: {exc}"
            ) from exc
        specs.append(spec)

    try:
        build_transition_gaps([str(clip_id) for clip_id in clip_ids], specs)
    except ValueError as exc:
        raise UnsupportedProjectTimeline(str(exc)) from exc
    return specs


class ProjectExportStore(ScenePlanStore, Protocol):
    def load_timeline(self, project_id: str) -> dict[str, Any]: ...


class SceneMediaExporter(Protocol):
    def export(
        self,
        clips: Sequence[ExportClip],
        output: str | Path,
        **kwargs: object,
    ) -> Path: ...


def validate_persisted_scene_edits(
    clip_durations: Mapping[str, float],
    state: Mapping[str, Any] | None,
) -> dict[str, tuple[float, float, float, float]]:
    """Decode rebuild-owned scene clip edits without interpreting legacy track payloads."""
    raw = dict(state or {}).get("sceneEdits", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise UnsupportedProjectTimeline("sceneEdits must be a list")

    durations: dict[str, float] = {}
    for raw_id, raw_duration in clip_durations.items():
        scene_id = str(raw_id).strip()
        if not scene_id:
            raise UnsupportedProjectTimeline("scene edit source id must not be blank")
        try:
            duration = float(raw_duration)
        except (TypeError, ValueError, OverflowError):
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} duration must be finite"
            ) from None
        if not math.isfinite(duration) or duration <= 0:
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} duration must be finite and > 0"
            )
        durations[scene_id] = duration

    edits: dict[str, tuple[float, float, float, float]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise UnsupportedProjectTimeline(
                f"sceneEdits entry {index} must be a mapping"
            )
        scene_id = str(item.get("scene_id", "")).strip()
        if not scene_id:
            raise UnsupportedProjectTimeline(
                f"sceneEdits entry {index} scene_id must not be blank"
            )
        if scene_id not in durations:
            raise UnsupportedProjectTimeline(
                f"sceneEdits entry {index} references unknown scene: {scene_id}"
            )
        if scene_id in edits:
            raise UnsupportedProjectTimeline(
                f"sceneEdits contains duplicate scene_id: {scene_id}"
            )

        try:
            trim_start = float(item.get("trim_start", 0.0))
        except (TypeError, ValueError, OverflowError):
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} trim_start must be finite"
            ) from None
        try:
            raw_end = item.get("trim_end", durations[scene_id])
            trim_end = durations[scene_id] if raw_end is None else float(raw_end)
        except (TypeError, ValueError, OverflowError):
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} trim_end must be finite"
            ) from None
        try:
            speed = float(item.get("speed", 1.0))
        except (TypeError, ValueError, OverflowError):
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} speed must be finite and > 0"
            ) from None

        if not math.isfinite(trim_start) or trim_start < 0:
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} trim_start must be finite and >= 0"
            )
        if not math.isfinite(trim_end) or trim_end <= trim_start:
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} trim_end must be finite and greater than trim_start"
            )
        source_duration = durations[scene_id]
        if trim_end > source_duration:
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} trim_end must not exceed scene duration {source_duration:.6f}"
            )
        if not math.isfinite(speed) or speed <= 0:
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} speed must be finite and > 0"
            )

        effective = (trim_end - trim_start) / speed
        if not math.isfinite(effective) or effective <= 0:
            raise UnsupportedProjectTimeline(
                f"scene {scene_id} edited duration must be finite and > 0"
            )
        edits[scene_id] = (trim_start, trim_end, speed, effective)
    return edits


def apply_persisted_scene_edits(
    clips: Sequence[ExportClip],
    state: Mapping[str, Any] | None,
) -> list[ExportClip]:
    """Apply explicit scene-level trim/speed after render and before assembly."""
    clip_list = list(clips)
    durations: dict[str, float] = {}
    for clip in clip_list:
        clip_id = str(clip.clip_id).strip()
        if not clip_id:
            raise UnsupportedProjectTimeline(
                "scene clip id must not be blank before applying sceneEdits"
            )
        if clip_id in durations:
            raise UnsupportedProjectTimeline(
                f"scene clip id must be unique before applying sceneEdits: {clip_id}"
            )
        durations[clip_id] = float(clip.duration)

    edits = validate_persisted_scene_edits(durations, state)
    if not edits:
        return clip_list

    result: list[ExportClip] = []
    for clip in clip_list:
        edit = edits.get(clip.clip_id)
        if edit is None:
            result.append(clip)
            continue
        trim_start, trim_end, speed, effective = edit
        result.append(
            replace(
                clip,
                duration=effective,
                trim_start=trim_start,
                trim_end=trim_end,
                speed=speed,
            )
        )
    return result


def apply_persisted_timeline_state(
    clips: Sequence[ExportClip],
    state: Mapping[str, Any] | None,
) -> list[ExportClip]:
    """Apply only timeline semantics recovered strongly enough for exact export.

    The recovered store proves four persisted timeline buckets exist, but it
    does not establish a trustworthy per-entry schema for ``clips``,
    ``videoClips`` or ``audioClips``. Silently ignoring any of those payloads
    would lose editor state, so this boundary fails closed until their shape is
    recovered. ``mediaOrder`` is safe only when it is an exact permutation of
    the already-rendered scene clip IDs.
    """
    ordered = list(clips)
    raw = dict(state or {})
    clip_ids = [clip.clip_id for clip in ordered]
    validate_persisted_timeline_state(clip_ids, raw)

    media_order = raw.get("mediaOrder", [])
    if not media_order:
        return ordered

    normalized_order = [str(item).strip() for item in media_order]
    clips_by_id = {clip.clip_id: clip for clip in ordered}
    return [clips_by_id[clip_id] for clip_id in normalized_order]


class ProjectSceneExporter:
    """Export persisted scene/canvas state instead of loose imported media.

    Routing is intentionally lossless and explicit: supported source-video
    scenes use the video compositor; ordinary whiteboard scenes use the
    recovered object-timed compositor; mixed whiteboard/source-video scenes
    with additional visible layers fail closed until their native timing and
    composition behavior is recovered; static/color-reveal scenes use a
    lossless snapshot plus the existing image profile. Every visible persisted
    image/video source, unsupported persisted render state, unsupported scene
    composition, unsupported whiteboard/video motion topology, and unsupported
    or ambiguous persisted timeline state is preflighted across the whole
    project before any scene renderer starts, so later invalid state cannot
    leave a partially rendered export. Temporary scene media remains alive for
    the whole synchronous MediaExporter call. Persisted timeline ordering is
    consumed only where recovered semantics are unambiguous.
    """

    def __init__(
        self,
        store: ProjectExportStore,
        *,
        media_exporter: SceneMediaExporter | None = None,
        snapshot_renderer: SnapshotRenderer = render_scene_snapshot,
        video_renderer: VideoRenderer | None = None,
        whiteboard_renderer: WhiteboardRenderer | None = None,
    ) -> None:
        self.store = store
        self.media_exporter = media_exporter or MediaExporter()
        self.snapshot_renderer = snapshot_renderer
        self.video_renderer = video_renderer or SceneVideoCompositor().render
        self.whiteboard_renderer = whiteboard_renderer or WhiteboardSceneCompositor().render

    def export(
        self,
        project_id: str,
        output: str | Path,
        *,
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
    ) -> Path:
        plans = build_scene_render_plan(self.store, project_id)
        if not plans:
            raise ValueError("project has no scenes to export")
        validate_project_scene_ordering(plans)
        validate_project_scene_media(plans)
        validate_project_scene_narration(plans)
        validate_project_scene_render_state(plans)
        validate_project_scene_composition(plans)
        timeline_state = self.store.load_timeline(project_id)
        scene_ids = [plan.scene_id for plan in plans]
        validate_persisted_timeline_state(scene_ids, timeline_state)
        validate_persisted_scene_edits(
            {plan.scene_id: plan.total_duration for plan in plans},
            timeline_state,
        )
        media_order = timeline_state.get("mediaOrder", [])
        ordered_scene_ids = (
            [str(item).strip() for item in media_order]
            if media_order
            else scene_ids
        )
        transitions = persisted_transition_specs(ordered_scene_ids, timeline_state)
        normalize_ffmpeg_render_geometry(width, height, fps)

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="nolane-studio-scenes-") as temp_raw:
            temp = Path(temp_raw)
            clips: list[ExportClip] = []
            for index, plan in enumerate(plans):
                narration_audio = persisted_scene_narration(plan)
                has_video = any(
                    str(obj.get("kind", "")).strip().lower() == "video"
                    and bool(obj.get("visible", True))
                    for obj in plan.objects
                )
                if has_video:
                    scene_video = temp / f"scene-{index:04d}-{plan.scene_id}.mp4"
                    rendered_video = Path(
                        self.video_renderer(
                            plan,
                            scene_video,
                            width=width,
                            height=height,
                            fps=fps,
                        )
                    )
                    clips.append(
                        ExportClip(
                            str(rendered_video),
                            "video",
                            duration=plan.total_duration,
                            trim_start=0.0,
                            trim_end=plan.total_duration,
                            clip_id=plan.scene_id,
                            narration_audio=narration_audio,
                        )
                    )
                    continue

                if plan.profile.style == "whiteboard" and plan.object_timing:
                    scene_whiteboard = temp / f"scene-{index:04d}-{plan.scene_id}.mp4"
                    rendered_whiteboard = Path(
                        self.whiteboard_renderer(
                            plan,
                            scene_whiteboard,
                            width=width,
                            height=height,
                            fps=fps,
                        )
                    )
                    clips.append(
                        ExportClip(
                            str(rendered_whiteboard),
                            "video",
                            duration=plan.total_duration,
                            trim_start=0.0,
                            trim_end=plan.total_duration,
                            clip_id=plan.scene_id,
                            narration_audio=narration_audio,
                        )
                    )
                    continue

                snapshot = temp / f"scene-{index:04d}-{plan.scene_id}.png"
                rendered = Path(self.snapshot_renderer(plan, snapshot))
                clips.append(
                    ExportClip(
                        str(rendered),
                        "image",
                        duration=plan.total_duration,
                        render_profile={
                            "style": plan.profile.style,
                            "camera": plan.profile.camera,
                            "reveal_duration": plan.profile.reveal_duration,
                            "hold_duration": plan.profile.hold_duration,
                        },
                        clip_id=plan.scene_id,
                        narration_audio=narration_audio,
                    )
                )

            clips = apply_persisted_scene_edits(clips, timeline_state)
            clips = apply_persisted_timeline_state(clips, timeline_state)
            export_kwargs: dict[str, object] = {
                "width": width,
                "height": height,
                "fps": fps,
            }
            if transitions:
                export_kwargs["transitions"] = transitions
            return Path(
                self.media_exporter.export(
                    clips,
                    output_path,
                    **export_kwargs,
                )
            )
