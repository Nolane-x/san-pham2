from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Protocol, Sequence

from .compositor import render_scene_snapshot
from .exporter import ExportClip, MediaExporter
from .scene_plan import ScenePlanStore, SceneRenderPlan, build_scene_render_plan
from .video_compositor import SceneVideoCompositor
from .whiteboard_compositor import WhiteboardSceneCompositor


SnapshotRenderer = Callable[[SceneRenderPlan, str | Path], Path]
VideoRenderer = Callable[..., Path]
WhiteboardRenderer = Callable[..., Path]


class SceneMediaExporter(Protocol):
    def export(
        self,
        clips: Sequence[ExportClip],
        output: str | Path,
        **kwargs: object,
    ) -> Path: ...


class ProjectSceneExporter:
    """Export persisted scene/canvas state instead of loose imported media.

    Routing is intentionally lossless and explicit: source-video scenes use the
    video compositor first; ordinary whiteboard scenes use the recovered
    object-timed compositor; static/color-reveal scenes use a lossless snapshot
    plus the existing image profile. Temporary scene media remains alive for
    the whole synchronous MediaExporter call.
    """

    def __init__(
        self,
        store: ScenePlanStore,
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

            return Path(
                self.media_exporter.export(
                    clips,
                    output_path,
                    width=width,
                    height=height,
                    fps=fps,
                )
            )
