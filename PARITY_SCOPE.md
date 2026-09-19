# Forensic parity scope — v0.6.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. The recovered EXE and recovered design evidence remain behavioral authorities: useful creator workflows and state contracts are restored while legacy branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority of this parity slice

- Recovered evidence states that the old voice subsystem supported ordinary synthesis, saved/provider voices, reference-based cloning and designed voices.
- The rebuild represents those behaviors as provider capabilities: `tts`, `clone`, `design` and `list_voices`; Studio never branches on provider names.
- Voice From Content accepts language, voice, speed, optional reference audio/text and optional design instructions for both selected-scene and project-wide generation.
- Reference audio is content-hashed. Cache identity includes narration text, provider, language, voice, speed, reference-audio hash, reference text and design instructions, so unchanged work is reused while meaningful input changes invalidate it.
- Capability preflight happens before advanced inputs reach a provider. Clone/design requests fail closed when the selected provider does not advertise the corresponding capability.
- Studio reads lazy provider descriptors to show or hide reference-audio, reference-text, design and catalog controls without instantiating the provider merely by opening the editor.
- Voice catalog loading is an explicit user action and is routed only when `list_voices` is advertised.
- The normal OpenAI-compatible TTS base/model path remains synthesize-only.
- An explicitly configured Advanced TTS endpoint uses the existing generic JSON-in/binary-out adapter for synthesize/clone/design fields. An optional, separately configured voice-catalog endpoint enables `list_voices`.
- Advanced TTS and catalog endpoints may be supplied from local settings or `NOLANE_STUDIO_TTS_ADVANCED_ENDPOINT` / `NOLANE_STUDIO_TTS_VOICES_ENDPOINT` environment overrides.
- Existing v0.3 Canvas/Object, v0.4 AI Analyze/Voice and v0.5 generated-image storage/render/export authority remains unchanged.

## Evidence-limited boundaries

- The recovered evidence defines voice capabilities but does not establish one universal vendor wire protocol for cloning/design. Nolane Studio therefore does not invent an “OpenAI-compatible clone API”; advanced HTTP transport is an explicit generic wrapper contract.
- Provider-internal saved-voice storage remains provider-owned. Nolane Studio consumes optional discovery through `list_voices` rather than recreating the removed heavyweight OmniVoice runtime.
- Exact readable-label post-processing and non-empty legacy multi-track `clips` / `videoClips` / `audioClips` entry schemas remain explicit forensic work because their source/layout or per-entry contracts are not sufficiently recovered.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- Subsequent parity work must be supported by recovered evidence or be labeled explicitly as new product design.
