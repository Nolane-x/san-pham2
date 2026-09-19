# Nolane Studio v0.10.0

Scene Clip Trim and Speed forensic-parity release.

Highlights:

- restores direct scene-level clip editing through an explicit rebuild-owned `sceneEdits` timeline contract keyed by stable scene identity;
- supports persisted trim start, trim end and playback speed without decoding the still-unrecovered legacy `clips`, `videoClips` or `audioClips` entry schemas;
- validates scene edit state fail-closed: unknown scenes, duplicate entries, non-finite values, reversed/out-of-range trim windows and non-positive speeds are rejected;
- applies the edited source window and speed consistently to final visual clips and persisted per-scene narration;
- keeps source-video audio synchronized with the edited visual clip while narration follows the same trim/speed window before final duration normalization;
- keeps additive scene transitions independent from clip edits instead of silently converting them into overlap semantics;
- exposes selected-scene Start / End / Speed controls in Studio with reset-to-full-duration behavior;
- preserves unrelated scene edits, transition state and unrecovered legacy timeline payloads when saving one scene edit;
- preserves v0.9 object timing, v0.8 scene narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images, v0.4 AI Analyze and v0.3 Canvas/Object behavior.

Forensic boundary:

- arbitrary custom draw paths, non-default hand rendering, background removal and object-FX/SFX semantics remain evidence-limited;
- arbitrary legacy multi-track clip splitting/cutting and the non-empty `clips`, `videoClips`, `audioClips` and `batch_voice_segments` entry schemas remain fail-closed rather than guessed;
- automatic exact readable-label post-processing remains evidence-limited because its recovered source/layout contract is still incomplete.

Release integrity:

- v0.9.0 remains the Object-level Whiteboard Timing Editor baseline;
- v0.10.0 is the first release where recovered scene-level trim/start-end/speed behavior is persisted explicitly and applied to authoritative final export;
- the feature implementation passed exact-head Linux fast tests and the full Windows test, NUI evidence, portable executable, installer, checksum and artifact packaging gates before its feature PR was merged;
- this metadata closure must itself pass the same branch gates before merge.
