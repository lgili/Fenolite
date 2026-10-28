## Why

The rest of package 4 of change c0175 ("Layout reuse"), after c0210 built `place --strategy reuse`. Three
gaps remain. A footprint whose pads share a number (three `GND` pads of a regulator, the exposed pads of a
package) gives the fit fewer pairs, and a footprint of `GND` pads only gives `reuse.no-fit`. The zones of a
block (a small ground pour under a regulator) are not copied, and a zone that a reader gives as a fill
without an outline cannot be written back. And a placed module cannot be turned or shifted with its
satellites and their copper as one piece, nor its best turn searched.

## What Changes

- `fenolite.reuse.fit_block` pairs the pads without a unique number by the nets of their pads: each
  reference net maps to the target net of the pads paired by number, and within a part a net's pads pair
  one to one, or by the nearest goal under the fit by number. `PadMatch` names both pad ids and how it was
  paired; `result.reuse.parts[].by_net` counts the pads paired by net.
- `fenolite.reuse.copy_copper` copies the zones of the block's nets whose stored fill joins paired pads
  only, outline and fill through the block transform, and rebuilds the outline of a zone read without one
  from its fill. The settling of c0210 judges a copied zone like a track and also drops one that no longer
  joins the images of its pads (`pad-lost`).
- A new strategy of `fenolite place`, `group`, implied by `--turn REFS --about X,Y --angle DEGREES` or
  `--shift REFS --by DX,DY`: the parts move rigidly with the copper and zones joined to their pads only,
  every moved pad is measured and the copper check compares the board before and after.
  `--pose-search --within LENGTH` tries the four turns and a grid of shifts and reports the demand across
  the group's border, without writing.
- Codes `place.group-failed` (error) and `place.fill-stale` (info); the hypotheses `H-G-GROUP-MOVE` and
  `H-G-REUSE-ZONE`, and `H-K-GROUP-DRC` for the KiCad proof of a group move.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `layout-reuse` (created by c0210, not archived yet): ADDED "Pads matched by net partition", "Zones of a
  copied block", "A zone read without its outline", "Group moves", "Copper of a moved group", "Pose search"
  and "Group move codes". These are c0175's requirements "Pads matched by net partition", "Zones of a copied
  block" and "Group moves", moved here with its tasks 8.4 to 8.6 on 2026-10-28 and split; c0175 no longer
  holds a `layout-reuse` delta.

## Non-goals

- Moving copper because a part "owns" it (c0175's "locked or scripted copper that the group's parts own"):
  the model has no owner of copper; copper moves when every pad it joins moves (design, decision 5).
- Moving board texts with a group: a footprint's fields move with it; texts on the board belong to no part.
- Judging the legality of each pose of `--pose-search`: the search ranks the poses by their demand only, and
  the chosen one is applied with `--turn ... --angle` and `--shift`, which the legality check judges.
- Filling a copied or moved zone again: its fill is the moved reference fill, and `place.fill-stale` /
  `reuse.fill-stale` ask for `fenolite fill`.

## Evidence level required

`INFERRED`: the pads of every moved part are measured on the board frame against their goals, the copper
check judges the copper (`H-G-REUSE-FIT`, now with the net partition; `H-G-REUSE-ZONE`; `H-G-GROUP-MOVE`).
A KiCad case (`tests/kicad/reuse/test_group_oracle.py`) runs `kicad-cli` DRC on a turned group and records
`H-K-GROUP-DRC`; the 9.x side runs in CI.

## Impact

- `src/fenolite/reuse/fit.py`, `reuse/copper.py`, `cli/reuse_copper.py`, `cli/place_reuse.py`, a new
  `cli/place_group.py`, `cli/cmd_place.py`, `placement/codes.py`, `cli/data/explain.toml`.
- Tests: `tests/unit/reuse/`, `tests/unit/cli/test_place_group.py`, `tests/kicad/reuse/`.
- `docs/cli-contract.md`, `docs/placement.md`, `docs/hypotheses.md`, the evidence matrix, the guide's
  `placement` page and its generated `commands` page, `CHANGELOG.md`.
- c0175: `tasks.md` (tasks 8.4 to 8.6 moved), `proposal.md`, `design.md`, and its `layout-reuse` delta,
  removed. `openspec/README.md`: a row for c0227.
- Integration: c0210 must be archived before this change, because this change's requirements are ADDED to
  the `layout-reuse` capability that c0210 creates.
