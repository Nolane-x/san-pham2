# Forensic parity scope

This branch restores recovered DrawAI 1.2.17 behavior without inventing a new product architecture.

Immediate parity slice:

- API-first AI Analyze preserving the recovered STT -> vision grounding -> local deterministic timing pipeline.
- Voice From Content and per-scene TTS backed by configurable providers.
- No FREE/PRO naming, paywall, license checks, mandatory auth, Ollama or OmniVoice runtime.
- Existing project, scene, media, timeline and render behavior remains authoritative.

Subsequent parity work must only restore behavior evidenced by the recovered executable unless explicitly requested by the user.
