# Nolane Studio v0.7.0

Scene Transition Editor forensic-parity release.

Highlights:

- restores the recovered scene-transition workflow as explicit persisted project state without guessing the unrecovered legacy `clips`, `videoClips` or `audioClips` entry schemas;
- adds an idempotent SQLite migration for `transitions_json`, preserving projects created by earlier Nolane Studio releases;
- adds a Studio transition editor for the selected scene → following scene pair, with explicit save/clear controls, effect selection and the recovered 0.1–10 second duration bounds;
- supports the transition effects already backed by the existing FFmpeg transition engine: fade, wipe left/right, slide left/right and smooth left/right;
- evaluates transition adjacency against the effective persisted `mediaOrder` when that order is an exact scene permutation;
- decodes persisted transition rows into validated `TransitionSpec` values before any scene renderer starts;
- fails closed on malformed transition entries, unsupported effects, duplicates or non-adjacent scene pairs instead of silently dropping timeline state;
- routes persisted transitions into final project export, where each transition remains its own normalized additive segment and never shortens or overlaps source scene duration;
- preserves v0.6 advanced voice, v0.5 generated images, v0.4 AI Analyze, v0.3 Canvas/Object and all prior render/export authority.

Forensic boundary:

- non-empty legacy `clips`, `videoClips` and `audioClips` per-entry schemas remain fail-closed because current recovered evidence does not establish their exact structure;
- advanced legacy drawing algorithms, non-default hand rendering/background-removal/object-FX behavior and exact readable-label post-processing remain separate evidence-limited parity work;
- v0.7 does not reinterpret those unknown payloads merely to make the timeline appear more complete.

Release integrity:

- v0.6.0 remains the Advanced Voice Capabilities baseline;
- v0.7.0 is the first release containing persisted scene-transition editing through final additive export;
- the Windows workflow tests the exact release commit, captures NUI rendered evidence, smoke-tests portable and installed executables, validates checksums and publishes versioned assets only from `main`.
