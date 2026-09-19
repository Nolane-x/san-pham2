# Nolane Studio v0.14.0

Apply Drawing Settings To All Scenes forensic-parity release.

Highlights:

- restores the recovered project-wide editor action for applying drawing settings across all scenes;
- persists the currently visible Inspector controls before propagation so the action uses what the user actually sees;
- propagates reveal/hold duration, style, visual mode, brush direction, hand selection, background-removal toggle and automatic object-FX toggle;
- performs the project-wide storage update atomically;
- deliberately preserves every target scene's object-addressed state rather than copying object IDs between scenes;
- preserves target object timing, custom push/effect/sound configuration, custom draw paths, camera/image-motion state and unknown target extras;
- preserves scene metadata such as narration and generated-image ownership;
- exposes the action only when a scene is selected and reports the number of updated scenes;
- preserves v0.13 lossless scene reset, v0.12 selected-scene preview, v0.11 grounded readable labels, v0.10 scene trim/speed, v0.9 object timing, v0.8 narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images and v0.4 AI Analyze behavior.

Forensic boundary:

- the action propagates only scene-wide drawing controls that can be moved safely between scenes;
- object-addressed state is intentionally not propagated because object identity is scene-local;
- non-empty legacy `clips`, `videoClips` and `audioClips` entry schemas remain unrecovered and are not decoded by this slice;
- arbitrary custom draw-path semantics, source-exact non-default hand/background-removal behavior, object-SFX semantics and source-exact legacy label typography/decoration remain evidence-limited.

Release integrity:

- package metadata and runtime `__version__` are both 0.14.0;
- storage coverage proves portable drawing controls propagate while target object-specific state and metadata remain intact;
- offscreen Studio coverage proves the action uses visible Inspector values and preserves target custom timing;
- merge is allowed only after Linux fast tests and the complete Windows test/NUI/portable/installer/checksum packaging workflow pass on the exact final head.
