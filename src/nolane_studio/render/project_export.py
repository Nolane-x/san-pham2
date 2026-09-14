from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from .compositor import render_scene_snapshot
from .exporter import ExportClip, MediaExporter
from .scene_plan import ScenePlanStore, SceneRenderPlan, build_scene_render_plan
from .video_compositor import SceneVideoCompositor
from .whiteboard_compositor import UnsupportedWhiteboardMotion, WhiteboardSceneCompositor


SnapshotRenderer = Callable[[SceneRenderPlan, str | Path], Path]
VideoRenderer = Callable[..., Path]
WhiteboardRenderer = Callable[..., Path]


class UnsupportedProjectTimeline(ValueError):
    """Raised when persisted editor timeline state cannot be exported faithfully."""


class ProjectExportStore(ScenePlanStore, Protocol):
    def load_timeline(self, project_id: str) -> dict[str, Any]: ...


class SceneMediaExporter(Protocol):
    def export(
        self,
        clips: Sequence[ExportClip],
        output: str | Path,
        **kwargs: object,
    ) -> Path: ...


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

    for field, empty in (
        ("clips", {}),
        ("videoClips", []),
        ("audioClips", []),
    ):
        value = raw.get(field, empty)
        if value:
            raise UnsupportedProjectTimeline(
                f"{field} timeline payload is not yet recovered strongly enough for faithful export"
            )

    media_order = raw.get("mediaOrder", [])
    if not media_order:
        return ordered
    if not isinstance(media_order, list):
        raise UnsupportedProjectTimeline("mediaOrder must be a list")

    normalized_order = [str(item).strip() for item in media_order]
    clip_ids = [clip.clip_id for clip in ordered]
    if (
        any(not item for item in normalized_order)
        or len(normalized_order) != len(clip_ids)
        or len(set(normalized_order)) != len(normalized_order)
        or set(normalized_order) != set(clip_ids)
    ):
        raise UnsupportedProjectTimeline(
            "mediaOrder must be an exact permutation of rendered scene clip ids"
        )

    clips_by_id = {clip.clip_id: clip for clip in ordered}
    return [clips_by_id[clip_id] for clip_id in normalized_order]


class ProjectSceneExporter:
    """Export persisted scene/canvas state instead of loose imported media.

    Routing is intentionally lossless and explicit: supported source-video
    scenes use the video compositor; ordinary whiteboard scenes use the
    recovered object-timed compositor; mixed whiteboard/source-video scenes
    with additional visible layers fail closed until their native timing and
    composition behavior is recovered; static/color-reveal scenes use a
    lossless snapshot plus the existing image profile. Temporary scene media
    remains alive for the whole synchronous MediaExporter call. Persisted
    timeline state is consumed only where recovered semantics are unambiguous;
    unsupported track payloads fail closed instead of being silently dropped.
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

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="nolane-studio-scenes-") as temp_raw:
            temp = Path(temp_raw)
            clips: list[ExportClip] = []
            for index, plan in enumerate(plans):
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
                    )
                )

            clips = apply_persisted_timeline_state(
                clips,
                self.store.load_timeline(project_id),
            )
            return Path(
                self.media_exporter.export(
                    clips,
                    output_path,
                    width=width,
                    height=height,
                    fps=fps,
                )
            )
