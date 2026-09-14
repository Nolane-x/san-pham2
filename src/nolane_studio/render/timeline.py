from __future__ import annotations

from collections.abc import Sequence

from nolane_studio.domain import TransitionSpec


def _transition_map(transitions: Sequence[TransitionSpec]) -> dict[tuple[str, str], TransitionSpec]:
    result: dict[tuple[str, str], TransitionSpec] = {}
    for transition in transitions:
        key = (transition.from_id, transition.to_id)
        if key in result:
            raise ValueError(f"duplicate transition {key!r}")
        result[key] = transition
    return result


def build_transition_gaps(clip_ids: Sequence[str], transitions: Sequence[TransitionSpec]) -> list[float]:
    lookup = _transition_map(transitions)
    adjacent = {(str(a), str(b)) for a, b in zip(clip_ids, clip_ids[1:])}
    invalid = set(lookup) - adjacent
    if invalid:
        raise ValueError(f"transitions must connect adjacent clips: {sorted(invalid)!r}")
    return [lookup.get((str(a), str(b))).duration if (str(a), str(b)) in lookup else 0.0 for a, b in zip(clip_ids, clip_ids[1:])]


def final_duration(clips: Sequence[tuple[str, float]], transitions: Sequence[TransitionSpec]) -> float:
    ids: list[str] = []
    base = 0.0
    for clip_id, duration in clips:
        duration = float(duration)
        if duration < 0:
            raise ValueError("clip duration must be >= 0")
        ids.append(str(clip_id))
        base += duration
    gaps = build_transition_gaps(ids, transitions)
    return base + sum(gaps)
