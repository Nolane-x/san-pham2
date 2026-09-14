# Timeline → Final Export Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for this bounded parity slice. Do not broaden into unsupported audio/SFX/transition decoding.

**Goal:** Make project export consume the unambiguous portion of persisted Visual Editor timeline state instead of silently ignoring it.

**Architecture:** `ProjectSceneExporter` continues rendering authoritative persisted scenes first. After scene clips exist, it loads `visual_editor_timeline_state` and applies only an exact `mediaOrder` permutation whose IDs match the rendered scene clip IDs one-for-one. Any non-empty `clips`, `videoClips`, or `audioClips`, or any ambiguous/incomplete/duplicate/unknown `mediaOrder`, fails closed with an explicit timeline-parity error rather than exporting a video that silently discards editor state.

**Tech Stack:** Python 3.11+, SQLite-backed `ProjectStore`, `ExportClip`, pytest, GitHub Actions Windows packaging gates.

**Spec:** `docs/superpowers/specs/2026-09-13-nolane-studio-rebuild-design.md`; forensic authority additionally records `visual_editor_timeline_state` with clips/video/audio/media-order JSON and the Visual Editor flow `timeline state -> render/export service -> final MP4`.

## Global Constraints

- Behavioral parity only; no new product feature or invented legacy per-clip schema.
- Preserve scene/canvas render authority already established on PR #4.
- `mediaOrder` is consumed only when it is an exact permutation of rendered scene IDs; otherwise fail closed.
- Non-empty `clips`, `videoClips`, and `audioClips` remain unsupported in this slice because recovered evidence does not establish their per-entry schema strongly enough.
- No Pro/paywall/license/auth coupling and no mandatory Ollama/OmniVoice runtime.
- Existing export behavior is unchanged when persisted timeline state is empty.

---

### Task 1: Bind unambiguous persisted timeline ordering to project export

**Files:**
- Modify: `src/nolane_studio/render/project_export.py`
- Test: `tests/render/test_project_scene_exporter.py`

**Interfaces:**
- Consumes: `ProjectStore.load_timeline(project_id) -> {clips, videoClips, audioClips, mediaOrder}` and rendered `ExportClip.clip_id` values.
- Produces: deterministic ordered `list[ExportClip]` or explicit `UnsupportedProjectTimeline` before `MediaExporter.export()`.

- [ ] **Step 1: Write failing tests**

Add contracts proving: empty timeline preserves scene order; exact reversed `mediaOrder` reverses final clip order; duplicate/unknown/incomplete order fails closed; any non-empty `clips`, `videoClips`, or `audioClips` fails closed without calling the media exporter.

- [ ] **Step 2: Verify RED**

Run the PR fast-test workflow and confirm failures are caused by project export ignoring timeline state / missing explicit validation.

- [ ] **Step 3: Implement the minimum adapter**

Add `UnsupportedProjectTimeline` plus a small pure ordering/validation helper. Load timeline state only after scene clips are rendered but before final `MediaExporter.export()`.

- [ ] **Step 4: Verify GREEN**

Run all fast tests. Confirm no regression in project scene rendering, whiteboard compositor, source-video compositor, transitions, or real FFmpeg smokes.

- [ ] **Step 5: Exact-head Windows verification**

Require both `Parity fast tests` and `Windows build and release` to succeed on the same final head before closing this slice.
