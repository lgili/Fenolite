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
| own footprint's silk strokes | blocks | blocks | blocks (field result, D6) |
| other silk strokes and texts + `clearance` | blocks | blocks | blocks |
| plated holes | blocks | blocks | blocks (through the mask opening) |
| unplated holes | blocks | blocks | not an obstacle |
| hidden designators | skipped | skipped | skipped |

In the `altium` model a text's box is its ink and the box Altium measures (`text_box`, revised by D6;
`H-A-SILK-DRC-MODEL`). `check_designators` judges with the same model
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

## D5 Texts already below the minimum (field result, 2026-11-17)

On the maintainer's board the search placed every designator it could, but 23 of them kept their own
height (0.5 to 0.7 mm), below the board's 0.8 mm minimum: `looks_of` never grows a text, so a field below
the floor has one height, its own. `check_designators` then failed them and nothing was written.

Decision (maintainer, 2026-11-17): a placed designator whose height and stroke are the field's own is not
judged by the minimum size. It is a finding the board already had: `silk.below-minimum` (warning), and the
board is written. A size the search chose is still judged, so a text it made too small stays
`silk.check-failed`. The search does not enlarge a text: that changes the board's style and may not fit.
Back-compatible: a board whose texts meet the minimum gives the same reply. Not taken: taking the board's
own least size as the minimum for every text, which would hide the finding.


## D6 The board's rules and the models measured in Altium and KiCad (field result, 2026-11-17)

Altium 24.5's DRC on the board written by D1 to D5 (`--model altium`) gave 237 silk violations against 24
before; KiCad 10.0.6 agreed. Four causes, each fixed in shared code:

1. The clearances ignored the board's rules (0.15 mm). `cmd_silk.clearances` takes `--clearance` and
   `--mask-clearance` from the largest `silk_clearance` rule of the `.kicad_dru` (KiCad judges silkscreen to
   a mask opening by the same constraint), else the project's `min_silk_clearance` above 0, else the
   defaults; `result.settings.sources` names the source of each value.
2. The text box was too small. Both tools measure at least the whole ink; Altium measures a box from half a
   stroke outside the stored corner, about one height per character along the text and `height + 2 ×
   stroke` across (`H-A-SILK-DRC-MODEL`, fitted to the report: 136 of 137 pad distances at or above the
   model's). `measured` (ink less half its stroke) is replaced by `text_box`: the ink, and in the `altium`
   model also `altium_box`, from the same corner `pcbdoc.text_corner` writes.
3. Altium judges a text against its own component's silkscreen (46 of 63 text-to-track violations), so the
   `altium` model no longer skips it.
4. An unplated pad that opens the mask is an opening for both tools (`mask_openings`, shared with
   `judge_silk`).

KiCad's courtyard findings come from the board's rule, not from our model of the courtyard: a
`silk_clearance` rule with no condition and no layer clause reaches every item of the side
(`H-K-SILK-REACH`): courtyards, copper tracks, zones, vias and visible fabrication-layer fields.

Decision (maintainer, 2026-11-17): when such a rule exists (`Settings.courtyard`), every courtyard, the
part's own too, is kept that rule's distance, and `--gap` defaults to at least it, counted from the
courtyard's ink (the box grows by half the courtyard's stroke). Copper under the mask and fabrication texts
stay out of the search: they do not print, Altium's silk rules do not judge them, and a designator could
not keep clear of a pour. KiCad reports them on the board as it was too; the rule translation is the place
to narrow them (follow-up). Not taken: courtyards blocking without such a rule (the dense bench of D1).
