# Nolane Studio v0.15.0

Scene Lifecycle Timeline Integrity forensic-parity release.

Highlights:

- makes scene Add, Duplicate, Move and Delete preflight persisted timeline state before changing the scene graph;
- rewrites `mediaOrder` to the exact authoritative current scene IDs after every supported scene lifecycle mutation;
- retains only transitions whose endpoints remain adjacent after the mutation, preventing stale transitions from silently retargeting a different visual relationship;
- removes `sceneEdits` entries whose scene no longer exists;
- clones a duplicated source scene's explicit trim/speed `sceneEdits` window onto the duplicate while preserving existing object/custom-timing ID remapping;
- recreates a valid one-scene timeline when the final scene is deleted and Studio creates its replacement blank scene;
- blocks lifecycle mutation before graph changes when opaque non-empty legacy `clips`, `videoClips` or `audioClips` state is present;
- rejects malformed timeline references such as non-adjacent persisted transitions before mutation rather than turning them into a later export failure;
- replaces stale diverged PR #16 with a clean current-main port on top of merged v0.14;
- preserves v0.14 project-wide drawing settings, v0.13 lossless scene reset, v0.12 selected-scene preview, v0.11 grounded readable labels, v0.10 scene trim/speed, v0.9 object timing, v0.8 narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images and v0.4 AI Analyze behavior.

Forensic boundary:

- this release reconciles only rebuild-owned, evidence-backed timeline semantics and does not decode or invent legacy non-empty track entry schemas;
- arbitrary legacy multi-track splitting/cutting remains outside this slice even though the repository contains generic timeline helpers;
- arbitrary custom draw paths, source-exact non-default hand/background-removal behavior, object-FX/SFX semantics and source-exact legacy label typography/decoration remain evidence-limited.

Release integrity:

- package metadata and runtime `__version__` are both 0.15.0;
- offscreen lifecycle coverage locks add, duplicate, move, delete, last-scene replacement, edit cloning/pruning, transition adjacency and fail-closed opaque legacy-track behavior;
- implementation fast tests passed before release closure;
- merge is allowed only after Linux fast tests and the complete Windows test/NUI/portable/installer/checksum packaging workflow pass again on the exact final release head.
