# Nolane Studio v0.5.0

Generated Image Workflow forensic-parity release.

Highlights:

- restores the recovered optional image-generation stage through a configurable, lazy OpenAI-compatible image provider;
- exposes Image endpoint/model settings alongside Analysis, Vision, STT and TTS, with `NOLANE_STUDIO_IMAGE_BASE_URL` and `NOLANE_STUDIO_IMAGE_MODEL` environment overrides;
- uses the existing deterministic prompt hardening so whiteboard generation requests pure-white, simple drawn-explainer visuals and does not delegate long readable text to diffusion;
- restores per-scene **Generate image** and project-wide **Generate All Images** actions without loading a local image model at startup;
- caches generated visuals by hardened prompt, provider and requested size, so identical inputs reuse the scene artifact while meaningful prompt/config changes regenerate it;
- stores one stable `image-{scene_id}` media slot per scene and persists image path/provider/size/cache metadata for AI Analyze and editor reuse;
- binds generated visuals into the v0.3 Canvas/Object Engine as persisted background image objects, so the same generated visual reaches Canvas and the authoritative scene render plan instead of living only in metadata;
- protects manually-authored image layers from stale generated-image metadata and refuses ambiguous generated-object state rather than silently overwriting user work;
- preserves v0.4 AI Analyze + Voice From Content behavior and all prior project/render/export authority.

Forensic boundary:

- the recovered evidence says exact readable labels are added deterministically after image generation, but the old label-source/layout contract is not yet recovered strongly enough to recreate automatically without guessing; v0.5 therefore does not invent that schema or extraction rule;
- multi-track `clips` / `videoClips` / `audioClips` entry schemas likewise remain fail-closed until stronger EXE evidence is available.

Release integrity:

- v0.4.0 remains the AI Analyze + Voice From Content baseline;
- v0.5.0 is the first release containing the restored generated-image provider/service/UI/Canvas workflow;
- the Windows workflow tests, renders NUI evidence, builds/smoke-tests portable and installed executables, packages checksums and publishes versioned assets only from `main`.
