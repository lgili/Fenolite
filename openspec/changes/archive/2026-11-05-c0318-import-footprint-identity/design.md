## Context

`Component.lib_footprint_ref` is currently both an imported native identity and a build lookup key.
`importer.vendor` derives changed physical instances as `<name>_2`; `emit.design` writes that local key
as `Part.footprint`. The build propagates it to schematic metadata and the PCB footprint header.
`drawn_connect.coverage` correctly requires shared physical sheet symbols to have equal value and
footprint metadata, so conflating the keys triggers a real false identity mismatch. Public level 3
also correctly compares the native PCB names and reports the changed name.

## Decisions

Decided 2026-11-01 under the authorized recommended decisions:

1. Retain `Component.lib_footprint_ref` as native/original identity. Add
   `Component.footprint_definition_ref: str = ""` solely for local definition resolution. Empty means
   ordinary resolution through `lib_footprint_ref`; canonical output omits the default.
2. Add keyword-only `Part(..., footprint_definition="...")`. A nonempty override requires an explicit
   native `footprint=` and an explicit symbol part, rather than a device/query. It selects geometry;
   it does not assert geometry equality or alter the pin map. Invalid value types are refused.
3. The importer retains its existing per-ref vendored lookup map and all derived definitions. Only
   differing native/lookup names emit `footprint=original, footprint_definition=local_variant`.
   Ordinary emission stays byte-identical. Explicit empty native IDs remain distinguishable because
   the override carries the physical lookup; no symbol fallback replaces such an explicit identity.
4. The build resolves the override while preserving native component identity. Embedding uses native
   identity only for the explicit override, leaving all ordinary placement behavior unchanged.
   Existing schematic writers and shared-sheet value/electrical guards continue using their current
   native field, so no schematic adapter or comparator normalization is needed.
5. Keep the existing import variant diagnostic and generated definitions. Do not accept, suppress or
   normalize footprint-name differences: the actual written PCB must carry the original name.
6. The model field is a pre-1.0 KEEP addition coordinated with c0218/c0219. The actual last model0
   source and freeze receipts are refreshed by the coordinator after this source is integrated.
7. The override is for KiCad builds. Package/library, pad-map and placement geometry selection uses
   the definition reference. Altium builds refuse an explicit override before planning writes; no
   Altium alias semantics are invented. Remove the old self-check variant-name exception: a real
   footprint name change must fail even when its spelling resembles a local variant.
8. Reserve `footprint_definition` against device-interface shadowing. The existing exact attribute
   proof exposes older omissions in the same table; complete it from the actual Part attributes,
   retaining its closed namespace and test rather than exempting the new keyword.

## Ownership and non-goals

This isolated worktree starts at immutable `96d687d1`. Own model/circuit, DSL conversion/part,
importer emit/vendor, the narrow build resolver and PCB embedding boundary, and focused tests/docs.
The schematic owner retains importer/schematic, KiCad drawn lowering and drawn models/alias work;
their files are not changed. Do not alter comparison, accepted loss, refusal coverage, pads, placement,
source provenance, native source files or default build bytes. No full suite, push or publication.

## Proof strategy

Use Fenolite-authored fixtures only. A meaningful edit changes a pad's geometry under the same source
ID; prove distinct local definitions and actual readback geometry, identical original native PCB IDs,
and zero public level-3 footprint-name differences. Repeat with one shared physical schematic and two
instance paths; preserve strict mismatch checks for value and same-unit electrical differences.
Measure complete ordinary build/import file maps from the immutable base before implementation and
compare every resulting byte. Rebuild the variant twice without acceptance/loss flags and run the
existing focused import, embed, model, DSL and drawn guards. External corpus observations may be
read-only supplementary checks, never committed third-party material or substitutes for authored proof.
