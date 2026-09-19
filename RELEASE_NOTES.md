# Nolane Studio v0.16.0

Recovered Whiteboard Outro Controls forensic-parity release.

Highlights:

- exposes the already-recovered whiteboard outro contract in the Studio Inspector instead of leaving it hidden in persisted render state;
- lets a whiteboard scene enable or disable its additive post-hold outro and edit the recovered 0–5 second outro duration;
- exposes only the strongly evidenced/rendered `left` direction for new edits; no unsupported direction is invented;
- preserves an unknown persisted legacy outro direction as an explicit `Unsupported · <value>` choice until the user deliberately selects verified `left`, preventing silent project-state rewriting;
- disables creation/editing of outro state for `color_reveal`, because the authoritative project exporter currently verifies outro only for whiteboard scenes without source video;
- keeps the Inspector compact by placing On/direction/duration in one row, preserving the existing 720p-oriented workspace density;
- Reset scene restores the canonical recovered outro defaults: disabled, `left`, 0.3 seconds;
- Apply drawing settings to all scenes intentionally does not copy scene-specific outro state between scenes;
- reuses the existing authoritative whiteboard renderer, duration math and FFmpeg scene-exit implementation rather than creating a second motion path;
- preserves v0.15 scene lifecycle integrity, v0.14 project-wide drawing settings, v0.13 lossless scene reset, v0.12 selected-scene preview, v0.11 grounded readable labels, v0.10 scene trim/speed, v0.9 object timing, v0.8 narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images and v0.4 AI Analyze behavior.

Forensic boundary:

- `left` is the only whiteboard outro direction currently supported by recovered evidence and the authoritative renderer; other persisted directions remain fail-closed/preserved rather than approximated;
- whiteboard outro with source-video composition and non-whiteboard outro behavior remain unsupported by the current faithful renderer;
- arbitrary custom draw paths, source-exact non-default hand/background-removal behavior, object-FX/SFX routing, non-empty legacy `clips` / `videoClips` / `audioClips` / `batch_voice_segments` schemas and source-exact legacy label typography/decoration remain evidence-limited.

Release integrity:

- package metadata and runtime `__version__` are both 0.16.0;
- renderer-level outro tests already lock additive duration, post-hold placement, verified leftward FFmpeg motion and fail-closed unknown directions;
- new offscreen Studio coverage locks persistence, unknown-direction preservation/repair, color-reveal gating, reset defaults and project-wide apply isolation;
- implementation fast tests passed before release closure;
- merge is allowed only after Linux fast tests and the complete Windows test/NUI/portable/installer/checksum packaging workflow pass on the exact final release head.
