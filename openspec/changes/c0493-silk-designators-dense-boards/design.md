# Design: c0493

## D1 Candidates

`layout._offsets(look, box, gap)` today returns twelve `(side, offset, anchor)` on one ring. It becomes
`_offsets(look, box, gap, reach, step)`. It returns, for each distance `d` in `gap, gap + step, …, reach`,
the twelve places at `d`, keeping the slot `(side, offset, ring)`. The default `step` is the look's height.
With `over_body`, it then returns the five places inside the box: the centre and the four flush corners. A
place's cost grows with `d`, as `own` does today. A place over the body costs `OVER_BODY_COST` more, so it
is used only when nothing outside fits.

`looks_of` builds the heights from the field's height down to `min_size` in steps of `size_step`, largest
first, each at 0° and 90°. The search already prefers larger looks (`2 * (largest - look.height)`).

The number of candidates grows with `reach / step`. The search is greedy per part, with a spatial index,
so the cost stays linear in candidates. Task 1.4 measures it on the authored dense bench and keeps it under
the existing `tests/unit/silk` time budget.

## D2 Clearance models

`Settings.model` is `kicad` or `altium`. `gather` builds obstacles per model.

| obstacle | kicad (today) | kicad (this change) | altium |
|---|---|---|---|
| other parts' courtyards | blocks | cost only | cost only |
| pad copper + `clearance` | blocks | blocks | not used |
| mask opening (pad copper grown by its own expansion, as `silk.clip` computes it) + `mask_clearance` | not used | not used | blocks |
| own footprint's silk strokes | blocks | blocks | owned: does not block its own text |
| other silk strokes and texts + `clearance` | blocks | blocks | blocks |
| plated holes | blocks | blocks | blocks (through the mask opening) |
| unplated holes | blocks | blocks | not an obstacle |
| hidden designators | skipped | skipped | skipped |

In the `altium` model a text's box is its ink bounding box shrunk by half its stroke on each side. That
is the rectangle Altium measures (`H-A-SILK-DRC-MODEL`). `check_designators` judges with the same model
that placed the texts, so a placed text never fails its own check.

KiCad's own DRC still runs with `--drc`. A board placed with `--model altium` may give KiCad
`silk_over_copper` findings that Altium does not. The reply says which model was used.

## D3 Report

`silk.no-place` gets `where` = the reference and a message naming the blocker of the cheapest place. It
also gets one of the closed kinds `pad`, `mask`, `hole`, `silk`, `text`, `courtyard`, `edge`, `outside`.
`result.unplaced` is `{kind: count}`.

## D4 Clip per footprint

`ClipOutcome.rows` already has one row per owner. `cmd_silk` exposes the footprint rows as
`result.clip.footprints`: `{ref, strokes_cut, pieces, dropped}`. With `--designators --clip` the clip runs
first. Its design is the one the search reads, and both go through one plan.

## Hypotheses registered by this change

| id | statement |
|---|---|
| `H-A-SILK-DRC-MODEL` | Altium Designer 24's silk-to-silk and silk-to-solder-mask rules measure a stroke text by its bounding box shrunk by half its stroke width on each side and a mask opening by each pad's own expansion, ignore a text against its own component's silk, and leave out hidden designators and unplated holes |
