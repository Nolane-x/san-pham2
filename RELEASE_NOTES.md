# Nolane Studio v0.17.0

Visible Object Push Activation Integrity forensic-parity release.

Highlights:

- closes the gap between the recovered per-object Push timing editor and the authoritative whiteboard push/export contract;
- saving custom object timing derives `large_object_push_enabled` from positive Push timing across currently visible scene objects, matching the timing entries the renderer actually consumes;
- resetting an object's timing recomputes the same activation contract, so removing the final positive visible Push disables scene push instead of leaving stale enabled state;
- hidden or stale object timing is preserved but cannot spuriously enable scene push, matching render-plan visibility semantics;
- existing automatic push mode and persisted direction are preserved rather than silently rewritten;
- malformed or ambiguous legacy timing makes activation derivation return no decision, so the UI preserves the existing activation flag instead of inventing a repair;
- duplicate timing entries for the same currently visible object are treated as ambiguous exactly like the renderer does, preventing UI-side activation drift before export preflight;
- UI-saved positive Push is covered through `ProjectSceneExporter`, proving it passes the existing push preflight and reaches the authoritative whiteboard render path;
- preserves v0.16 recovered whiteboard outro controls and every earlier verified parity wave.

Forensic boundary:

- this release synchronizes activation only; it does not claim new object-push motion semantics;
- the authoritative renderer still supports only the existing recovered/default automatic `from_left` push direction; non-automatic modes, custom push configs and unsupported directions remain fail-closed;
- source-video positive push remains unsupported by the faithful renderer;
- malformed timing for the currently selected layer can still be rejected by existing timing/UI validation paths rather than being silently coerced;
- arbitrary custom draw paths, source-exact non-default hand/background-removal behavior, object-FX/SFX routing, non-empty legacy `clips` / `videoClips` / `audioClips` / `batch_voice_segments` schemas and source-exact legacy label typography/decoration remain evidence-limited.

Release integrity:

- package metadata and runtime `__version__` are both 0.17.0;
- new tests lock positive activation, reset/deactivation, hidden stale timing isolation, malformed-state preservation and ProjectSceneExporter compatibility;
- the implementation fast gate passed after correcting the malformed-other-object test setup;
- merge is allowed only after Linux fast tests and the complete Windows test/NUI/portable/installer/checksum packaging workflow pass on the exact final release head.
