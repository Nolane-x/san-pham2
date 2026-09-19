# Forensic parity scope — v0.16.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. Recovered executable behavior and recovered project evidence remain behavioral authorities. Creator workflows are restored only where the state contract is sufficiently grounded; branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority recovered through v0.16

- v0.3 established durable Canvas/object state used by the visual editor and authoritative render pipeline.
- v0.4 restored API-first AI Analyze plus per-scene Voice From Content contracts.
- v0.5 restored the optional generated-image workflow with hardened prompts, durable scene-owned media and deterministic cache identity.
- v0.6 expanded voice support through provider capabilities rather than vendor/runtime coupling.
- v0.7 restored persisted additive scene transitions: transition duration is added and never steals source-scene duration.
- v0.8 bound persisted per-scene narration into authoritative final export, including source-video audio mixing and scene-duration normalization.
- v0.9 exposed recovered per-object whiteboard pause/draw/push timing and preserves object timing across scene duplication by remapping copied object IDs.
- v0.10 introduced the explicit rebuild-owned `sceneEdits` contract for scene trim-start, trim-end and speed; the same window applies to visuals and narration.
- v0.11 materializes exact AI Analyze grounded labels as persisted Canvas text objects using recovered normalized box placement, while deliberately using neutral rebuild typography where source-exact styling is not evidenced.
- v0.12 restores the Studio Preview control as a real selected-scene render through the authoritative Canvas/video/whiteboard pipeline, with narration and `sceneEdits`, but without project transitions/order.
- v0.13 restores bounded lossless reset of scene render/motion state while preserving scene content, media ownership, narration and analysis metadata.
- v0.14 restores project-wide application of scene-wide drawing controls without copying scene-local object-addressed state between scenes.
- v0.15 keeps supported timeline state coherent across scene Add/Duplicate/Move/Delete, including exact `mediaOrder`, transition adjacency, scene-edit pruning/cloning and fail-closed opaque legacy tracks.
- v0.16 exposes the already-implemented recovered whiteboard outro control in Studio. The authoritative whiteboard pipeline treats the outro as an additive phase after the final hold, includes its duration in scene duration, and renders the strongly evidenced `left` direction as a full-scene FFmpeg exit. Studio persists enable/duration/verified direction, preserves unsupported legacy direction values until explicit repair, prevents new non-whiteboard outro state, restores defaults through Reset scene, and keeps outro scene-local during project-wide drawing-settings propagation.

## Evidence-limited boundaries

- Whiteboard outro direction `left` is recovered and rendered; other direction values are not approximated and remain unsupported/fail-closed until stronger evidence exists.
- Whiteboard outro on source-video composition and outro behavior for non-whiteboard styles remain outside the faithful renderer.
- v0.16 does not infer or decode non-empty legacy `clips`, `videoClips`, `audioClips` or `batch_voice_segments` entry schemas.
- Arbitrary legacy multi-track splitting/cutting remains unrecovered; generic rebuild timeline helpers are not treated as proof of the original persisted schema.
- Arbitrary custom draw-path semantics and source-exact non-default hand rendering remain separate parity work.
- Background-removal internals and object effect/sound routing remain evidence-limited even though recovered enable/disable controls can be persisted.
- Source-exact legacy label font family, decoration, callout shapes, collision avoidance and other layout nuance beyond grounded-box placement remain unrecovered.
- New parity work must distinguish recovered evidence from rebuild-owned contracts and must not claim source parity merely because a plausible implementation exists.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, OCR dependency or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- SQLite remains authoritative local project state and FFmpeg remains the authoritative supported media composition layer.
- Unsupported recovered state must fail closed rather than be silently discarded or guessed.
