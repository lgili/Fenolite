## 0. Entry and baseline

- [x] 0.1 Read repository/coordination rules, import/model/lens/equivalence contracts and the conversion
  ownership report; verify c0318 is unused, record the decisions, and validate the proposal.
  Proof: `openspec validate c0318-import-footprint-identity --strict`.
- [x] 0.2 Capture immutable ordinary/default build and ordinary import complete-file digests before
  implementation, and reproduce the authored same-ID/different-geometry identity defect.
  Proof: focused baseline/reproduction tests and saved baseline SHA.

## 1. Separate identity and lookup

- [x] 1.1 Add the optional/default-omitted model field and validated keyword-only DSL override, preserving
  native `lib_footprint_ref`. Reserve the actual Part attributes against device-interface shadowing
  (including the inherited table omissions exposed by this proof). Regenerate active model schemas
  and record the field for final KEEP.
  Proof: focused model/DSL serialization, invalid-type/device/query tests and generated schema check.
- [x] 1.2 Emit overrides only for differing vendored/native IDs; resolve the exact internal definition and
  embed the original native PCB name. Use the lookup for package, pad-map and layout geometry; refuse
  the override on Altium before writing. Remove the old variant-name self-check exception, preserving
  all pads and local variant files.
  Proof: authored import/build/readback variant tests and strict public comparison, with no acceptance.

## 2. Regression and teaching

- [x] 2.1 Prove a repeated shared sheet with physical variants builds twice while native metadata, value,
  same-unit and electrical mismatches still fail through the existing guards.
  Proof: authored repeated-sheet cases and existing drawn/importer guard groups.
- [x] 2.2 Compare complete ordinary/default build and ordinary import file maps to immutable base;
  document the identity/lookup boundary and teach the optional keyword with a tested guide line.
  Proof: byte guards, guide recipes/budget, docs and one Unreleased changelog entry.

## 3. Validation and handoff

- [x] 3.1 Run focused import/vendor/emit, native embed, DSL/model and drawn regression groups; run lint,
  format, types, residue and generated/strict checks. Proof: recorded focused logs and strict validation.
- [x] 3.2 Coordinator: integrate the signed source with the pending source schematic packets, refresh
  the actual final model0 KEEP/freeze inventory, and run the scheduled full gate/exact-head CI.
  Proof: actual final source/inventory and CI jobs. Leave open in this worker; no full suite or push.
  Integration check 2026-11-04 on 468d8a61: the source is integrated with the schematic packets that
  were pending (c0276, c0320, c0326, c0329 and c0330 are archived on this base). `tools/model_review.py`
  regenerates 175 dataclasses and 1251 fields whose names, types and defaults equal c0218's committed
  final inventory, including `Component.footprint_definition_ref` (str, default ""); the field is in
  `schemas/fenolite.model.v1/circuit.json`. Focused identity/alias/vendor/embed/DSL/model/review-tool
  tests 103 passed. The scheduled full gate and exact-head CI stay with the coordinator.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): the full gate is the exact-head CI: CI 41968083051 on 5f46b8d7 (cac/lote-16): every required job green, including unit on five platforms, kicad-9, kicad-10 shards 0-3, routing 9/10, viewer, mcp, wheel, complete test coverage and ci-complete.
