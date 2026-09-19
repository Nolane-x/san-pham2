# Forensic parity scope — v0.5.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. The recovered EXE remains a behavioral oracle: useful workflows and state contracts are restored, while legacy branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling stay outside the creator path.

## Authority of this parity slice

- The recovered pipeline explicitly contains **optional image generation** between validated scene prompts and the visual editor.
- Image generation is a lazy provider capability. Opening Nolane Studio does not construct or download a local image model.
- A generated scene visual is keyed deterministically by hardened prompt, provider and requested size.
- Each scene owns a stable generated media slot `image-{scene_id}`; cache hits reuse that asset and prompt/provider/size changes invalidate it.
- The generated visual is also represented by one persisted Canvas image object at the back of the scene stack, making the Canvas/Object Engine and render plan authoritative rather than keeping generated files in side metadata only.
- Generated-object ownership is explicit. Stale metadata must never hijack or overwrite a manual image layer.
- Studio exposes **Generate image** and **Generate All Images**; Providers exposes Image endpoint/model configuration and environment overrides.
- Generated images populate the scene image metadata already consumed by v0.4 AI Analyze.
- Existing v0.3 Canvas/Object and v0.4 AI Analyze/Voice storage/render/export contracts remain authoritative.

## Evidence-limited boundaries

- Recovered documentation states that exact readable labels are overlaid deterministically after image generation, but the source and layout schema for those labels is not sufficiently recovered in the current evidence. This branch does not invent one.
- Non-empty legacy multi-track `clips`, `videoClips` and `audioClips` entries remain fail-closed because their per-entry schema is not yet sufficiently recovered.
- These boundaries are explicit remaining forensic work, not silent feature substitutions.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, or model-weight download merely to open/use the editor.
- No provider-specific SDK is required for the OpenAI-compatible HTTP paths in this slice.
- Subsequent parity work must be supported by recovered evidence or be labeled explicitly as new product design.
