from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.render.exporter import ExportClip, build_video_segment_command


def test_scene_edit_applies_trim_speed_and_effective_duration_to_video_clip():
    from nolane_studio.render.project_export import apply_persisted_scene_edits

    clip = ExportClip(
        "scene.mp4",
        "video",
        duration=10.0,
        trim_start=0.0,
        trim_end=10.0,
        speed=1.0,
        clip_id="scene-a",
        narration_audio="voice.wav",
    )
    edited = apply_persisted_scene_edits(
        [clip],
        {
            "sceneEdits": [
                {
                    "scene_id": "scene-a",
                    "trim_start": 2.0,
                    "trim_end": 8.0,
                    "speed": 2.0,
                }
            ]
        },
    )

    assert len(edited) == 1
    result = edited[0]
    assert result.trim_start == pytest.approx(2.0)
    assert result.trim_end == pytest.approx(8.0)
    assert result.speed == pytest.approx(2.0)
    assert result.duration == pytest.approx(3.0)
    assert result.narration_audio == "voice.wav"


def test_scene_edit_shortens_static_scene_and_keeps_narration_window():
    from nolane_studio.render.project_export import apply_persisted_scene_edits

    clip = ExportClip(
        "scene.png",
        "image",
        duration=10.0,
        clip_id="scene-a",
        narration_audio="voice.wav",
    )
    edited = apply_persisted_scene_edits(
        [clip],
        {
            "sceneEdits": [
                {
                    "scene_id": "scene-a",
                    "trim_start": 2.0,
                    "trim_end": 8.0,
                    "speed": 2.0,
                }
            ]
        },
    )[0]

    assert edited.kind == "image"
    assert edited.duration == pytest.approx(3.0)
    assert edited.trim_start == pytest.approx(2.0)
    assert edited.trim_end == pytest.approx(8.0)
    assert edited.speed == pytest.approx(2.0)


@pytest.mark.parametrize(
    "entry, message",
    [
        ({"scene_id": "unknown", "trim_start": 0.0, "trim_end": 1.0, "speed": 1.0}, "unknown"),
        ({"scene_id": "scene-a", "trim_start": -1.0, "trim_end": 1.0, "speed": 1.0}, "trim_start"),
        ({"scene_id": "scene-a", "trim_start": 3.0, "trim_end": 2.0, "speed": 1.0}, "trim_end"),
        ({"scene_id": "scene-a", "trim_start": 0.0, "trim_end": 11.0, "speed": 1.0}, "duration"),
        ({"scene_id": "scene-a", "trim_start": 0.0, "trim_end": 1.0, "speed": 0.0}, "speed"),
    ],
)
def test_scene_edit_fails_closed_on_invalid_or_unknown_state(entry, message):
    from nolane_studio.render.project_export import (
        UnsupportedProjectTimeline,
        apply_persisted_scene_edits,
    )

    clip = ExportClip("scene.mp4", "video", duration=10.0, clip_id="scene-a")
    with pytest.raises(UnsupportedProjectTimeline, match=message):
        apply_persisted_scene_edits([clip], {"sceneEdits": [entry]})


def test_narrated_video_trim_and_speed_apply_to_narration_chain():
    command = build_video_segment_command(
        "ffmpeg",
        "scene.mp4",
        "out.mp4",
        has_audio=True,
        trim_start=2.0,
        trim_end=8.0,
        speed=2.0,
        duration=3.0,
        narration_audio="voice.wav",
    )
    joined = " ".join(command)

    assert "-ss 2.000000" in joined
    assert "-t 6.000000 -i scene.mp4" in joined
    assert "[1:a]atrim=start=2.000000:end=8.000000" in joined
    assert "atempo=2.000000" in joined
    assert "atrim=duration=3.000000[narration]" in joined
