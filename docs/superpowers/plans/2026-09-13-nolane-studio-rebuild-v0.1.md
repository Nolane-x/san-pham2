# Nolane Studio Rebuild v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a testable Nolane Studio rebuild foundation that preserves recovered project/scene/render contracts while replacing Pro/local-AI coupling with capability-based providers.

**Architecture:** Pure Python core packages isolate domain, SQLite storage, scene planning, TTS/AI provider adapters and FFmpeg render planning from the optional PySide6 UI. Every external runtime is injected or lazy. The v0.1 core is fully testable offline.

**Tech Stack:** Python 3.10+, stdlib dataclasses/sqlite3/urllib/subprocess, pytest for development tests, optional PySide6 for UI.

**Spec:** `docs/superpowers/specs/2026-09-13-nolane-studio-rebuild-design.md`

## Global Constraints

- Windows desktop target with 8 GB RAM.
- No mandatory Ollama, OmniVoice, ComfyUI, model weights, API key, telemetry or license service.
- No FREE/PRO feature gates.
- SQLite local project store.
- FFmpeg media composition.
- 24 fps and 1280x720 reference defaults unless a project overrides them.
- Scene transitions are additive and never shorten drawing/video clips.
- Heavy providers are lazy and optional.
- Tests must run offline.

---

### Task 1: Package skeleton and domain contracts

**Files:**
- Create: `pyproject.toml`
- Create: `src/nolane_studio/domain/models.py`
- Create: `src/nolane_studio/domain/__init__.py`
- Test: `tests/domain/test_models.py`

**Interfaces:**
- Produces: `Scene`, `ProjectSpec`, `RenderConfig`, `TransitionSpec`, `VoiceRequest` dataclasses and validation helpers.

- [ ] Write failing tests for default canvas/fps, duration validation and transition duration bounds.
- [ ] Run focused tests and verify RED.
- [ ] Implement minimal immutable/value-like domain models.
- [ ] Run focused tests and verify GREEN.

### Task 2: SQLite compatibility store

**Files:**
- Create: `src/nolane_studio/storage/schema.py`
- Create: `src/nolane_studio/storage/store.py`
- Create: `src/nolane_studio/storage/__init__.py`
- Test: `tests/storage/test_store.py`

**Interfaces:**
- Consumes: domain project/timeline values.
- Produces: `ProjectStore(db_path)`, `initialize()`, `create_project()`, `add_item()`, `get_project()`, `save_timeline()`, `load_timeline()`.

- [ ] Write failing temporary-SQLite tests for idempotent schema and CRUD/timeline round-trip.
- [ ] Verify RED.
- [ ] Implement recovered compatibility tables and transactional repository operations.
- [ ] Verify GREEN.

### Task 3: Deterministic scene planner and prompt hardening

**Files:**
- Create: `src/nolane_studio/ai/scenes.py`
- Create: `src/nolane_studio/ai/prompts.py`
- Create: `src/nolane_studio/ai/__init__.py`
- Test: `tests/ai/test_scenes.py`
- Test: `tests/ai/test_prompts.py`

**Interfaces:**
- Produces: `split_script_into_scenes(text, min_words=30, max_words=50)` and `build_image_prompt(scene, style, additional_prompt='')`.

- [ ] Write failing tests for deterministic sentence grouping, blank input and whiteboard hardening.
- [ ] Verify RED.
- [ ] Implement local scaffold planner and prompt builder.
- [ ] Verify GREEN.

### Task 4: Capability-based provider registries

**Files:**
- Create: `src/nolane_studio/providers/base.py`
- Create: `src/nolane_studio/providers/registry.py`
- Create: `src/nolane_studio/providers/http.py`
- Create: `src/nolane_studio/providers/__init__.py`
- Test: `tests/providers/test_registry.py`
- Test: `tests/providers/test_http.py`

**Interfaces:**
- Produces: `ProviderRegistry`, `ProviderCapabilities`, `AnalysisProvider`, `TTSProvider`, `OpenAICompatibleAnalysisProvider`, `OpenAICompatibleTTSProvider`, `GenericHttpTTSProvider`.

- [ ] Write failing tests for lazy registration/capability selection and HTTP request serialization using a fake transport.
- [ ] Verify RED.
- [ ] Implement provider protocols/registry and transport-injected HTTP adapters.
- [ ] Verify GREEN.

### Task 5: Render config normalization and timeline math

**Files:**
- Create: `src/nolane_studio/render/config.py`
- Create: `src/nolane_studio/render/timeline.py`
- Create: `src/nolane_studio/render/__init__.py`
- Test: `tests/render/test_config.py`
- Test: `tests/render/test_timeline.py`

**Interfaces:**
- Produces: `normalize_render_config(raw)`, `final_duration(clips, transitions)`, `build_transition_gaps(...)`.

- [ ] Write failing tests for recovered defaults/clamps, unknown-field preservation and additive transition math.
- [ ] Verify RED.
- [ ] Implement pure normalization/timeline functions.
- [ ] Verify GREEN.

### Task 6: FFmpeg command planning

**Files:**
- Create: `src/nolane_studio/render/ffmpeg.py`
- Test: `tests/render/test_ffmpeg.py`

**Interfaces:**
- Produces: `FFmpegPaths`, `build_normalize_segment_command(...)`, `build_concat_command(...)`, `build_global_audio_mux_command(...)`, `SubprocessRunner`.

- [ ] Write failing exact-argument tests for segment normalization, concat and global voice mux.
- [ ] Verify RED.
- [ ] Implement deterministic command builders and injected runner.
- [ ] Verify GREEN.

### Task 7: Application service and CLI

**Files:**
- Create: `src/nolane_studio/app.py`
- Create: `src/nolane_studio/cli.py`
- Create: `src/nolane_studio/__init__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces CLI commands `init-db`, `analyze`, `providers`, `render-plan`.

- [ ] Write failing CLI tests using temporary directories and captured stdout.
- [ ] Verify RED.
- [ ] Implement application composition and CLI.
- [ ] Verify GREEN.

### Task 8: Optional PySide6 shell and release verification

**Files:**
- Create: `src/nolane_studio/ui/main_window.py`
- Create: `src/nolane_studio/ui/__init__.py`
- Create: `README.md`
- Create: `FORENSIC_ARCHITECTURE.md`
- Test: `tests/ui/test_import_guard.py`

**Interfaces:**
- Produces: `nolane_studio.ui.run()` with a clear missing-extra error when PySide6 is absent.

- [ ] Write failing import-guard test that does not require PySide6.
- [ ] Verify RED.
- [ ] Implement lazy UI import and a minimal sidebar/workspace shell.
- [ ] Document recovered architecture, provider setup and next parity milestones.
- [ ] Run the entire test suite and package checks.
