import pytest
from nolane_studio.domain import TransitionSpec
from nolane_studio.render.timeline import build_transition_gaps, final_duration


def test_transitions_are_additive_not_overlapping():
    clips = [("a", 8.0), ("b", 7.0), ("c", 4.0)]
    transitions = [TransitionSpec("a","b","fade",0.6), TransitionSpec("b","c","zoom",1.2)]
    assert final_duration(clips, transitions) == pytest.approx(20.8)
    assert build_transition_gaps(["a","b","c"], transitions) == [0.6, 1.2]


def test_transition_must_connect_adjacent_clips():
    clips = [("a", 3.0), ("b", 3.0), ("c", 3.0)]
    with pytest.raises(ValueError, match="adjacent"):
        final_duration(clips, [TransitionSpec("a","c","fade",0.5)])


def test_negative_clip_duration_is_rejected():
    with pytest.raises(ValueError, match="duration"):
        final_duration([("a", -1.0)], [])
