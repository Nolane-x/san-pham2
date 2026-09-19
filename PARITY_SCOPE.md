# Forensic parity scope — v0.7.0

This branch continues the clean source rebuild of the user's legacy Windows creator application. The recovered EXE and recovered design evidence remain behavioral authorities: useful creator workflows and state contracts are restored while legacy branding, trade dress, licensing, account, telemetry, updater and heavyweight-runtime coupling remain outside the creator path.

## Authority of this parity slice

- Recovered render evidence establishes that scene transitions are **additive**: transition duration is inserted between scene clips and never steals, overlaps or shortens the source scene duration.
- The existing `TransitionSpec`, additive timeline math and FFmpeg transition-segment renderer remain the rendering authority.
- v0.7 adds one explicit rebuild-owned timeline field, `transitions_json`, rather than guessing the unknown per-entry schema of legacy `clips`, `videoClips` or `audioClips`.
- Existing databases are migrated idempotently: `ProjectStore.initialize()` adds `transitions_json TEXT NOT NULL DEFAULT '[]'` only when the column is absent.
- Transition persistence round-trips independently from the four older timeline buckets and does not rewrite their contents.
- Studio edits the selected scene → following scene transition with a supported effect and a duration within the recovered 0.1–10 second bounds.
- When persisted `mediaOrder` is an exact scene permutation, it defines effective adjacency for the editor and final transition preflight.
- Final project export decodes persisted entries into `TransitionSpec`, validates duplicate/adjacent pairs before any renderer runs, then passes them to the existing `MediaExporter`.
- Supported persisted effects are limited to effects already backed by the transition engine: `fade`, `wipeleft`, `wiperight`, `slideleft`, `slideright`, `smoothleft`, and `smoothright`.
- Malformed rows, unsupported effects and non-adjacent transitions fail closed rather than being approximated or silently discarded.
- Existing v0.3 Canvas/Object, v0.4 AI Analyze/Voice, v0.5 Generated Images and v0.6 Advanced Voice storage/render/export authority remains unchanged.

## Evidence-limited boundaries

- Non-empty legacy `clips`, `videoClips` and `audioClips` entry schemas remain fail-closed. Their table buckets are known, but current evidence does not establish a trustworthy per-entry contract.
- Advanced legacy drawing behavior including arbitrary custom draw paths, non-default hand rendering, background removal and object effect/sound semantics remains evidence-limited.
- Exact readable-label post-processing after generated images remains evidence-limited because its source/layout contract has not yet been recovered strongly enough.
- These boundaries are explicit remaining forensic work, not silent feature substitutions.

## Product constraints retained

- Windows desktop remains the primary target, including 8 GB RAM machines.
- No FREE/PRO feature naming, paywall, license verification, mandatory login, or mandatory account gate.
- No mandatory Ollama, OmniVoice, ComfyUI, local LLM, local speech model, local image model, or model-weight download merely to open/use the editor.
- API keys are not persisted in `settings.json`.
- Subsequent parity work must be supported by recovered evidence or be labeled explicitly as new product design.
