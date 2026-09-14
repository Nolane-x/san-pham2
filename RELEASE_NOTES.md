# Nolane Studio v0.2.0

Editor Core release: scenes are now durable project data instead of transient UI state.

Highlights:

- persistent SQLite scene model with stable scene IDs and deterministic ordering;
- scene plans created from scripts are stored before the project enters Studio;
- projects reopened from Library restore their real scenes instead of falling back to blank/demo state;
- add, duplicate, delete and reorder scene workflows are wired to persistent storage;
- selected scene narration/description can be edited and saved from Inspector;
- scene list and Timeline are rebuilt from the same persisted source of truth;
- legacy projects without scene rows migrate into persistent scenes on first Studio open;
- project scene counts stay synchronized with the persistent editor model;
- v0.1.0 remains intact as the verified first public Windows baseline.

Windows release verification continues to cover the full test suite, native rendered UI evidence, portable executable smoke testing, per-user installer build, silent install/launch/uninstall, packaged checksums and GitHub release assets.

The next architecture phase is the real Canvas/Object Engine: persistent visual objects and layers, transforms, z-order, drawing/reveal paths, motion/keyframes and scene composition serialization. Advanced multi-track editing, generated-image workflows and full voice authoring remain subsequent milestones.
