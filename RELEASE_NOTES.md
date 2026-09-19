# Nolane Studio v0.13.0

Lossless Scene Render Reset forensic-parity release.

Highlights:

- restores the recovered Inspector `Reset scene` control as a real bounded action instead of an inert placeholder;
- restores canonical render defaults for reveal/hold timing, style, visual mode, brush direction, hand selection, background-removal toggle, object-FX toggle and object timing mode;
- removes stale custom render configuration, including future/unknown keys stored inside the scene `render_config` envelope;
- deliberately preserves scene text, Canvas objects and layer order, imported/generated media ownership, narration metadata, AI-analysis metadata and project ordering;
- leaves legacy non-empty timeline buckets and object-SFX schemas untouched rather than guessing their structure;
- refreshes the visible Inspector/Canvas state immediately after reset;
- preserves v0.12 selected-scene preview, v0.11 grounded readable labels, v0.10 scene trim/speed, v0.9 object timing, v0.8 narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images and v0.4 AI Analyze behavior.

Forensic boundary:

- `Reset scene` is implemented only as a render-state reset because that boundary is represented explicitly in the recovered editor state;
- it does not delete content, media, narration or analysis state and does not reinterpret unrecovered legacy multi-track/object-SFX payloads;
- arbitrary custom draw paths, source-exact non-default hand/background-removal behavior, object-SFX semantics and source-exact legacy label typography/decoration remain evidence-limited.

Release integrity:

- package metadata and runtime `__version__` are both 0.13.0;
- storage coverage proves render-only reset and preservation of non-render metadata/Canvas layers;
- offscreen Studio coverage proves the recovered Reset control updates the UI and preserves the selected layer;
- merge is allowed only after Linux fast tests and the complete Windows test/NUI/portable/installer/checksum packaging workflow pass on the exact final head.
