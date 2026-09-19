# Nolane Studio v0.12.0

Selected Scene Preview forensic-parity release.

Highlights:

- restores the recovered Studio Preview control as a real selected-scene render instead of a placeholder;
- routes preview through the same authoritative persisted Canvas/video/whiteboard scene pipeline used by final rendering;
- includes persisted per-scene narration in preview output;
- honors the rebuild-owned `sceneEdits` trim-start, trim-end and playback-speed contract for the selected scene;
- intentionally excludes project ordering and additive scene transitions because Preview is a local scene inspection action rather than a project export;
- renders and preflights only the selected scene, so an unrelated unsupported scene cannot block local preview;
- opens the rendered preview from the Studio toolbar after the background render task completes;
- rejects missing/unknown selected scenes and invalid persisted edit state fail-closed;
- preserves v0.11 grounded readable labels, v0.10 scene clip trim/speed, v0.9 object timing, v0.8 narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images and v0.4 AI Analyze behavior.

Forensic boundary:

- selected-scene preview does not decode the still-unrecovered non-empty legacy `clips`, `videoClips` or `audioClips` entry schemas;
- project transition/order behavior remains final-export-only by design for this recovered control;
- arbitrary custom draw paths, source-exact non-default hand/background-removal behavior, object-SFX semantics and source-exact legacy label typography/decoration remain evidence-limited.

Release integrity:

- package metadata and runtime `__version__` are both 0.12.0;
- preview behavior is covered by selected-only render, narration binding, trim/speed, transition exclusion, unknown-scene fail-fast and toolbar wiring tests;
- merge is allowed only after Linux fast tests and the complete Windows test/NUI/portable/installer/checksum packaging workflow pass on the exact final head.
