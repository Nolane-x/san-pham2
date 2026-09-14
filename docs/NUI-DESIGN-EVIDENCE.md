# Nolane Studio — Nolane UI Intelligence High-Ambition Packet

## Evidence class

`ARTIFACT_WORK`

This packet documents product UI decisions and verification for Nolane Studio. It does not claim that NUI itself has been empirically proven by this product work.

## Task-profile checksum

- **Surface:** Windows desktop creator application.
- **Primary user/job:** individual creator turns scripts/media into visual video projects during long editing sessions.
- **Inputs:** pointer + keyboard; high-density precision workspace.
- **AI role:** assistive/generative provider, never required for core project persistence or manual editing.
- **Temporal behavior:** long-running exports, interruption-sensitive editing, offline-degraded operation.
- **Risk:** routine creator tool; secrets limited to optional API credentials.
- **Visual ambition:** flagship/high; must feel authored and professional rather than a generic admin dashboard.
- **Density:** medium-high in Studio, lower in Create/Library.
- **Platform:** Windows x64 release only for this milestone.
- **Hard constraints:** 8 GB RAM target; no legacy product name/artwork; no mandatory heavy local inference; preserve creator mental model.
- **Available evidence:** repository tests; GitHub Windows runtime; Qt offscreen screenshots; workflow logs. No human usability study or screen-reader lab is available in this milestone.

## Route-justification ledger

Activated owners:

- `designing-desktop-windowed-workspaces` — long-session precision desktop workspace.
- `designing-nonlinear-media-editors` — scene/media/timeline editing semantics.
- `designing-editor-canvas-workspaces` — central visual canvas plus inspectors/rails.
- `designing-sidebar-navigation` — stable four-destination global shell.
- `directing-visual-hierarchy` — high-density workspace needs clear focus control.
- `crafting-typography` — dense metadata and action hierarchy.
- `crafting-color` — dark creator environment with color-independent structure.
- `modeling-component-states` — selected scene/nav/provider/export states.
- `designing-empty-loading-error-states` — no-project/no-provider/import/export boundaries.
- `designing-accessible-interfaces` — keyboard/focus/contrast obligations.
- `iterating-rendered-visual-design` — high-ambition completion requires actual renders.

Inactive high-impact owners:

- touch/mobile — excluded because this milestone is Windows desktop only.
- collaboration/multi-user — no product requirement in this milestone.
- spatial/3D — no product requirement.
- external component library adoption — intentionally none; Qt primitives are styled locally and no third-party UI trade dress is adopted.

## Visual thesis — “Midnight production desk”

The product should read as one continuous editing environment, not a stack of unrelated cards. The visual system therefore uses:

- near-black canvas and sidebar with three restrained surface elevations;
- one violet primary accent for action/selection and one mint secondary accent for system/local status;
- compact Segoe UI typography with strong title-to-metadata hierarchy;
- rounded geometry only where it communicates grouping or manipulable controls;
- a new authored N mark drawn in code, so no legacy imagery or external asset is inherited;
- an editor-specific signature: narrow scene rail, light paper canvas inside a dark production field, precision inspector and compressed timeline strip.

The identity should survive logo blinding: the central light composition canvas, production rails and timeline still communicate a focused visual-story editor rather than a generic SaaS dashboard.

## Information architecture

```text
Create
  story input + local scene map

Studio
  scenes/media | canvas | inspector
  -------------------------------
              timeline

Library
  durable local project collection

Providers
  low-memory provider configuration and runtime state
```

The structure preserves the recovered creator mental model while replacing old branding and visual language completely.

## Accessibility/interaction obligations

- navigation buttons have clear checked state in addition to color;
- primary actions remain text-labelled;
- creator state is not encoded by color alone;
- tooltips explain compact controls;
- focusable Qt controls retain native keyboard semantics;
- minimum window is 1120×720 and splitters allow density adjustment;
- long operations run off the UI thread where implemented (export);
- reduced-motion is naturally respected because the initial shell contains no decorative animation.

## Rendered iteration ledger

### Baseline

The pre-redesign shell was structurally functional but visually flat: one 230 px sidebar, plain list navigation, text-only pages, no authored canvas/editor signature and no real workspace density.

### Iteration A — current branch

**Hypothesis:** replacing the flat shell with a creator-native continuous workspace will improve hierarchy and product specificity without adding heavy media or animation.

Changed variables:

- navigation composition;
- surface hierarchy;
- typography scale;
- authored brand mark;
- Create split-pane scene map;
- Studio scene/canvas/inspector/timeline composition;
- status and provider surfaces.

Runtime evidence is produced by `.github/workflows/windows-release.yml` as `artifacts/ui/create.png` and `artifacts/ui/studio.png`.

**Status:** `UNKNOWN` until the Windows render is inspected. Build/test success alone does not close this packet.

## Omission declaration

This milestone does not provide human usability evidence, screen-reader traversal evidence, high-contrast/forced-colors capture, or real Windows DPI matrix captures. Those remain `UNKNOWN`; they are not silently promoted to PASS.
