## Why

The dogfood buck board (29 parts, built through the public API only) hit two gaps in c0011's build:

- **User properties.** A part number or supplier code cannot reach a built footprint. The DSL `Part` has no properties, the build rewrites `Component.properties` (a model-API property is dropped silently), and c0017's writer refuses a property that the footprint lacks (`kicad.board.projection-read-only`). BOM and placement exports (v0.2a) need them.
- **Global footprints.** c0011 vendors only project-row footprints. `kicad-cli` runs with an empty configuration (c0009's runner, c0013's `check`), so each footprint of a global or template row gives `lib_footprint_issues`: 29 on that board.

Runs on 2026-10-02 (`kicad-cli` 10.0.6 and the pinned 9.0.9 image; S-0020, S-0029) built the blink from a fake global table: three `lib_footprint_issues` without vendoring, none with it. Hidden user properties loaded, caused no `lib_footprint_mismatch`, and survived a 10.0.6 re-save.

## What Changes

- **DSL.** `Part(..., properties={...})`, checked at the call: printable text, no case duplicates, no reserved name (`Reference`, `Value`, `Footprint`, `Datasheet`, `Description`, prefixes `fenolite.` and `ki_`). `to_model` adds them to `Component.properties`.
- **Build, properties.** Each user property is written with `embed.with_property` after `fenolite.path`, in code-point order, hidden on the fabrication layer. `Component.properties` equals what `read_board` projects, so the strict writer passes unchanged. New errors: `build.property-reserved`, `build.property-invalid`, `build.property-conflict` (a library property with the same name and another value).
- **Build, vendoring.** Every placed footprint is copied into `lib/<nickname>.pretty/`, whatever its row origin, under its own nickname, so lib ids stay unchanged. Only placed items are copied. `fenolite build --vendor project` keeps c0011's rule (`build.global-library`). New codes: `build.vendor-unsafe-name` (error) and `build.library-changed` (warning, from the last build record).
- **Evidence.** `PROPERTY_EVIDENCE` and `VENDOR_EVIDENCE` join the envelope when they apply. The `vendor-*` probes run before the build code, with stop rules. The oracle uses fake global and template libraries made from the CC0 mini library, and checks the official-library blink locally (`needs_libs`).
- **Registers.** S-0105 (Python string methods). Hypotheses `H-K-VENDOR-GLOBAL`, `-SHADOW`, `-PROPS`, `-DUPNAME`. Pages `docs/dsl.md`, `board.md`, `libraries.md` and `cli-contract.md`.

Budget: 5.25 working days.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-dsl`:
  - ADDED "User properties in the DSL", "User properties on built footprints" and "Footprints of every row origin are vendored".
  - MODIFIED "DSL to model", "Placement of built parts", "Built project files", "Build command", "Build issue codes" and "Build evidence". c0011 adds these requirements and archives first.
- `kicad-oracle`: ADDED "Vendored projects and user properties pass the oracle".

## Non-goals

- c0017's "Projected fields on write" and field placement or visibility (c0030).
- `kicad-cli` library environment, cache and scan rows (c0021).
- BOM and placement exports (v0.2a).
- Symbol libraries and `sym-lib-table` (schematic writer, v0.2a); 3D models; whole libraries.
- Pruning stale vendored files, and property edits on footprints that layout preservation keeps (c0019).
- Any model, schema or layering change.

## Evidence level required

- DSL checks, property form and order, vendoring rules, issue codes and determinism: mechanical (hermetic tests).
- Vendored global footprints pass the library check (`H-K-VENDOR-GLOBAL`), and user properties load without a library mismatch (`H-K-VENDOR-PROPS`): `KICAD-VERIFIED` on 9.0.9 (target 9) and 10.0.6 (targets 9 and 10). Survival of a re-save is checked on 10.0.6.
- A project row hides a global row with the same nickname (`H-K-VENDOR-SHADOW`): `KICAD-VERIFIED (9.0.x, 10.0.x)`. A re-save merges a duplicate field name (`H-K-VENDOR-DUPNAME`): `KICAD-VERIFIED (10.0.x)`.
- The `build` envelope stays `INFERRED`.

## Impact

- Code: `dsl/part.py`, `dsl/convert.py`, `lens/build.py` and `cli/cmd_build.py`. Tests go under `tests/unit/dsl`, `tests/unit/lens`, `tests/kicad/build` and `tests/libs`.
- Archive order: c0011 first. c0019 rebases four shared requirements.
- Official footprint copies go only into the user's `--out` folder, never into the repository (S-0048).
