# Nolane Studio

**Nolane Studio** is a local-first Windows creator workspace for turning scripts, images, narration audio and video into structured visual stories without forcing a heavy local AI stack onto the machine.

The product is a clean rebuild based on behavior recovered from a legacy Windows creator application. Its identity, branding, UI, packaging and source code are new. No legacy logos, product artwork, paywall, license gate, telemetry gate, updater gate, mandatory Ollama runtime or mandatory local speech model are carried forward.

## What works today

- **Create** — paste a script and generate a deterministic local scene plan before any provider is contacted.
- **Studio** — creator workspace with Scenes, Canvas, Inspector and Timeline regions.
- **Media import and attachment** — images, narration audio and video are copied into the local project workspace and can be attached explicitly to scenes.
- **Generated images** — per-scene Generate image and project-wide Generate All Images use hardened scene prompts, stable cached media slots and persisted background Canvas objects that flow into the authoritative render plan.
- **AI Analyze** — configured STT supplies narration timing, configured vision supplies grounded object identity/location, and deterministic local logic joins the result into scene metadata with content-based caching.
- **Readable label overlays** — grounded AI Analyze labels are materialized as deterministic persisted Canvas text layers; service-owned slots update idempotently while manual text remains untouched, and a genuinely regenerated image invalidates stale grounding/labels until it is analyzed again.
- **Voice generation** — per-scene Generate voice and project-wide Voice From Content use capability-driven providers with stable cached scene media slots; providers may additionally expose reference-audio cloning, designed voices and voice discovery.
- **Scene narration export** — persisted per-scene narration is preflighted before rendering and normalized into each final scene clip; source-video audio is mixed with narration while silent visual scenes use narration directly.
- **Scene transitions** — edit the selected scene → next-scene transition with persisted effect/duration; final export inserts validated additive transition segments without shortening scene clips.
- **Object timing** — in Custom mode, edit per-layer pause/draw/push timing directly in Studio; missing overrides use the render engine's deterministic fixed-share fallback and duplicated scenes remap timing to copied object IDs.
- **Scene clip edits** — trim the selected scene's source window and adjust playback speed through explicit persisted `sceneEdits`; final export applies the same edit window to visuals and scene narration while keeping additive transitions independent.
- **Selected-scene preview** — the Preview control renders only the selected scene through the authoritative Canvas/video/whiteboard pipeline, includes persisted narration, honors scene trim/speed, and intentionally excludes project ordering/transitions.
- **Lossless scene reset** — the recovered Inspector Reset scene control restores canonical render/motion defaults while preserving scene text, layers, media ownership, narration and analysis metadata.
- **Apply drawing settings to all scenes** — scene-wide drawing controls can be propagated project-wide in one storage transaction while each target scene keeps its own object timing, object-addressed effects/sound state, draw paths, camera/image-motion state and unknown target extras.
- **Scene lifecycle timeline integrity** — Add, Duplicate, Move and Delete preflight persisted timeline state, synchronize `mediaOrder` to authoritative scene order, drop transitions that cease to be adjacent, prune deleted-scene edits, clone a duplicated scene's `sceneEdits` window, and fail closed when opaque legacy tracks are populated.
- **Whiteboard outro** — expose the recovered additive post-hold scene exit in Studio; verified whiteboard scenes can enable a leftward outro with persisted duration, while unknown legacy directions stay visible/preserved and unsupported rather than being silently rewritten.
- **Object push activation integrity** — saving/resetting per-object Push timing now synchronizes the renderer's recovered scene-level push-enable contract from positive timing on visible objects only, so UI-authored push is exportable while hidden/stale timing cannot spuriously enable it.
- **Windows video export** — media is normalized sequentially with FFmpeg and exported as H.264/AAC MP4 without loading all frames into RAM.
- **Library** — durable local SQLite projects with no expiry timer.
- **Providers** — configurable Analysis, Image, Vision, STT and TTS endpoints plus an optional advanced voice-wrapper/catalog pair; environment variables can override local settings for automation.
- **Low-memory startup** — opening the app does not start a local LLM, TTS model, speech model or image model.

## Product shape

```text
Create
  script -> local scene scaffold -> optional provider enrichment

Studio
  Scenes | Canvas | Inspector
  ---------------------------
            Timeline

Library
  durable local projects + imported media

Providers
  analysis API / image API / vision API / STT API / TTS API
```

## Windows release

The Windows workflow produces three release assets:

- `NolaneStudio.exe` — portable one-file build.
- `NolaneStudio-Windows-x64-<version>.zip` — portable ZIP.
- `NolaneStudio-Setup-<version>.exe` — per-user installer, no administrator privileges required.

`SHA256SUMS.txt` is published alongside the release assets. FFmpeg is bundled in the Windows build through `imageio-ffmpeg`, so a separate FFmpeg installation is not required for the supported export path.

## Development

Core tests do not require Qt, network access or API keys:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

Desktop UI:

```bash
python -m pip install -e '.[ui]'
python -m nolane_studio
```

CLI examples:

```bash
nolane-studio init-db ./studio.db
nolane-studio analyze "Your script" --min-words 30 --max-words 50 --style whiteboard
nolane-studio render-plan --clip a:8 --clip b:7 --transition a:b:fade:0.6
nolane-studio providers
```

## Provider configuration

Settings can be entered from the Providers screen. Automation can override them with:

```text
NOLANE_STUDIO_AI_BASE_URL=https://provider.example/v1
NOLANE_STUDIO_AI_MODEL=analysis-model
NOLANE_STUDIO_IMAGE_BASE_URL=https://provider.example/v1
NOLANE_STUDIO_IMAGE_MODEL=image-model
NOLANE_STUDIO_VISION_BASE_URL=https://provider.example/v1
NOLANE_STUDIO_VISION_MODEL=vision-model
NOLANE_STUDIO_STT_BASE_URL=https://provider.example/v1
NOLANE_STUDIO_STT_MODEL=transcription-model
NOLANE_STUDIO_TTS_BASE_URL=https://provider.example/v1
NOLANE_STUDIO_TTS_MODEL=speech-model
NOLANE_STUDIO_TTS_ADVANCED_ENDPOINT=https://voice-wrapper.example/tts
NOLANE_STUDIO_TTS_VOICES_ENDPOINT=https://voice-wrapper.example/voices
NOLANE_STUDIO_API_KEY=...
```

The API key is intentionally **not** persisted in `settings.json`.

The normal TTS base URL/model pair is a synthesize-only OpenAI-compatible path. When `NOLANE_STUDIO_TTS_ADVANCED_ENDPOINT` (or the matching Providers-screen field) is configured, Nolane Studio uses the explicit generic advanced-voice JSON adapter instead and advertises clone/design capabilities. `NOLANE_STUDIO_TTS_VOICES_ENDPOINT` is optional; when present it enables provider voice discovery. This keeps vendor-specific clone/design wire protocols outside the product core instead of pretending they are standardized.

## Architecture

- `nolane_studio.domain` — pure scene/project/render/voice contracts.
- `nolane_studio.storage` — SQLite project, media and timeline state.
- `nolane_studio.ai` — deterministic scene planning and prompt hardening.
- `nolane_studio.providers` — lazy Analysis/Image/Vision/STT/TTS providers.
- `nolane_studio.render` — FFmpeg command planning and low-memory mixed-media export.
- `nolane_studio.ui` — PySide6 desktop workspace.

See [`RECOVERED_ARCHITECTURE.md`](RECOVERED_ARCHITECTURE.md) for the behavioral reconstruction map and [`docs/NUI-DESIGN-EVIDENCE.md`](docs/NUI-DESIGN-EVIDENCE.md) for the high-ambition UI route and evidence ledger.

## Current boundary

This release includes the recovered generated-image workflow, capability-driven advanced voice workflow, persisted additive scene-transition editor/export path, per-scene narration in authoritative final export, direct editing of the recovered per-object pause/draw/push whiteboard timing contract, scene-level trim/start-end/speed editing through the rebuild-owned `sceneEdits` contract, deterministic readable-label materialization from AI Analyze grounded labels/boxes, selected-scene preview through the same authoritative render path, bounded lossless scene render reset, project-wide propagation of scene-wide drawing controls without copying object-addressed state between scenes, fail-closed scene-lifecycle reconciliation for supported persisted timeline state, the recovered additive whiteboard outro with the verified leftward exit direction, and visible-object push activation synchronized with the authoritative whiteboard timing/export contract. It does **not** yet claim parity for unrecovered whiteboard outro directions beyond `left`, unrecovered object-push directions/modes beyond the existing automatic `from_left` renderer contract, arbitrary custom draw paths, source-exact non-default hand/background-removal behavior, arbitrary legacy multi-track clip splitting/cutting or decoded non-empty `clips` / `videoClips` / `audioClips` entry schemas, object-SFX semantics, or source-exact legacy label typography/decoration beyond the recovered grounded-box placement authority. Those remain subsequent parity layers rather than being hidden behind a false “finished” claim.
