# c0493: `fenolite silk --designators` places designators on dense boards

Found on: reviewing a private maintainer board on 2026-11-11 (codes only; nothing from the board is in
this change).

## Why

On a dense board, `fenolite silk --designators` placed only a small part of the designators, even with a
0.8 mm height and a 0.05 mm gap. The rest got `silk.no-place`. The board's designators fit in Altium, and
Altium's DRC passes them.

Reading `silk/board.py` (`gather`) and `silk/layout.py` (`_offsets`, `candidates`) gives these causes:

1. **Too few places.** There are twelve candidates per look, all on one ring `gap` outside the box of the
   part's own courtyard. On a dense board that ring overlaps a neighbour's courtyard on every side. There is
   no second ring and no place over the part's own body.
2. **Courtyards are obstacles.** Other parts' courtyards block a designator. Neither Altium's silkscreen
   rules nor KiCad's silkscreen tests judge text against a courtyard.
3. **Pad copper, not the mask opening.** Pads are obstacles by their copper grown by `--clearance`. Altium
   judges silk against the solder-mask opening, each pad with its own mask expansion. `--clip` already uses
   that opening.
4. **Its own silk blocks a text.** A footprint's own silkscreen strokes have no owner in `gather`, so they
   block its designator. Altium 24 does not check a text against the silk of its own component.
5. **Few sizes.** Without `--sizes` the looks are the field's height and the board's least height.

When a designator stays unplaced, the reply says so but does not group the reasons. A user cannot tell
"no room anywhere" from "one neighbour's courtyard".

## What Changes

- **Candidates.** For each look: places on all four sides of the part's own box at increasing distances,
  in steps up to a reach. The ring at `gap` comes first, then up to `--reach`, by default 2 mm.
  Each side holds a centred place and two flush ones. Places over the part's own body come last and are
  used only with `--over-body`. Angles are 0° and 90° as today. Heights go from the field's height down to
  `--min-size` in steps of `--size-step`. The defaults are the board's least text height and 0.1 mm.
- **Clearance model.** A new `--model kicad|altium` option, default `kicad`, which keeps today's model.
  - `kicad`: today's obstacles, minus other parts' courtyards. Courtyards only add cost, as nearness to a
    foreign part does today.
  - `altium`: the model Altium 24's silk-to-silk and silk-to-solder-mask rules measure.
    - Silk to silk 0.15 mm, or `--clearance`.
    - Silk to mask: each pad's mask opening, its copper grown by its own solder-mask expansion, with the
      silk-to-mask clearance of `--mask-clearance`.
    - A text box is its bounding box minus half its stroke width on each side.
    - A text does not see the silk of its own component.
    - Hidden designators are neither placed nor obstacles.
    - An unplated hole is not an obstacle.

    Each of these is recorded as a hypothesis row until a kit run confirms it.
- **Report.** Each part left unplaced gets one `silk.no-place` with the obstacle that blocked its cheapest
  place (the existing `_blocker`) and the kind of that obstacle. `result.unplaced` counts the parts by that
  kind.
- **Trimming the footprint silk.** `--clip` already cuts silkscreen strokes at mask openings with each pad's
  own expansion. With `--designators --clip`, the clip runs first and the search sees the clipped silk.
  `result.clip.footprints` gives one row per footprint with the strokes cut and the pieces dropped.

## Impact

- `src/fenolite/silk/layout.py` (`_offsets`, `candidates`), `src/fenolite/silk/board.py` (`gather`,
  `Settings`, `looks_of`, `check_designators`), `src/fenolite/silk/clip.py` (the per-footprint rows).
- `src/fenolite/cli/cmd_silk.py` (options), `src/fenolite/agent/skill/references/` (the silk page, then
  `tools/gen_agent_guide.py`).
- `docs/assembly.md`, "Designators".
- Under `--model kicad`, a board whose designators were all placed before keeps the same places, except
  where a foreign courtyard was the only blocker.
