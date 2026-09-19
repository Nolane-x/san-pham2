# Forensic parity scope — v0.4.0

This branch restores behavior recovered from the legacy Windows creator application without inventing a new product architecture or reintroducing its branding, trade dress, licensing, account, telemetry, updater, or heavyweight-runtime coupling.

## Authority of this parity slice

- API-first **AI Analyze** preserves the recovered pipeline: timestamped STT determines **when**, vision grounding determines **what/where**, and deterministic local logic produces scene object timing/metadata.
- AI Analyze cache identity is content-based and deterministic; unchanged image/audio/language/target-phrase inputs may be reused, while meaningful input changes invalidate the cache.
- **Generate voice** and **Voice From Content** are provider operations backed by configurable TTS capabilities and stable per-scene cached media slots.
- Studio receives the live lazy provider registry. Providers are instantiated only when their capability is actually requested.
- The Providers UI exposes Analysis, Vision, STT and TTS endpoint/model configuration. Environment variables remain valid automation overrides.
- Image/audio/video attachment is explicit persisted scene metadata. AI Analyze requires real scene image and narration-audio inputs instead of silently fabricating them.
- The v0.3.0 project/scene/media/Canvas/Object/timeline/render/export state remains authoritative and is not replaced by AI-specific storage.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, or model-weight download merely to open/use the editor.
- No provider-specific SDK is required for the OpenAI-compatible HTTP paths in this slice.
- Subsequent forensic parity work must restore behavior supported by recovered evidence unless the product scope is explicitly changed.
