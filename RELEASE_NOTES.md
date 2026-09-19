# Nolane Studio v0.11.0

Grounded Readable Label Overlay forensic-parity release.

Highlights:

- restores the recovered rule that readable labels are added deterministically after image generation instead of asking the diffusion/image provider to render long text;
- consumes the already-persisted AI Analyze contract: exact `label` text plus normalized grounded `box` coordinates;
- materializes each recovered label as an editable Canvas `text` object, so the normal scene compositor and authoritative final export render the same layer state the user sees;
- syncs labels both when an analyzed scene image is generated/regenerated and when AI Analyze runs after an image already exists;
- uses stable analysis slots so repeated synchronization is idempotent and existing service-owned object IDs are retained when possible;
- removes only stale Nolane-owned readable-label slots and never hijacks or deletes user-created text layers;
- validates the complete requested label set before the first label mutation and rejects malformed/non-finite/out-of-range/zero-area boxes fail-closed;
- limits automatic label materialization to the recovered whiteboard path; other visual styles remain untouched;
- preserves v0.10 scene clip trim/speed, v0.9 object timing, v0.8 scene narration export, v0.7 transitions, v0.6 advanced voice, v0.5 generated images and v0.4 AI Analyze behavior.

Forensic boundary:

- grounded box coordinates are the recovered placement authority for this slice;
- the rebuild uses a neutral deterministic text style and does **not** claim source-exact legacy font, decoration, callout shape or typography;
- arbitrary custom draw paths, non-default hand rendering, background removal and object-FX/SFX semantics remain evidence-limited;
- arbitrary legacy multi-track clip splitting/cutting and the non-empty `clips`, `videoClips`, `audioClips` and `batch_voice_segments` entry schemas remain fail-closed rather than guessed.

Release integrity:

- package metadata and runtime `__version__` are both 0.11.0 in this branch;
- the label implementation is covered by core idempotence/preservation/fail-closed tests plus an offscreen Studio AI Analyze lifecycle test;
- merge is allowed only after Linux fast tests and the complete Windows test/NUI/portable/installer/checksum packaging workflow pass on the exact final head.
