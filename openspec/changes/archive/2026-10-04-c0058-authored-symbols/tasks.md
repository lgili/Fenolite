# Tasks

- [x] Add exported `Symbol` DSL authoring, validation, explicit `Design.add` membership, and conversion to model definitions.
- [x] Implement deterministic KiCad symbol-library serialization for the supported authored subset.
- [x] Integrate authored symbol resolution and project-local symbol-library output into `fenolite build --target kicad`.
- [x] Add Fenolite-authored tests for DSL validation, serialization roundtrip and build resolution/output without `kicad-cli`.
- [x] Update normative specs, docs, evidence and `CHANGELOG.md`; focused tests (3 passed), `make check-fast` (4804 passed, 9 skipped) and OpenSpec validation passed.
