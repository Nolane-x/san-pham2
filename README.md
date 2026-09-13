# Nolane Studio

**Nolane Studio** is a local-first Windows creator workspace for turning scripts, images and video into structured visual stories without forcing a heavy local AI stack onto the machine.

The product is a clean rebuild based on behavior recovered from a legacy Windows creator application. Its identity, branding, UI, packaging and source code are new. No legacy logos, product artwork, paywall, license gate, telemetry gate, updater gate, mandatory Ollama runtime or mandatory local speech model are carried forward.

## What works today

- **Create** — paste a script and generate a deterministic local scene plan before any provider is contacted.
- **Studio** — creator workspace with Scenes, Canvas, Inspector and Timeline regions.
- **Media import** — images and video are copied into the local project workspace.
- **Windows video export** — media is normalized sequentially with FFmpeg and exported as H.264/AAC MP4 without loading all frames into RAM.
- **Library** — durable local SQLite projects with no expiry timer.
- **Providers** — configurable analysis and TTS endpoints; environment variables can override local settings for automation.
- **Low-memory startup** — opening the app does not start a local LLM, TTS model or image model.
- **Voice architecture** — capability-based provider contracts support synthesis today and leave room for cloning/design/list-voices adapters without binding the product to one engine.

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
  analysis API / TTS API / optional local command adapters
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
NOLANE_STUDIO_TTS_BASE_URL=https://provider.example/v1
NOLANE_STUDIO_TTS_MODEL=speech-model
NOLANE_STUDIO_API_KEY=...
```

The API key is intentionally **not** persisted in `settings.json`.

## Architecture

- `nolane_studio.domain` — pure scene/project/render/voice contracts.
- `nolane_studio.storage` — SQLite project, media and timeline state.
- `nolane_studio.ai` — deterministic scene planning and prompt hardening.
- `nolane_studio.providers` — lazy analysis/TTS providers.
- `nolane_studio.render` — FFmpeg command planning and low-memory mixed-media export.
- `nolane_studio.ui` — PySide6 desktop workspace.

See [`RECOVERED_ARCHITECTURE.md`](RECOVERED_ARCHITECTURE.md) for the behavioral reconstruction map and [`docs/NUI-DESIGN-EVIDENCE.md`](docs/NUI-DESIGN-EVIDENCE.md) for the high-ambition UI route and evidence ledger.

## Current boundary

This release is a strong native rebuild foundation with a working creator shell, local project/media flow and mixed image/video export. It does **not** yet claim parity for every advanced legacy drawing algorithm, object-level whiteboard animation, multi-track trimming/cutting, transition editor, generated-image workflow or complete voice-generation UX. Those are tracked as subsequent parity layers rather than being hidden behind a false “finished” claim.
