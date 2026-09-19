# Forensic parity scope — v0.11.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. The recovered EXE and recovered design evidence remain behavioral authorities: useful creator workflows and state contracts are restored while legacy branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority of this parity slice

- Recovered AI behavior explicitly states that exact readable labels are overlaid deterministically after image generation rather than delegated to the image model.
- The existing hardened whiteboard prompt already tells image providers not to render long text and to leave readable labels to deterministic post-processing.
- AI Analyze already persists grounded objects with exact `label` text, exact spoken `phrase`, normalized `box` coordinates and timing. v0.11 uses only the unambiguous `label + box` subset for visual label materialization.
- Each requested label becomes a normal persisted Canvas `text` object. Existing Canvas and final-render paths therefore remain authoritative; no second hidden raster pipeline is introduced.
- Normalized boxes map directly onto the 1280×720 recovered reference canvas. The text itself is exact; typography is a neutral rebuild default.
- Label synchronization is idempotent by analysis slot, preserves user-created text and every non-owned layer, and deletes only stale objects marked with the v0.11 Nolane readable-label owner contract.
- The whole requested label set is validated before label mutation. Non-mapping analysis state, blank labels, malformed/non-finite/out-of-range boxes and non-positive-area boxes fail closed.
- AI Analyze materializes labels after the visual exists; cache hits for the same generated image resynchronize idempotently.
- A provider call that produces a new generated image invalidates prior `ai_analysis` grounding and service-owned readable labels because normalized boxes are derived from the previous image bytes. Failed generation leaves the prior derived state untouched.
- Non-whiteboard visual styles are outside this automatic overlay slice and are left unchanged.
- Existing v0.3 Canvas/Object through v0.10 Scene Clip Edit authority remains unchanged.

## Evidence-limited boundaries

- v0.11 does not claim source-exact legacy font family, text decoration, callout shapes, collision avoidance or any unrecovered label-layout nuance beyond grounded-box placement.
- Arbitrary custom draw paths and source-exact non-default hand rendering remain separate parity work.
- Background-removal behavior and object effect/sound routing remain evidence-limited.
- Arbitrary legacy multi-track clip splitting/cutting and non-empty `clips`, `videoClips`, `audioClips` and `batch_voice_segments` entry schemas remain fail-closed.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, OCR dependency or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- Subsequent parity work must be supported by recovered evidence or be labeled explicitly as new product design.
