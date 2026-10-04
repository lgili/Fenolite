# Design: DSL footprint authoring

## Public API

Add `Footprint` to `fenolite.dsl`. It represents one library definition with a library nickname and safe footprint name, description, kind, `pad(...)`, and `line`, `rect`, `circle`, and `polygon` methods. Inputs use existing DSL length parsing (`mm`, `mil`, `nm`) and tuple coordinates. `Design.add_footprint(fp)` registers definitions outside the canonical model. `Part(..., footprint=fp.lib_id)` assigns by the existing library ID contract.

## Implementation

- `src/fenolite/dsl/footprint.py`: validated builder; lowers to immutable `FootprintDef` with deterministic entities and pads/graphics in declaration order.
- `src/fenolite/dsl/design.py`: registry with duplicate-ID rejection and `add_footprint`.
- `src/fenolite/dsl/__init__.py` and `docs/dsl.md`: exports and examples.
- `src/fenolite/backends/kicad/mod.py`: allow writing authored definitions without source KiCad slots, with deterministic native output and the same representability/loss checks.
- `src/fenolite/lens/build.py`: registered definition lookup takes precedence over library resolution; generated library is included in output and board placement uses the registered definition.
- `src/fenolite/lens/altium.py`: the Altium footprint resolver accepts registered definitions for matching links and lowers the supported subset with the existing writer.
- `openspec/README.md`, `docs/roadmap.md`, and `CHANGELOG.md`: record ownership and progress.

Authored definitions are build inputs only; they are not inserted into `model.Design`, `.fenolite` JSON, or read back as project-owned library rows. Existing library resolution and assignment remain intact.

## Evidence and proof

Pure API checks and generated-file checks can reach `CORPUS-VERIFIED` with authored data. KiCad syntax and Altium binary output remain `INFERRED` absent external oracle verification. Per-task proof commands are recorded in `tasks.md`; full tests are deferred unless explicitly requested.

## Budget

Approximately 4 design-days: API and validation (1), KiCad write/build integration (1.5), Altium integration and docs (1), evidence and changelog (0.5).
