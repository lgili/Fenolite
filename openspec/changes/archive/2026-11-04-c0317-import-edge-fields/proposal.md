## Why

The source-bound strict fidelity census on `613b6f1b` refused six board imports because their root
outline strokes differ from the created board's fixed 0.1 mm width. Each has one uniform width;
one includes both lines and arcs. The refusal prevents silent loss, but the supported native stroke
field can be carried through the DSL and writer. The other census failures need separate fixes.

## What changes

- Add an optional `Design.board(..., outline_width=length)` and optional model outline stroke width.
- Preserve a uniform supported root outline width during import and native KiCad build.
- Keep mixed or invalid widths and unrelated omissions as strict, located refusals.
- Prove the behavior with authored controls, unchanged default build bytes and a focused external
  remeasurement. Keep the historical census and all unreviewed acceptance baselines intact.

## Non-goals

No schematic changes, general per-edge styling API, lossy import, relaxed equivalence, accepted
differences, ratchet changes, native GUI claims, upstream CAD fixtures, new dependencies or new codes.

## Evidence level required

The implementation and authored writer/readback controls are `INFERRED`. A focused cached public
input measurement records its exact source and results without promoting the native application
evidence. Required KiCad 9.0.9/10.0.6 and exact-head whole-batch CI remain open until they run.

## Sources

Existing KiCad stroke representation: S-0001 and `docs/formats/kicad/board.md`. Existing contracts:
c0277 board import coverage, c0281 outline-loss accounting and c0278 strict geometry/fidelity proof.
The 2026-11-01 census is recorded in `docs/evidence/fidelity.md`; no new format fact is introduced.
