# Nolane Studio v0.13.0

Scene Lifecycle Timeline Integrity forensic-parity release.

Highlights:

- makes scene Add, Duplicate, Move and Delete preflight persisted timeline state before changing the scene graph;
- treats current persisted scene order as the authority after a scene lifecycle mutation and rewrites `mediaOrder` to the exact current scene IDs;
- retains only transitions whose endpoints remain adjacent after the mutation, preventing an old transition from silently targeting a different visual relationship;
- removes `sceneEdits` entries whose scene no longer exists;
- duplicates the source scene's explicit `sceneEdits` trim/speed window when a scene is duplicated;
- preserves existing visual-object duplication and custom object-timing ID remapping;
- blocks scene lifecycle mutation when non-empty legacy `clips`, `videoClips` or `audioClips` buckets are present, because their mutation/retarget semantics remain unrecovered;
- validates malformed/duplicate/unknown transition and `sceneEdits` references before mutation instead of allowing the editor to create a later export failure;
- preserves v0.12 selected-scene preview, v0.11 grounded readable labels, v0.10 scene clip trim/speed, v0.9 object timing, v0.8 narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images and v0.4 AI Analyze behavior.

Forensic boundary:

- this release reconciles only rebuild-owned, evidence-backed timeline semantics; it does not decode or invent legacy non-empty `clips`, `videoClips`, `audioClips` or `batch_voice_segments` entries;
- arbitrary legacy multi-track splitting/cutting remains outside this slice even though the repository contains a generic `TimelineClip/split_clip` core;
- arbitrary custom draw paths, source-exact non-default hand/background-removal behavior, object-FX/SFX semantics and source-exact legacy label typography/decoration remain evidence-limited.

Release integrity:

- package metadata and runtime `__version__` are both 0.13.0;
- lifecycle behavior is covered for add, duplicate, move, delete, edit cloning/pruning, transition adjacency and fail-closed opaque legacy-track state;
- the v0.13 implementation passed its initial Linux fast-test gate before release closure;
- merge is allowed only after Linux fast tests and the complete Windows test/NUI/portable/installer/checksum packaging workflow pass again on the exact final release head.
