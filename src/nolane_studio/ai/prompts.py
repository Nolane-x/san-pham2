from __future__ import annotations

from nolane_studio.domain import Scene


def build_image_prompt(scene: Scene, style: str, additional_prompt: str = "") -> str:
    style = (style or "whiteboard").strip().lower()
    additional_prompt = (additional_prompt or "").strip()

    if style == "whiteboard":
        semantic = scene.image_prompt.strip() if scene.image_prompt else "Illustrate the scene meaning with a few clear visual objects."
        parts = [
            "Pure white background.",
            "Simple 2D hand-drawn explainer illustration with clean black outlines and sparse purposeful color.",
            semantic,
            "Do not render long text, captions, paragraphs, numbers, watermarks, UI, borders, or decorative background clutter.",
            "Leave readable labels to the deterministic post-processing overlay.",
        ]
    else:
        semantic = scene.image_prompt.strip() or scene.text
        parts = [f"{style.title()} visual style.", semantic]

    if additional_prompt:
        parts.append(additional_prompt)
    return " ".join(part.strip() for part in parts if part.strip())
