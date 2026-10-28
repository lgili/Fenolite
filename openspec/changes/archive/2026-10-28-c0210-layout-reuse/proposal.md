## Why

Package 4 of change c0175 ("Layout reuse"). A datasheet layout, a reference board or a channel already
placed holds a block that a board should repeat: a regulator with its capacitors, a gate driver, a
measurement channel. Copying it by hand is slow, and a copy by the part centres can come out mirrored or
turned without anyone noticing; the agent guide already teaches "copy by the pads" (`board-floorplan`,
"Reference blocks"), but nothing in Fenolite does it. The pieces exist: board-frame pad records for any
backend, `move_footprint` for a turn or a side change, the legality check of `place`, the copper groups
and `prune` of `tidy` and the copper check.

## What Changes

- New package `fenolite.reuse` (imports `model`, `geometry` and `backends.base` only):
  - `fit_rigid` and `fit_block`: the least-squares rigid fit (four quarter turns, a mirror, a
    translation) over the pads with a number found once in both footprints, first of the anchor, then of
    each part onto the block transform of its reference part's pads; the side comes from the fit.
  - `copy_copper`: the reference tracks, arcs and vias of the block's nets mapped through the block
    transform onto the board's nets and layers.
- A new strategy of `fenolite place`: `--strategy reuse` (implied by `--from REFERENCE`) with `--only`,
  `--anchor`, `--map TARGET=REFERENCE`, `--copper`, `--tolerance` and `--drc`. Its glue (`cli.place_reuse`,
  `cli.reuse_copper`) moves the parts, measures their pads, runs the copper check before and after, and
  settles the copied copper with `tidy.prune`, an island rule and the copper check, until nothing changes.
- Eight issue codes `reuse.*`, explained by `fenolite explain`; the hypotheses `H-G-REUSE-FIT` and
  `H-K-REUSE-DRC`.

## Capabilities

### New Capabilities

- `layout-reuse`: "Rigid fit of a block", "Parts placed by their pads", "A part without a fit",
  "Placement of a copied block", "Copper of a copied block", "Settling the copied copper", "Reuse strategy
  of place", "Reuse with DRC" and "Reuse codes". It holds the copy of a block of a reference board by
  the pads, with the copper that joins them, each placement and each copied item checked before the
  write.

### Modified Capabilities

None. c0175 keeps the rest of its `layout-reuse` delta, narrowed: "Pads matched by net partition",
"Zones of a copied block" and "Group moves", with its tasks 8.4, 8.5 and 8.6; moved on 2026-10-28 to
change c0227 (`openspec/changes/c0227-reuse-moves/`), which adds them to `layout-reuse` after this change.

## Non-goals

- Matching a pad without a unique number by the nets of its pads (c0175, task 8.5): the fit uses the
  pads with unique numbers, and a footprint of `GND` pads only gives `reuse.no-fit`.
- Copying zones, and rebuilding a zone whose reader output holds a fill and no outline (c0175, task 8.6):
  a copied zone needs its fill judged against the board's other zones.
- Group moves `place --turn`, `--shift` and `--pose-search` (c0175, task 8.4).
- A separate `fenolite reuse` command: the strategy of `place` shares its protocol, legality check,
  placement rules and measures, and keeps the generated command page within its budget (design,
  decision 1).
- Running DRC without `--drc`: the unit suites stay without a tool, as for `tidy`.

## Evidence level required

`INFERRED` (`H-G-REUSE-FIT`): every moved pad is measured on the board frame against its goal, the
copper check and the legality check judge the result, and no tool compares the copy with the reference.
With `--drc`, `kicad-cli` DRC on the exact bytes adds `KICAD-VERIFIED` for the written board
(`H-K-REUSE-DRC`), combined with the evidence of the reference board read; `tests/kicad/reuse/` settles
the row on both majors.

## Impact

- `src/fenolite/reuse/`, `src/fenolite/cli/place_reuse.py`, `src/fenolite/cli/reuse_copper.py`,
  `src/fenolite/cli/cmd_place.py` (the strategy),
  `cli/explain.py`, `cli/data/explain.toml`, `tests/unit/test_import_graph.py` (row `reuse`), the bench
  `tests/_reusebench.py`, tests, `docs/placement.md`, `docs/cli-contract.md`, `docs/hypotheses.md`, the
  guide's `placement` and `board-floorplan` pages and its generated `commands` page, `CHANGELOG.md`, and
  c0175's `tasks.md`, `design.md` and `specs/layout-reuse/spec.md`.
