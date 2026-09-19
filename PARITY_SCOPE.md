# Forensic parity scope — v0.17.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. Recovered executable behavior and recovered project evidence remain behavioral authorities. Creator workflows are restored only where the state contract is sufficiently grounded; branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority recovered through v0.17

- v0.3 established durable Canvas/object state used by the visual editor and authoritative render pipeline.
- v0.4 restored API-first AI Analyze plus per-scene Voice From Content contracts.
- v0.5 restored the optional generated-image workflow with hardened prompts, durable scene-owned media and deterministic cache identity.
- v0.6 expanded voice support through provider capabilities rather than vendor/runtime coupling.
- v0.7 restored persisted additive scene transitions.
- v0.8 bound persisted per-scene narration into authoritative final export.
- v0.9 exposed recovered per-object whiteboard pause/draw/push timing.
- v0.10 introduced the rebuild-owned `sceneEdits` contract for trim/speed.
- v0.11 materialized grounded readable labels as persisted Canvas text objects.
- v0.12 restored selected-scene Preview through the authoritative render pipeline.
- v0.13 restored bounded lossless scene render reset.
- v0.14 restored project-wide propagation of scene-wide drawing settings without copying object-addressed state.
- v0.15 restored coherent supported timeline state across scene lifecycle mutations.
- v0.16 exposed the recovered additive whiteboard outro with verified leftward scene exit.
- v0.17 aligns UI-authored per-object Push timing with the renderer's existing scene-level activation contract. Positive Push is derived only from visible-object custom timing, which is the same population used by the render plan. Saving or resetting timing updates `large_object_push_enabled` when the persisted timing shape is interpretable; hidden/stale object entries are ignored for activation, while malformed/ambiguous timing causes the UI to preserve existing activation state rather than guess. Existing mode/direction values remain untouched, and ProjectSceneExporter remains the authority that rejects unsupported push combinations.

## Evidence-limited boundaries

- v0.17 does not add new push motion. The recovered/default automatic `from_left` path is the only object-push direction/mode currently rendered faithfully.
- Non-automatic push modes, custom push configs, unsupported push directions and source-video positive push remain fail-closed.
- Whiteboard outro direction `left` is recovered and rendered; other direction values remain unsupported/fail-closed.
- Non-empty legacy `clips`, `videoClips`, `audioClips` and `batch_voice_segments` entry schemas remain unrecovered.
- Arbitrary legacy multi-track splitting/cutting remains unrecovered.
- Arbitrary custom draw-path semantics and source-exact non-default hand rendering remain separate parity work.
- Background-removal internals and object effect/sound routing remain evidence-limited.
- Source-exact legacy label typography/decoration beyond grounded-box placement remains unrecovered.
- New parity work must distinguish recovered evidence from rebuild-owned contracts and must not claim source parity merely because a plausible implementation exists.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, OCR dependency or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- SQLite remains authoritative local project state and FFmpeg remains the authoritative supported media composition layer.
- Unsupported recovered state must fail closed rather than be silently discarded or guessed.
