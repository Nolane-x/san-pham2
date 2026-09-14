from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Sequence

from .ai import build_image_prompt, split_script_into_scenes
from .app import build_services
from .domain import TransitionSpec
from .render import final_duration
from .storage import ProjectStore


def _json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _parse_clip(raw: str) -> tuple[str, float]:
    try:
        clip_id, duration = raw.rsplit(":", 1)
        return clip_id, float(duration)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("clip must be ID:DURATION") from exc


def _parse_transition(raw: str) -> TransitionSpec:
    try:
        from_id, to_id, effect, duration = raw.split(":", 3)
        return TransitionSpec(from_id, to_id, effect, float(duration))
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("transition must be FROM:TO:EFFECT:DURATION") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nolane_studio", description="Nolane Studio forensic rebuild foundation")
    sub = parser.add_subparsers(dest="command", required=True)

    p_db = sub.add_parser("init-db", help="initialize a local Nolane Studio-compatible SQLite database")
    p_db.add_argument("database")

    p_analyze = sub.add_parser("analyze", help="deterministically split and scaffold a script")
    p_analyze.add_argument("text")
    p_analyze.add_argument("--min-words", type=int, default=30)
    p_analyze.add_argument("--max-words", type=int, default=50)
    p_analyze.add_argument("--style", default="whiteboard")
    p_analyze.add_argument("--additional-prompt", default="")

    sub.add_parser("providers", help="list configured provider capabilities without constructing them")

    p_render = sub.add_parser("render-plan", help="inspect recovered additive timeline timing")
    p_render.add_argument("--clip", action="append", type=_parse_clip, default=[])
    p_render.add_argument("--transition", action="append", type=_parse_transition, default=[])

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "init-db":
        store = ProjectStore(args.database)
        store.initialize()
        _json({"status": "ok", "database": args.database})
        return 0

    if args.command == "analyze":
        scenes = split_script_into_scenes(args.text, min_words=args.min_words, max_words=args.max_words)
        payload = []
        for scene in scenes:
            payload.append(
                {
                    "index": scene.index,
                    "text": scene.text,
                    "voice_text": scene.voice_text,
                    "image_prompt": build_image_prompt(scene, args.style, args.additional_prompt),
                }
            )
        _json({"provider_used": None, "scenes": payload})
        return 0

    if args.command == "providers":
        services = build_services()
        descriptors = []
        for descriptor in sorted(services.providers.descriptors(), key=lambda item: item.name):
            descriptors.append({"name": descriptor.name, "capabilities": asdict(descriptor.capabilities)})
        _json(descriptors)
        return 0

    if args.command == "render-plan":
        base = sum(duration for _, duration in args.clip)
        transition_seconds = sum(t.duration for t in args.transition)
        total = final_duration(args.clip, args.transition)
        _json({
            "clips": [{"id": clip_id, "duration": duration} for clip_id, duration in args.clip],
            "base_duration": base,
            "transition_duration": transition_seconds,
            "final_duration": total,
        })
        return 0

    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
