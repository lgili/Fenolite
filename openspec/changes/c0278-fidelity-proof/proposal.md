## Why

The board library (`docs/research/board-library.md`, sections 4.4 and 4.5, row c0278 of section 5) turns
public boards into `design.py` files (c0275). A converted board is worth something only with a proof that
the code rebuilds the original, and that proof must keep holding as Fenolite changes: a regression in a
reader, the DSL or a writer must show up as a failed board. That is what makes the library a benchmark.

`fenolite equivalent` already compares two designs at five levels: components, netlist, footprints and
pads, placement, and routing per net (connectivity, vias and length). That is not enough for a
conversion:

- level 5 accepts any copper that joins the same pads with the same lengths, so a track drawn on another
  path passes;
- net classes, clearances, custom rules and the stack-up are not compared at all;
- the outline, zone outlines, board drawings, texts and footprint fields are not compared;
- nothing compares what a person sees: the layers and the schematic as drawn;
- the schematic is compared only as a netlist, never as a drawing (c0276 makes drawings possible).

There is also no one command that takes a script and an original, builds the script and compares, and no
place to write down a difference that is understood and accepted.

## What Changes

- **Level 5 strict.** `--strict` (and `compare_designs(..., strict=True)`) matches every track, arc and
  via item by item, by copper span and geometry, then compares width, drill, span, type, net and lock. It
  is a second rule table beside the routing rule, as c0089 left room for.
- **Level 6 rules.** Net classes, their members, custom rules, board-wide rules and minimums, the stack-up
  and the layer table, field by field from the canonical JSON, ids and provenance left out.
- **Level 7 exact geometry.** Outline rings, cut-outs and slots, zones by outline, layers, net, priority and
  settings (never the fill), rule areas, board graphics and texts, holes, dimensions, and the graphics,
  texts and fields of each footprint, after an integer normalisation of rings, segments and arcs.
- **Level 8 presentation.** Each board layer and each schematic sheet of both sides rendered by Fenolite's
  scene builder into integer run-length masks on one grid and compared within a pixel tolerance (default
  1000 ppm, as the viewer's screenshot tests use), with the region located and the changed primitives
  named by the visual diff of c0184.
- **Level S drawn schematic.** Two drawn schematics (c0276) compared item by item, wires as maximal
  collinear segments, and their resolved connectivity.
- **`fenolite verify-source SCRIPT --against ORIGINAL`** builds the script in a temporary folder for the
  original's KiCad major, reads both sides and runs every level, skipping with a stated reason what a side
  cannot reach. Hermetic unless `--upgrade` is asked for.
- **Accepted differences in `PROVENANCE.json`.** The member `fidelity.accepted` lists each understood
  difference (level, kind, where glob, field, reason, attribution, date); they become exclusion rules of
  the existing equivalence package. An entry that no longer matches is reported, so acceptances shrink as
  Fenolite improves. `--record` writes `fidelity.proof` (version, date, hashes, tolerances, level statuses)
  through plan and confirm.
- **Round-trip test category** `tests/fidelity/`: read an authored KiCad project, emit code (c0275), build,
  verify, all hermetic; and `tests/kicad/fidelity/` over the corpus rows of a new use `rtf`, with a ratchet
  of allowed counts per row that holds no upstream name.
- **`fenolite equivalent`** gains `--level 6`, `7`, `8`, `S` and `--strict`; its default level and its
  output for existing calls do not change.

## Capabilities

### New Capabilities

- `fidelity-proof`: the `verify-source` command, its inputs, temporary build, levels, tolerances, result,
  exit codes, accepted differences and recording in the provenance file, rendered layer masks, codes, the
  round-trip test category and corpus runs, evidence and documentation.

### Modified Capabilities

- `design-equivalence`: MODIFIED "Equivalence package", "Differences are located", "Equivalent command",
  "Level 5 in the equivalent command" and "Equivalence documentation". ADDED "Level 5 strict compares
  copper items", "Level 5 strict matching", "Level 6 compares rules", "Level 7 compares exact geometry",
  "Level 7 normalisation", "Level 8 compares rendered presentation", "Level S compares drawn schematics"
  and "Levels 6 to 8 and S in the equivalent command".
- `corpus-policy`: ADDED "Round-trip fidelity use".

## Dependencies

- **c0275 board-to-code** (required for the round-trip category and the library): `fenolite import --to
  python` and the `PROVENANCE.json` file it creates. Levels 5 strict to 8 and `verify-source` itself do
  not need it and can land first.
- **c0276 drawn-schematic** (required for level S): `DrawnSchematic`, `extract` and `resolve`.
- **c0277 dsl-board-coverage**: what the DSL cannot express shows as differences at levels 6 and 7 until
  c0277 closes it; those are accepted with attribution `fenolite`.
- **c0279 board-library** uses `verify-source` in its CI and owns the rest of the provenance schema.
- Reuses c0045 and c0089 (equivalence package, sides, tolerances, exclusions), c0184 (visual diff) and the
  scene builders of the viewer.

## Non-goals

- No comparison of zone fills: they depend on the filler and its version. Level 8 draws zone outlines.
- No pixel comparison against KiCad's own plots in this change (open question 2).
- No proof for Altium drawings at level S (the Altium reader keeps no wire geometry yet).
- No automatic acceptance: each accepted difference is written with a reason by a person or a reviewed
  `--accept`.
- No change of the default level or output of existing `fenolite equivalent` calls.

## Evidence level required

- Levels 5 strict, 6, 7 and S: `INFERRED`, unit-tested with planted edits, and proved on the authored
  fixtures; corpus counts recorded in `docs/evidence/fidelity.md`.
- Level 8: `INFERRED`, because one renderer draws both sides (`H-K-FID-PLOT-AGREE` stays open).
- Zone outlines unchanged by KiCad's save and refill: `H-K-FID-ZONE-OUTLINE`, `INFERRED` until the KiCad CI
  job measures it.

## Impact

- New: `src/fenolite/checks/equivalence/strict.py`, `rules.py`, `shapes.py`, `drawn.py`;
  `src/fenolite/view/fidelity.py`; `src/fenolite/cli/cmd_verify_source.py`;
  `schemas/fenolite.verify-source.v0.json`; `docs/fidelity.md`; `docs/evidence/fidelity.md`;
  `tests/fidelity/`, `tests/kicad/fidelity/`, `tests/data/fidelity/` (authored, CC0); tests under
  `tests/unit/checks/equivalence`, `tests/unit/view` and `tests/unit/cli`.
- Changed: `checks/equivalence/__init__.py`, `levels.py`, `codes.py`, `exclusions.py`, `cli/cmd_equivalent.py`,
  `api/` (the equivalence result keys), `schemas/fenolite.equivalent.v0.json`, `tests/corpus/manifest.toml`,
  `explain.toml`, `docs/equivalence.md`, `docs/cli-contract.md`, `docs/roadmap.md`, `docs/hypotheses.md`,
  the guide page `checks.md`, `CHANGELOG.md`.
- Size: about 9 design-days (M).
