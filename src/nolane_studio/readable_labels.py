from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .storage.store import ProjectStore


CANVAS_WIDTH = 1280.0
CANVAS_HEIGHT = 720.0
READABLE_LABEL_OWNER = "nolane-readable-label-overlay-v1"


@dataclass(frozen=True, slots=True)
class ReadableLabelSpec:
    analysis_index: int
    text: str
    x: float
    y: float
    width: float
    height: float
    analysis_content_hash: str


def _label_specs(
    metadata: Mapping[str, Any] | None,
    *,
    canvas_width: float = CANVAS_WIDTH,
    canvas_height: float = CANVAS_HEIGHT,
) -> tuple[ReadableLabelSpec, ...]:
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, Mapping):
        raise ValueError("scene metadata must be a mapping")

    render_config = metadata.get("render_config")
    if render_config is not None:
        if not isinstance(render_config, Mapping):
            raise ValueError("scene render_config must be a mapping")
        style = str(render_config.get("style") or "whiteboard").strip().lower()
        if style and style != "whiteboard":
            return ()

    analysis = metadata.get("ai_analysis")
    if analysis is None:
        return ()
    if not isinstance(analysis, Mapping):
        raise ValueError("ai_analysis must be a mapping")

    raw_objects = analysis.get("objects", [])
    if not isinstance(raw_objects, (list, tuple)):
        raise ValueError("ai_analysis objects must be a list")

    content_hash = str(analysis.get("content_hash") or "").strip()
    specs: list[ReadableLabelSpec] = []
    for index, raw in enumerate(raw_objects):
        if not isinstance(raw, Mapping):
            raise ValueError(f"readable label {index} must be a mapping")

        label = str(raw.get("label") or "").strip()
        if not label:
            raise ValueError(f"readable label {index} text must not be blank")

        box = raw.get("box")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            raise ValueError(f"readable label box {index} must contain four coordinates")
        try:
            x1, y1, x2, y2 = (float(value) for value in box)
        except (TypeError, ValueError):
            raise ValueError(f"readable label box {index} must contain finite numbers") from None
        if any(not math.isfinite(value) for value in (x1, y1, x2, y2)):
            raise ValueError(f"readable label box {index} must contain finite numbers")
        if any(value < 0.0 or value > 1.0 for value in (x1, y1, x2, y2)):
            raise ValueError(f"readable label box {index} must stay within 0..1")
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"readable label box {index} must have positive area")

        specs.append(
            ReadableLabelSpec(
                analysis_index=index,
                text=label,
                x=x1 * canvas_width,
                y=y1 * canvas_height,
                width=(x2 - x1) * canvas_width,
                height=(y2 - y1) * canvas_height,
                analysis_content_hash=content_hash,
            )
        )
    return tuple(specs)


def validate_readable_label_metadata(
    metadata: Mapping[str, Any] | None,
) -> None:
    """Validate the recovered label source contract without mutating project state."""
    _label_specs(metadata)


def _owned_label_slots(
    rows: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    slots: dict[int, dict[str, Any]] = {}
    for row in rows:
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            continue
        if payload.get("nolane_owner") != READABLE_LABEL_OWNER:
            continue
        object_id = str(row.get("id") or "").strip()
        if str(row.get("kind") or "").strip().lower() != "text":
            raise ValueError(
                f"readable label object {object_id} must remain a text object"
            )
        index = payload.get("analysis_index")
        if type(index) is not int or index < 0:
            raise ValueError(
                f"readable label object {object_id} analysis_index must be a non-negative integer"
            )
        if index in slots:
            raise ValueError(
                f"readable label analysis_index {index} must be unique"
            )
        slots[index] = row
    return slots


def validate_readable_label_object_state(
    store: ProjectStore,
    scene_id: str,
) -> None:
    """Validate existing service-owned label slots without mutating them."""
    scene_id = str(scene_id).strip()
    if not scene_id:
        raise ValueError("scene_id must not be blank")
    _owned_label_slots(store.list_visual_objects(scene_id))


def sync_readable_label_objects(
    store: ProjectStore,
    scene_id: str,
    metadata: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Materialize recovered readable labels as deterministic editable Canvas text layers.

    The recovered behavior requires exact label text to be added after image
    generation rather than delegated to the image model. Grounded AI Analyze
    boxes provide the recovered placement authority. Typography is deliberately
    a neutral rebuild default, not a claim about legacy source-exact styling.
    """

    scene_id = str(scene_id).strip()
    if not scene_id:
        raise ValueError("scene_id must not be blank")

    # Compile and validate every requested label before the first write.
    specs = _label_specs(metadata)
    rows = store.list_visual_objects(scene_id)
    existing = _owned_label_slots(rows)

    result_ids: list[str] = []
    desired_slots = {spec.analysis_index for spec in specs}
    for spec in specs:
        payload = {
            "text": spec.text,
            "font_size": 32,
            "color": "#20232A",
            "nolane_owner": READABLE_LABEL_OWNER,
            "analysis_index": spec.analysis_index,
            "analysis_content_hash": spec.analysis_content_hash,
        }
        row = existing.get(spec.analysis_index)
        if row is None:
            object_id = store.add_visual_object(
                scene_id,
                "text",
                name=f"Readable label · {spec.text}",
                x=spec.x,
                y=spec.y,
                width=spec.width,
                height=spec.height,
                payload=payload,
            )
        else:
            object_id = str(row["id"])
            store.update_visual_object(
                object_id,
                name=f"Readable label · {spec.text}",
                x=spec.x,
                y=spec.y,
                width=spec.width,
                height=spec.height,
                payload=payload,
            )
        result_ids.append(object_id)

    # Remove only stale service-owned slots; manual text and every other layer
    # are intentionally outside this service's authority.
    for index, row in existing.items():
        if index not in desired_slots:
            store.delete_visual_object(str(row["id"]))

    return tuple(result_ids)
