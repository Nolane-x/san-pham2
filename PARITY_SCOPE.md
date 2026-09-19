# Forensic parity scope — v0.13.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. The recovered EXE and recovered design evidence remain behavioral authorities: useful creator workflows and state contracts are restored while legacy branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority recovered through v0.13

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
- v0.13 keeps supported timeline state coherent across scene Add/Duplicate/Move/Delete. Scene lifecycle changes rewrite `mediaOrder` to authoritative current scene order, retain only still-adjacent transitions, prune deleted-scene edits, clone a duplicated scene's `sceneEdits` entry, and fail closed before mutation when opaque legacy track buckets are non-empty.

## Evidence-limited boundaries

- Arbitrary custom draw-path semantics remain unrecovered beyond persisted Canvas drawing objects and the supported whiteboard reveal/timing pipeline.
- Source-exact non-default hand rendering and background-removal behavior remain separate parity work.
- Object effect/SFX configuration names are recovered, and final composition is known to support object SFX conceptually, but exact routing/config semantics remain evidence-limited.
- Source-exact legacy label font family, decoration, callout shapes, collision avoidance and other layout nuance beyond grounded-box placement remain unrecovered.
- Arbitrary legacy multi-track clip splitting/cutting and non-empty `clips`, `videoClips`, `audioClips` and `batch_voice_segments` entry schemas remain fail-closed. The generic rebuild `TimelineClip/split_clip` helper is not treated as proof of the legacy persisted schema.
- New parity work must distinguish recovered evidence from rebuild-owned contracts and must not claim source parity merely because a plausible implementation exists.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, OCR dependency or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- SQLite remains authoritative local project state and FFmpeg remains the authoritative supported media composition layer.
- Unsupported recovered state must fail closed rather than be silently discarded or guessed.
