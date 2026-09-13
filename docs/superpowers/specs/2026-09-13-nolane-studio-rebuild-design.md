# Nolane Studio Rebuild v0.1 — Design Specification

## 1. Purpose

Build Nolane Studio from statically recovered behavior of a legacy Windows creator application while removing obsolete licensing/paywall coupling and heavy local-AI assumptions. The rebuild must preserve the creator workflows that matter: Manual Whiteboard, AI Project, Visual Editor, Voice From Content, and deterministic video export.

This is a behavior-driven clean rebuild. The recovered installer and payload are an oracle for contracts and data flow, not a requirement to execute the original binary.

## 2. Forensic baseline

The unnamed reference application is version 1.2.17 on Windows x86_64 and used Inno Setup 6.7.0. The packaged app is Python 3.10/PyInstaller with PySide6/Qt6. Static recovery found four major product zones:

- `native_v2`: native PySide6 shell/editor and parity stages.
- `desktop_core`: project persistence, editor routes, render client/runtime, update/auth/telemetry integrations.
- `ai_pipeline`: deterministic scene splitting, prompt construction, ComfyUI/Ollama/OmniVoice orchestration, project store.
- `server_render_engine`: final render/export pipeline, source-video integration and additive transitions.

Recovered render behavior establishes the following important contracts:

1. Render item configuration is normalized before invoking a renderer.
2. A scene renderer produces a base video; FFmpeg then normalizes the segment to the project canvas.
3. Default reference canvas is 1280x720 at 24 fps.
4. Segment export is separate from final export.
5. Final export can combine rendered image segments and source video clips.
6. Scene transitions are additive in duration and never shorten or overlap drawing segments.
7. Final audio can include global/per-image voice, source-video audio, and object SFX.
8. A final validation pass occurs before the video is registered as complete.

Recovered AI behavior establishes:

1. Script splitting has a deterministic local pre-pass.
2. AI enrichment is optional and works on bounded scene batches rather than receiving responsibility for all structural splitting.
3. Whiteboard prompts are hardened to pure-white/simple drawn-explainer output.
4. Exact readable labels are overlaid deterministically after image generation instead of asking diffusion to render long text.

Recovered TTS behavior establishes:

1. Voice generation is logically a provider operation and does not belong inside project storage or rendering.
2. The old OmniVoice implementation supported saved voices, cloning and designed voices, but its heavyweight runtime is not a required architectural dependency.
3. Voice generation supports per-scene output plus a batch “Voice From Content” workflow.

## 3. Product constraints

- Primary target: Windows desktop machines with 8 GB RAM.
- No mandatory Ollama install.
- No mandatory local LLM.
- No mandatory OmniVoice runtime.
- No FREE/PRO feature gates.
- No license verification in creator or render paths.
- No mandatory telemetry.
- No mandatory self-updater in core.
- API providers are first-class and configurable.
- Local providers are lazy, optional adapters.
- Core workflows must remain usable offline when their chosen providers are local/offline.
- SQLite remains the authoritative local project store.
- FFmpeg is the authoritative media composition layer.
- Heavy engines must never be imported or started merely to open the application.

## 4. Architecture

The rebuild is split into six packages with strict boundaries.

### 4.1 `nolane_studio.domain`

Pure data contracts: scenes, clips, render settings, voice jobs, project metadata and status values. It has no Qt, database, network or subprocess dependencies.

### 4.2 `nolane_studio.storage`

SQLite bootstrap and repository operations. It preserves compatible table/column concepts from the recovered application: `batch_projects`, `batch_items`, `batch_videos`, `visual_editor_media`, `visual_editor_timeline_state`, and `user_project_library`.

Authentication columns may remain nullable for migration compatibility, but access control is not enforced by the new local product.

### 4.3 `nolane_studio.ai`

Contains deterministic scene splitting and prompt hardening plus a provider protocol. Local deterministic planning always runs before optional provider enrichment. Provider failures must leave a valid scaffold instead of destroying the project.

### 4.4 `nolane_studio.tts`

Provider registry and adapters. The core contract accepts text, language, voice selection, optional reference audio/text and design instructions, and returns an audio artifact. API providers are the default deployment direction. Local providers are optional and lazily probed.

### 4.5 `nolane_studio.render`

Contains render configuration normalization, duration/timeline math, FFmpeg probing/composition, additive scene transitions, source-video normalization and final export orchestration. It depends on domain/storage interfaces but never on Qt.

### 4.6 `nolane_studio.ui`

PySide6 shell and editor. The UI binds to application services, never directly to SQLite, network APIs, or FFmpeg. The first rebuild stage may provide a functional shell and progressively restore high-density editing behavior from the recovered UI oracle.

## 5. Data flow

### Manual Whiteboard

`import images -> create project/items -> edit per-item/global render settings -> RenderPlan -> scene renderer -> normalized segment -> timeline -> final export`

### AI Project

`source text -> deterministic scene split -> optional AI enrichment -> prompt hardening -> image provider -> TTS provider -> project media -> Visual Editor -> final export`

### Voice From Content

`lines/segments -> language/voice settings -> TTS provider -> per-segment audio -> preview/batch attach`

### Visual Editor

`media library -> clips/tracks -> timeline state -> render/export service -> final MP4`

## 6. TTS policy

The rebuild must not encode “OmniVoice” as the product architecture. It exposes capabilities instead:

- `synthesize`: text-to-speech.
- `clone`: reference-based voice cloning when supported.
- `design`: text-described voice design when supported.
- `list_voices`: optional provider voice discovery.

Providers report capabilities at runtime. The UI hides unsupported controls instead of branching on provider names.

Initial adapters should include:

- OpenAI-compatible HTTP TTS adapter.
- Generic HTTP JSON/binary adapter for self-hosted/vendor APIs.
- Command adapter for optional local engines (Piper/V-TTS/VieNeu wrappers can target it without entering core).

No model weights ship in the base package.

## 7. AI provider policy

`ScenePlanner` always produces deterministic scaffolds. An `AnalysisProvider` can enrich them. The provider interface uses structured scene objects; malformed provider output is rejected and the scaffold remains usable.

The first provider adapters are:

- OpenAI-compatible chat/completions-style JSON API.
- Generic HTTP adapter hook.
- No built-in Ollama dependency; an Ollama adapter can be optional because the original used it.

## 8. Render contracts

### Item normalization

Normalize and validate:

- `style`: whiteboard/color_reveal.
- `visual_mode`: drawing/camera_motion.
- reveal/hold duration.
- brush mode.
- drawing points/object order.
- large-object push.
- object effect and SFX settings.
- camera settings.
- object timing settings.
- outro.
- hand style.
- background removal.

Unknown fields are preserved under `extras` where practical so old project data can round-trip.

### Timeline math

A final timeline duration is:

`sum(visual clip durations) + sum(additive transition durations)`

Transitions never subtract source duration. Source video can coexist with image segments, but unsupported combinations must fail with an explicit validation error rather than silently changing timing.

### FFmpeg

Command construction and execution are separated. Command builders are deterministic and unit-testable without FFmpeg. Runtime probing/execution is injected behind a runner interface.

## 9. Storage compatibility

The new schema creates a compatibility-oriented superset of the recovered tables. Schema migrations are idempotent. Projects are never automatically deleted due to old cleanup timers.

All project mutations occur transactionally. Render status updates use explicit state transitions and preserve errors for UI diagnostics.

## 10. Error handling

- Provider timeout: mark provider task failed, preserve scaffold/media state, allow retry.
- TTS failure: fail the scene voice artifact only; do not corrupt the project.
- FFmpeg failure: capture command exit status/stderr and mark the active render operation failed.
- Missing media: validation error before render starts.
- Cancellation: cooperative cancellation token checked between expensive stages and forwarded to provider/subprocess adapters where supported.
- Database error: rollback transaction and surface a typed storage error.

## 11. RAM discipline

- No heavyweight AI imports at process startup.
- Media decoding is streaming/chunked where possible.
- Only one heavy local provider process is warm by default.
- Optional local TTS workers use idle shutdown.
- Image generation remains external/provider-based unless the user explicitly configures ComfyUI.
- Thumbnail/preview caches are bounded.

## 12. UI direction

The initial UI should preserve the recovered mental model rather than the old pixel layout:

- Global shell: Create, Studio, Library, Providers.
- Create flow: source content -> local scene map -> Studio.
- Studio: scenes/media rail, canvas, inspector, timeline, preview/export controls.
- Provider settings are grouped by capability rather than legacy product names.
- No PRO badges or upgrade gates.

## 13. Testing strategy

- Domain/timeline math: pure unit tests.
- Storage: temporary SQLite integration tests.
- Scene planning/prompt hardening: deterministic golden tests.
- Provider adapters: local HTTP test server/fakes; no external API required in CI.
- FFmpeg command builders: exact argument tests.
- FFmpeg runtime: optional integration tests when binary exists.
- UI: smoke tests kept separate from core.

## 14. Definition of done for v0.1 foundation

v0.1 foundation is complete when:

1. A local project DB can be initialized and CRUD a project/items/timeline.
2. Source text can be deterministically split into scenes with hardened prompts.
3. AI/TTS provider registries can select capability-compatible providers without importing heavy runtimes.
4. Render config normalization and additive transition timeline math match recovered behavior.
5. FFmpeg export command planning is deterministic and validated.
6. A CLI can exercise database initialization, scene analysis, provider inspection and render-plan inspection.
7. All tests pass without network access, API keys, Ollama, OmniVoice, ComfyUI, or PySide6.
8. An optional PySide6 shell can start when the UI extra is installed.

This foundation intentionally does not claim full renderer or editor parity yet. It creates the stable contracts on which those layers can be restored without repeating the architectural coupling of the original application.
