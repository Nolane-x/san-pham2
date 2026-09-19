# Forensic parity scope — v0.8.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. The recovered EXE and recovered design evidence remain behavioral authorities: useful creator workflows and state contracts are restored while legacy branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority of this parity slice

- Recovered render evidence states that voice/source-video audio are final composition layers; generated or explicitly attached per-scene narration must therefore reach authoritative final export rather than remain only in metadata/media storage.
- Voice From Content already persists scene-local narration through `voice_path` and `voice_media_id`. v0.8 carries that persisted path through `SceneRenderPlan` into `ExportClip`.
- Every persisted `voice_path` is preflighted across the whole project before any scene renderer starts. Missing/stale narration fails closed through `MissingSceneNarration`.
- Image/static scene normalization replaces the synthetic silent track with scene narration when narration is present.
- Rendered whiteboard/video scenes carry the same scene-local narration into final normalization.
- When a normalized video already has audio, narration is mixed with that source audio rather than silently replacing it.
- When a video has no source audio, narration becomes the scene audio without fabricating an additional mix layer.
- Narration is resampled, padded when shorter and trimmed to the authoritative scene duration, so scene duration and additive transition duration remain independent.
- Existing no-narration FFmpeg command behavior remains unchanged.
- Existing v0.3 Canvas/Object, v0.4 AI Analyze/Voice, v0.5 Generated Images, v0.6 Advanced Voice and v0.7 Scene Transition authority remains unchanged.

## Evidence-limited boundaries

- Non-empty legacy `audioClips`, `videoClips` and `clips` entry schemas remain fail-closed; this slice does not reinterpret them as scene narration.
- `batch_voice_segments` remains fail-closed because its persisted segment scheduling semantics are not sufficiently recovered for final composition.
- Object SFX/custom sound semantics remain evidence-limited and are not inferred from scene narration.
- Advanced legacy drawing behavior, exact readable-label post-processing and unrecovered multi-track trimming/cutting remain separate forensic work.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- Subsequent parity work must be supported by recovered evidence or be labeled explicitly as new product design.
