# Nolane Studio v0.6.0

Advanced Voice Capabilities forensic-parity release.

Highlights:

- restores the recovered capability model for ordinary TTS, reference-audio cloning, designed voices and optional voice discovery without reintroducing the legacy OmniVoice runtime;
- routes reference audio/text and design instructions through selected-scene Generate voice and project-wide Voice From Content;
- hashes reference-audio content and includes every advanced voice input in deterministic cache identity, so changing the sample itself invalidates stale cached speech;
- validates provider capabilities before clone/design/catalog operations and fails closed instead of silently dropping unsupported advanced inputs;
- exposes clone/design/catalog controls only when the selected TTS provider advertises those capabilities, using lazy descriptors so opening Studio does not instantiate a provider;
- adds explicit voice-catalog loading and de-duplicates returned voice names before presenting them in Studio;
- adds configurable Advanced TTS and optional Voice catalog endpoints with `NOLANE_STUDIO_TTS_ADVANCED_ENDPOINT` and `NOLANE_STUDIO_TTS_VOICES_ENDPOINT` automation overrides;
- keeps the standard OpenAI-compatible TTS base/model path synthesize-only and uses the generic advanced HTTP adapter only when explicitly configured, avoiding a fabricated vendor-specific clone API;
- preserves v0.5 generated images, v0.4 AI Analyze, v0.3 Canvas/Object and the existing final render/export contracts;
- keeps creator workflows free of Pro/license/login gates and does not require a local speech model merely to open the application.

Forensic boundary:

- recovered evidence defines clone/design/list-voices capabilities but not a single universal network schema, so provider-specific voice internals remain behind explicit adapters;
- provider-owned saved voice storage is not recreated as a mandatory local runtime; optional voice discovery is the rebuild boundary;
- exact readable-label post-processing and non-empty multi-track entry schemas remain separate evidence-limited parity work.

Release integrity:

- v0.5.0 remains the Generated Image Workflow baseline;
- v0.6.0 is the first release containing end-to-end capability-aware advanced voice service/UI/provider configuration;
- pre-release exact-head verification reached 693 passing tests on Linux and Windows plus NUI evidence, portable executable smoke testing, installer validation, checksums and artifact upload;
- the Windows workflow publishes versioned assets only from `main`.
