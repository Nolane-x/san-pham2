# Nolane Studio v0.3.0

Canvas/Object Engine parity release.

Highlights:

- persistent visual objects and layers are stored per scene with stable IDs and deterministic z-order;
- Studio canvas restores persisted shape, text, image, video and drawing objects instead of flattening editor state;
- layer movement, object transforms, deletion and scene duplication preserve authoritative SQLite state;
- freehand drawing persists as scene drawing layers and survives scene reloads;
- recovered scene render settings, reveal/hold timing, drawing modes, brush direction, hand style, background removal and object timing are persisted;
- final project export now consumes persisted scene composition and validated timeline ordering rather than silently ignoring editor state;
- static, whiteboard and source-video composition paths preserve supported layer ordering and fail closed on ambiguous or unsupported persisted state;
- render preflight rejects malformed identities, kinds, z-order, geometry, payloads, timing, camera settings and other non-finite/corrupt persisted values before output side effects;
- storage writers reject silent sequence-to-mapping, fractional-index, non-finite geometry and truthiness coercions that could create invalid scene/object state;
- Canvas hydration validates z-index and payload shape before destructive UI replacement;
- Windows verification covers the full 654-test suite, NUI rendered evidence, portable executable smoke testing, Inno Setup packaging, silent install/launch/uninstall and SHA-256 verification.

Release integrity:

- v0.2.0 remains the Editor Core baseline;
- v0.3.0 is the first release containing the persistent Canvas/Object Engine parity work;
- release automation refuses to overwrite an existing version tag that belongs to a different commit, preventing stale-version asset clobbering.
