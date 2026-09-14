from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderProfile:
    style: str = "static"
    camera: str = "static"
    reveal_duration: float = 0.0
    hold_duration: float = 6.0

    def __post_init__(self) -> None:
        style = str(self.style).strip().lower().replace("-", "_")
        camera = str(self.camera).strip().lower().replace("-", "_")
        if style not in {"static", "whiteboard", "color_reveal"}:
            raise ValueError("style must be static, whiteboard, or color_reveal")
        if camera not in {"static", "slow_zoom", "pan_left", "pan_right"}:
            raise ValueError("camera must be static, slow_zoom, pan_left, or pan_right")
        reveal = float(self.reveal_duration)
        hold = float(self.hold_duration)
        if reveal < 0 or hold < 0 or reveal + hold <= 0:
            raise ValueError("render profile requires a positive total duration")
        object.__setattr__(self, "style", style)
        object.__setattr__(self, "camera", camera)
        object.__setattr__(self, "reveal_duration", reveal)
        object.__setattr__(self, "hold_duration", hold)

    @property
    def total_duration(self) -> float:
        return self.reveal_duration + self.hold_duration


def _normalization(width: int, height: int, fps: int) -> str:
    width = max(2, int(width))
    height = max(2, int(height))
    if width % 2:
        width -= 1
    if height % 2:
        height -= 1
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,"
        f"fps={int(fps)},setsar=1"
    )


def _camera_filter(width: int, height: int, fps: int, camera: str) -> str:
    if camera == "static":
        return ""
    if camera == "slow_zoom":
        return (
            f",zoompan=z='min(zoom+0.0008,1.08)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    if camera == "pan_left":
        return (
            f",zoompan=z='1.05':x='max(0,(iw-iw/zoom)*(1-on/(fps*8)))':"
            f"y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={fps}"
        )
    return (
        f",zoompan=z='1.05':x='min(iw-iw/zoom,(iw-iw/zoom)*(on/(fps*8)))':"
        f"y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={fps}"
    )


def build_image_filter_graph(width: int, height: int, fps: int, profile: RenderProfile) -> str:
    """Build a single-output FFmpeg filter graph labeled ``[outv]``.

    Whiteboard mode is implemented as a progressive wipe from a clean white
    canvas to the normalized source. Color reveal starts with a grayscale
    version and progressively exposes color. Camera motion is applied before
    the reveal so the visible scene remains spatially coherent.
    """
    width = max(2, int(width))
    height = max(2, int(height))
    if width % 2:
        width -= 1
    if height % 2:
        height -= 1
    fps = max(1, int(fps))
    total = profile.total_duration
    reveal = min(profile.reveal_duration, total)
    base = _normalization(width, height, fps) + _camera_filter(width, height, fps, profile.camera)

    if profile.style == "static" or reveal <= 0:
        return f"[0:v]{base},trim=duration={total:.6f},setpts=PTS-STARTPTS[outv]"

    if profile.style == "whiteboard":
        return (
            f"color=c=white:s={width}x{height}:r={fps}:d={total:.6f}[white];"
            f"[0:v]{base},trim=duration={total:.6f},setpts=PTS-STARTPTS[image];"
            f"[white][image]xfade=transition=wipeleft:duration={reveal:.6f}:offset=0[outv]"
        )

    return (
        f"[0:v]{base},trim=duration={total:.6f},setpts=PTS-STARTPTS,split=2[gray_src][color_src];"
        f"[gray_src]hue=s=0[gray];"
        f"[gray][color_src]xfade=transition=wipeleft:duration={reveal:.6f}:offset=0[outv]"
    )
