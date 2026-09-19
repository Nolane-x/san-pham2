# Nolane Studio v0.8.0

Scene Narration Final Export forensic-parity release.

Highlights:

- closes the gap between Voice From Content persistence and final project export: persisted per-scene `voice_path` now reaches the authoritative rendered scene clip;
- preflights every persisted narration source before any scene renderer starts, so stale/missing voice media cannot leave a partially rendered project export;
- carries scene metadata into the render plan without replacing Canvas/Object or render-configuration authority;
- adds an optional `narration_audio` surface to normalized export clips while preserving the old no-narration command path;
- replaces synthetic silence with narration for image/static scenes;
- mixes narration with existing source-video/normalized-scene audio rather than silently discarding either layer;
- uses narration directly when the video source is silent;
- resamples narration to 48 kHz, pads short narration and trims long narration to the authoritative scene duration;
- keeps additive transitions independent: transition segments remain separate and do not steal or overlap narrated scene duration;
- retains fail-closed boundaries for unrecovered `audioClips`, `batch_voice_segments` and object-SFX semantics;
- adds real bundled-FFmpeg smoke coverage for narrated image normalization and narration/source-audio mixing;
- preserves v0.7 transitions, v0.6 advanced voice, v0.5 generated images, v0.4 AI Analyze and v0.3 Canvas/Object behavior.

Forensic boundary:

- this release does not decode legacy multi-track audio entries or batch-voice scheduling whose exact persisted schemas remain unrecovered;
- custom object sound effects remain separate from scene narration until their routing/timing contract is recovered;
- advanced drawing/custom paths, non-default hand/background-removal/object-FX behavior and exact readable-label post-processing remain evidence-limited.

Release integrity:

- v0.7.0 remains the Scene Transition Editor baseline;
- v0.8.0 is the first release where persisted per-scene narration participates in final project audio composition;
- final exact-head verification must pass the complete Linux/Windows suite, real FFmpeg narration smokes, NUI evidence, portable executable smoke, installer validation, checksums and artifact upload before merge.
