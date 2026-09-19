# Forensic parity scope — v0.9.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. The recovered EXE and recovered design evidence remain behavioral authorities: useful creator workflows and state contracts are restored while legacy branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority of this parity slice

- Recovered render evidence exposes per-object `pause / draw / push` timing and the existing render engine already represents it as `custom_object_timing_config` keyed by stable visual-object identity.
- Studio now exposes that existing contract for the selected visible Canvas layer instead of offering only the coarse Fixed/Custom mode switch.
- A missing custom entry follows the render engine's recovered fallback exactly: zero pause, zero push and an equal share of scene `reveal_duration` for draw time.
- Applying timing replaces or appends only the selected object's canonical entry and preserves unrelated entries.
- **Use default** removes only the selected object's override so the engine fallback becomes authoritative again.
- Object timing controls follow layer selection and are disabled when Fixed mode is active, no scene is selected, or the selected object is not visible.
- Scene duplication remaps custom timing object IDs to the copied scene's newly allocated object IDs, preserving the source scene's custom animation semantics after duplication.
- The underlying sequential `ObjectTimingEntry` plan, whiteboard compositor and final project export behavior are unchanged.
- Existing v0.3 Canvas/Object, v0.4 AI Analyze/Voice, v0.5 Generated Images, v0.6 Advanced Voice, v0.7 Scene Transition and v0.8 Scene Narration authority remains unchanged.

## Evidence-limited boundaries

- Arbitrary custom draw paths and source-exact hand rendering are not inferred from the timing editor.
- Background-removal behavior and object effect/sound routing remain evidence-limited.
- Non-empty legacy `clips`, `videoClips`, `audioClips` and `batch_voice_segments` schemas remain fail-closed.
- Automatic exact readable-label post-processing remains separate forensic work because its source/layout contract is not sufficiently recovered.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- Subsequent parity work must be supported by recovered evidence or be labeled explicitly as new product design.
