# Nolane Studio v0.9.0

Object-level Whiteboard Timing Editor forensic-parity release.

Highlights:

- exposes the recovered per-object whiteboard timing contract directly in Studio for the selected visible Canvas layer;
- supports explicit per-object `pause`, `draw` and `push` durations without changing the render engine's sequential timing semantics;
- uses the existing engine fallback for objects without an explicit custom entry: zero pause/push and `reveal_duration / visible_object_count` draw time;
- keeps timing controls synchronized with Canvas/layer selection and disables object timing when the scene is in Fixed mode or no visible layer is selected;
- applies one selected-object timing override without destroying unrelated timing entries;
- adds a per-object **Use default** action that removes only the selected override and returns that layer to the recovered engine fallback;
- fixes scene duplication so custom timing entries are remapped from source object IDs to the copied scene's new object IDs instead of silently falling back to defaults;
- preserves the existing whiteboard compositor, brush-direction, push, outro, camera, scene narration and additive transition behavior;
- preserves v0.8 scene narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images, v0.4 AI Analyze and v0.3 Canvas/Object behavior.

Forensic boundary:

- arbitrary custom draw paths, non-default hand rendering, background removal and object-FX/SFX semantics remain evidence-limited;
- non-empty legacy `clips`, `videoClips`, `audioClips` and `batch_voice_segments` payload schemas remain fail-closed;
- automatic exact readable-label post-processing remains evidence-limited because its recovered source/layout contract is still incomplete.

Release integrity:

- v0.8.0 remains the Scene Narration Final Export baseline;
- v0.9.0 is the first release where recovered custom per-object pause/draw/push timing is directly editable in Studio;
- final exact-head verification must pass the complete Linux/Windows suite, NUI evidence, portable executable smoke, installer validation, checksums and artifact upload before merge.
