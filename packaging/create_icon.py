from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def build_icon(size: int = 512) -> Image.Image:
    image = Image.new("RGBA", (size, size), (10, 11, 15, 255))
    draw = ImageDraw.Draw(image)
    margin = int(size * 0.10)
    radius = int(size * 0.22)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=(132, 118, 255, 255),
    )
    # New, authored Nolane mark: a continuous N path with a mint terminal.
    stroke = int(size * 0.085)
    x1, x2 = int(size * 0.31), int(size * 0.69)
    y1, y2 = int(size * 0.31), int(size * 0.69)
    draw.line((x1, y2, x1, y1, x2, y2, x2, y1), fill=(10, 11, 15, 255), width=stroke, joint="curve")
    dot = int(size * 0.055)
    draw.ellipse((x2 - dot, y1 - dot, x2 + dot, y1 + dot), fill=(78, 215, 197, 255))
    return image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image = build_icon()
    image.save(output, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
