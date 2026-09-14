from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Protocol, Sequence

from .compositor import render_scene_snapshot
from .exporter import ExportClip, MediaExporter
from .scene_plan import ScenePlanStore, SceneRenderPlan, build_scene_render_plan


SnapshotRenderer = Callable[[SceneRenderPlan, str | Path], Path]


class SceneMediaExporter(Protocol):
    def export(
        self,
        clips: Sequence[ExportClip],
        output: str | Path,
        **kwargs: object,
    ) -> Path: ...


class ProjectSceneExporter:
    """Export persisted scenes instead of the loose imported-media list.

    Scene snapshots live for the entire synchronous media-export call, so a
    background worker can safely let FFmpeg consume them before the temporary
    workspace is removed. Composition errors (notably video-layer routing)
    propagate unchanged; parity code never falls back to silently dropping a
    canvas layer.
    """

    def __init__(
        self,
        store: ScenePlanStore,
        *,
        media_exporter: SceneMediaExporter | None = None,
        snapshot_renderer: SnapshotRenderer = render_scene_snapshot,
    ) -> None:
        self.store = store
        self.media_exporter = media_exporter or MediaExporter()
        self.snapshot_renderer = snapshot_renderer

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
