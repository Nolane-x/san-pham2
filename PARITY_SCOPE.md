# Forensic parity scope — v0.14.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. Recovered executable behavior and recovered project evidence remain behavioral authorities. Creator workflows are restored only where the state contract is sufficiently grounded; branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority of this parity slice

- The recovered editor exposes a project-wide action to apply drawing settings to all scenes.
- v0.14 treats only scene-wide render controls as portable across scene identities: reveal/hold duration, style, visual mode, brush mode, hand style, background-removal toggle and automatic object-FX toggle.
- The currently visible Inspector controls are persisted first, so project-wide propagation operates on the user's visible state instead of a stale stored snapshot.
- Project-wide propagation is performed in one storage transaction.
- Target-scene object-addressed state remains authoritative for that target. Object timing, custom push/effect/sound configuration, draw paths, camera/image-motion state and unknown target extras are preserved.
- Scene metadata unrelated to scene-wide drawing controls, including narration and generated-image ownership, is preserved.
- The implementation does not copy scene-local object identifiers across scenes.
- Existing v0.3 Canvas/Object through v0.13 Lossless Scene Reset authority remains unchanged.

## Evidence-limited boundaries

- v0.14 does not infer or decode non-empty legacy `clips`, `videoClips`, `audioClips` or `batch_voice_segments` entry schemas.
- Arbitrary custom draw-path behavior and source-exact non-default hand rendering remain separate parity work.
- Background-removal internals and object effect/sound routing remain evidence-limited even though their recovered scene-wide enable/disable controls can be persisted.
- Source-exact legacy label typography/decoration beyond recovered grounded-box placement remains unrecovered.
- Scene lifecycle reconciliation for supported timeline state is tracked separately and must be rebased from clean current `main` rather than merged from the stale diverged v0.13 branch.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, OCR dependency or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- Subsequent parity work must be supported by recovered evidence or be labeled explicitly as new product design.
