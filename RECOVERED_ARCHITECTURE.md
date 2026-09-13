# Recovered Architecture — Behavioral Map

## Purpose

A legacy Windows creator application (v1.2.17) was inspected statically to recover product behavior and data-flow contracts. Its name, artwork and trade dress are intentionally not carried into Nolane Studio.

The reference package used Inno Setup 6.7.0 and contained a Python 3.10 / PyInstaller / PySide6 application. Static recovery exposed native-editor, desktop-core, AI-pipeline and render-engine layers. The reference binary is an oracle for behavior only; it is not shipped or required at runtime.

## Recovered product topology

### Native desktop/editor layer

The native layer covered project lifecycle, AI-assisted project preparation, voice-from-content, runtime settings and a dense visual editor with media, preview, properties, timeline, cut/transport and render controls.

### Desktop core

The desktop core owned durable project persistence, media/timeline state and render orchestration. Authentication, telemetry and updater integrations existed in the reference app but are deliberately outside Nolane Studio's creator path.

### AI pipeline

The useful architectural pattern was:

```text
script
  -> deterministic local scene scaffold
  -> optional provider enrichment
  -> validated visual prompts
  -> optional image generation
  -> optional voice generation
  -> visual editor
```

Nolane Studio preserves deterministic structure-first behavior while replacing fixed local-engine assumptions with provider capabilities.

### Render engine

Recovered render behavior established these contracts:

- normalize item settings before rendering;
- render/normalize scene segments independently;
- default canvas 1280×720 at 24 fps;
- H.264 `yuv420p` normalized output;
- final export may combine image segments and source video;
- scene transitions add timeline duration instead of stealing clip duration;
- voice/source-video audio/object SFX are final composition layers;
- validate final output before registration.

The current rebuild implements deterministic FFmpeg planning plus a low-memory image/video export path. Advanced source drawing renderers remain a later parity layer.

## Storage contracts retained

The compatibility-oriented SQLite schema keeps the useful concepts of:

- batch projects;
- per-scene items;
- rendered videos;
- visual-editor media;
- persisted timeline state;
- local project library.

Legacy identity fields may remain for migration shape, but creator access is not gated by login or licensing.

## Deliberately removed coupling

- free/pro paywall branches;
- license verification in creator/render paths;
- mandatory authentication;
- mandatory telemetry;
- mandatory signed self-update;
- project expiry timers;
- mandatory local LLM downloads;
- mandatory heavyweight local speech runtime.

## Rebuild direction

Nolane Studio keeps the workflows and timing/storage contracts that are useful, but the implementation is organized around small domain, storage, provider, render and UI boundaries. Heavy inference happens only when the user explicitly configures and invokes a provider.
