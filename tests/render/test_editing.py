from __future__ import annotations

import pytest

from nolane_studio.render.editing import TimelineClip, split_clip


def test_video_clip_effective_duration_respects_trim_and_speed():
    clip = TimelineClip(
        clip_id="v1",
        path="source.mp4",
        kind="video",
        source_duration=20.0,
        trim_start=3.0,
        trim_end=15.0,
        speed=1.5,
    )
    assert clip.effective_duration == pytest.approx(8.0)


def test_split_video_clip_preserves_source_ranges_without_overlap():
    clip = TimelineClip(
        clip_id="v1",
        path="source.mp4",
        kind="video",
        source_duration=20.0,
        trim_start=2.0,
        trim_end=14.0,
        speed=2.0,
    )
    left, right = split_clip(clip, 2.5)
    assert left.clip_id == "v1-a"
    assert right.clip_id == "v1-b"
    assert left.trim_start == pytest.approx(2.0)
    assert left.trim_end == pytest.approx(7.0)
    assert right.trim_start == pytest.approx(7.0)
    assert right.trim_end == pytest.approx(14.0)
    assert left.effective_duration + right.effective_duration == pytest.approx(clip.effective_duration)


def test_split_image_clip_divides_still_duration():
    clip = TimelineClip(clip_id="i1", path="cover.png", kind="image", still_duration=8.0)
    left, right = split_clip(clip, 3.25)
    assert left.still_duration == pytest.approx(3.25)
    assert right.still_duration == pytest.approx(4.75)


def test_timeline_clip_roundtrips_to_persisted_dict():
    clip = TimelineClip(
        clip_id="v1",
        path="source.mp4",
        kind="video",
        source_duration=13.5,
        trim_start=1.0,
        trim_end=11.5,
        speed=1.25,
        render_profile={"style": "whiteboard", "camera": "slow-zoom"},
    )
    restored = TimelineClip.from_dict(clip.to_dict())
    assert restored == clip


def test_invalid_trim_range_is_rejected():
    with pytest.raises(ValueError, match="trim"):
        TimelineClip(
            clip_id="bad",
            path="source.mp4",
            kind="video",
            source_duration=10.0,
            trim_start=7.0,
            trim_end=5.0,
        )
