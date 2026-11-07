# c0413: teardrop proof scope for rotated and custom pad parents

## Why

The c0401 census (`kicad-demo-9-0-9-1-pcb-01`, KiCad 10.0.6, 2026-11-05) leaves `7:opaque-count=1`: the
import omits the board's six `padvia` teardrop caches as regenerated, and the c0340 same-tool proof
(`fenolite.backends.kicad.derived_teardrops.qualifies`) refuses the board before native execution. Three
narrow limits refuse it, measured on that public board:

- a footprint and its custom pad at 20° raise "unqualified non-quarter parent pose";
- a custom pad with `(options (clearance convexhull) …)` raises "unknown custom clearance option";
- with those two let through in a scratch run, KiCad regenerates six caches on each side, with
  exact equal geometry, but one regenerated cache touches only the primitive copper of a custom pad
  at 270°, 4.7 mm from its anchor, so the anchor-only parent body cannot attach it.

## What

Widen the qualification of teardrop parents, keeping every decision exact or refused:

- a parent pose at any whole-microdegree angle, judged with `core.trig.cos_sin_fixed` and an explicit
  error bound; a containment or contact test the bound cannot settle refuses qualification;
- custom pads with `(clearance outline)` or `(clearance convexhull)`; the anchor is copper in both modes;
- custom pad bodies grow from the anchor to the primitives whose copper is a known subset: a line as
  its round-capped stroke, a filled circle as its disc, and, under quarter-turn poses, a filled polygon
  as its interior. Arcs, unfilled shapes and other primitives add no body; bottom-side footprints keep the
  anchor only.

Native authored controls (KiCad DRC contact on 9.0.9 and 10.0.6) prove the rotated body and the
primitive frame. Native regeneration stays KiCad 10 only (`H-K-DERIVED-TD-PROOF`).

## Impact

- `src/fenolite/backends/kicad/derived_teardrops.py` (`_at`, `_Parent`, `_parents`, `_custom_anchor`).
- Tests: `tests/unit/backends/kicad/test_derived_teardrops.py`; a new native control
  `tests/kicad/board/test_rotated_custom_parent_oracle.py`.
- Evidence: `docs/formats/kicad/frame.md` rows, source `S-1740`, `H-K-DERIVED-TD-PROOF` scope text.
- No public name, CLI argument, model field or evidence level of another row changes. Pure equivalence
  is unchanged; only which boards may enter the existing proof widens.
