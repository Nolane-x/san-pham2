# Forensic parity scope — v0.10.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. The recovered EXE and recovered design evidence remain behavioral authorities: useful creator workflows and state contracts are restored while legacy branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority of this parity slice

- Recovered Visual Editor behavior supports clip transport/editing, but the legacy non-empty `clips`, `videoClips` and `audioClips` entry schemas are not recovered strongly enough to decode safely.
- Nolane Studio therefore uses an explicit rebuild-owned `sceneEdits` list keyed by stable scene identity for the recovered scene-level subset: `trim_start`, `trim_end` and `speed`.
- Scene edits are validated against authoritative scene render-plan durations and fail closed on unknown scene IDs, duplicate IDs, non-finite numbers, invalid trim windows, out-of-range trim end values or non-positive playback speeds.
- The effective scene duration is `(trim_end - trim_start) / speed`; final export applies the same source window and speed to visual content, source-video audio and persisted scene narration.
- Static/image scenes preserve their visual content while their edited duration and narration window follow the same scene-level contract.
- Scene transitions retain the recovered additive semantics and are applied independently after scene edits rather than becoming overlapping crossfades.
- Studio exposes Start / End / Speed controls for the selected scene and a reset action that removes only that scene's explicit edit.
- Saving one scene edit preserves unrelated scene edits, transition state and legacy timeline payloads.
- Existing v0.3 Canvas/Object, v0.4 AI Analyze/Voice, v0.5 Generated Images, v0.6 Advanced Voice, v0.7 Scene Transition, v0.8 Scene Narration and v0.9 Object Timing authority remains unchanged.

## Evidence-limited boundaries

- Arbitrary custom draw paths and source-exact hand rendering are not inferred from scene clip editing.
- Background-removal behavior and object effect/sound routing remain evidence-limited.
- Arbitrary legacy multi-track clip splitting/cutting and non-empty `clips`, `videoClips`, `audioClips` and `batch_voice_segments` entry schemas remain fail-closed.
- Automatic exact readable-label post-processing remains separate forensic work because its source/layout contract is not sufficiently recovered.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- Subsequent parity work must be supported by recovered evidence or be labeled explicitly as new product design.
