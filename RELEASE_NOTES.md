# Nolane Studio v0.4.0

AI Analyze + Voice From Content forensic-parity release.

Highlights:

- restores the recovered AI Analyze workflow through replaceable API-first providers: timestamped STT determines when narration phrases occur, vision grounding determines what/where visible objects are, and deterministic local logic joins the two;
- caches AI Analyze results by scene image/audio/language/target-phrase content so unchanged inputs reuse deterministic analysis while meaningful input changes invalidate the cache;
- persists AI analysis under scene metadata without replacing unrelated Canvas/Object Engine metadata;
- restores per-scene Generate voice and project-wide Voice From Content using configurable TTS providers and stable cached `voice-{scene_id}` media slots;
- exposes Analysis, Vision, STT and TTS endpoint/model settings in the Providers UI while retaining environment-variable overrides for automation;
- restores audio import and explicit scene media attachment so AI Analyze can consume attached/generated image and narration audio end-to-end;
- injects the live lazy ProviderRegistry into Studio, so merely opening the application does not load heavyweight AI engines;
- preserves the v0.3.0 Canvas/Object Engine as the authoritative project, scene, layer, timing and final-export substrate;
- keeps the Windows-first, local-project workflow free from Pro/paywall/license/login gates and does not require Ollama, OmniVoice or other heavyweight local AI runtimes;
- removes the stale hard-coded UI version label so release identity is no longer allowed to drift from package/release metadata.

Release integrity:

- v0.3.0 remains the persistent Canvas/Object Engine parity baseline;
- v0.4.0 is the first release containing the restored AI Analyze + Voice From Content application workflow;
- the release workflow packages and smoke-tests the exact PR/main commit before publishing versioned Windows artifacts and refuses to overwrite an existing version tag that belongs to a different commit.
