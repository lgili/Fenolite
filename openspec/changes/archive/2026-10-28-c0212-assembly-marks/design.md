## Context

c0175's decision 8 plans text extents rendered with `kicad-cli pcb export svg`, a designator search with
obstacles per side, candidates at two angles and two sizes, a cost, a greedy start and best-response
sweeps, row alignment and `--keep`, then silkscreen clipping and test-point placement. The pieces exist:
the board frame of `backends.kicad.frame` (pads, courtyards), `backends.kicad.fields` (a field's anchor and
angle, `set_field`), the footprint items of `backends.kicad.fpitems`, the edge rings of
`backends.kicad.outline`, exact thick shapes in `geometry.thick`, and the mutation protocol. KiCad's own
facts on fields (`H-K-FIELD-FRAME`, `H-K-FIELD-JUSTIFY`) are verified; the ink of a text was not modelled
("KiCad's glyphs are not modelled", `fields.py`).

## Decisions

1. **Scope: ink extents and designators.** They are the core of the package and can be proved end to end
   by KiCad's DRC. Clipping changes footprints and needs the library-from-board path; test-point placement
   needs the copper clearance of new copper. Both stay with c0175 (proposal, "Non-goals").
2. **The ink comes from the tool that draws it.** A plot of `pcb export svg` writes each text as one
   `stroked-text` group of centre lines with the stroke width in its style (already used for sheet texts,
   `H-K-WKS-SVG`). Many texts are measured with one call: one `gr_text` per cell of a grid whose cells are
   wider than any text can reach, each group mapped back to the cell that holds its centre. The box is
   relative to the anchor, in the text's reading frame, for its own justification.
3. **The cache is keyed by the tool.** One JSON file per tool version, string, size, stroke and
   justification, under `$FENOLITE_CACHE_DIR/silk` (else the user's cache folder), written atomically; a
   file that cannot be read is a miss. A second run renders nothing.
4. **The estimate is measured, not transcribed.** `tools/measure_glyphs.py` measures, for each glyph of the
   designator alphabet (letters, digits, `-_.+/`), the boxes of `c` and `cc` centred: they give its advance
   and the left and right of its ink in its cell; the bottom of `H` gives the baseline, and `H` at other
   heights, strokes and justifications gives the baseline's stroke term and the shifts of a justification,
   each fitted on two points and checked on the others. The tool fails when a check misses by more than 1 µm.
   The table holds boxes and advances only, never a stroke of a glyph; `--check` and the oracle test
   measure it again. The estimate adds 1 µm on every side; an unknown glyph takes the widest metrics and
   grows the box by the spread of the advances, so the estimate only grows.
5. **A field's box on the board follows the verified frame facts.** The anchor is `field_anchor`, the
   angle `field_angle`; a mirrored text flips its box in x, a text at 180° or 270° is drawn as at 0° or 90°
   (keep upright), then the box turns as a footprint turns a point. Designators are written at 0° or 90° on
   the board, centred both ways, mirrored on the bottom, so their boxes are exact rectangles. Other texts
   are boxed by the box symmetric about their anchor, turned and boxed again: no upright rule or mirror can
   move ink out of it.
6. **Obstacles are thick shapes, per side.** Pad copper on the side's outer layer as the frame gives it,
   every pad and via hole and board hole, silkscreen strokes (arcs and circles polygonised and widened by
   their tolerance), other texts' rectangles, other parts' courtyard faces and the edge rings with their
   arcs. A text keeps `--clearance` (0.15 mm by default, above KiCad's default silkscreen clearance of 0)
   from all of them, measured exactly with `thick_closer_than`, and its centre lies in the board's material
   (an odd count of edge rings around it). A spatial index keeps the search linear in practice.
7. **Candidates beside the courtyard box.** For each look (height, from `--sizes` or the field's own then
   the project's least; angle 0 or 90), twelve places `--gap` away from the box of the own courtyard
   (pad hull without one): centred and flush with either end, on each side. The stroke keeps the field's
   ratio to the height, at least the least stroke, at most a quarter of the size. Identical parts get
   identical candidates relative to their boxes, so a common slot aligns their facing edges.
8. **Cost.** The distance to the own box, an eighth of the offset of the text's middle from the part's
   middle, twice the height below the largest, `ANGLE_COST` (0.5 mm) across the part's long side, and
   nearness to a foreign box: the shortfall below the own distance plus 0.3 mm, and `FOREIGN_COST` (10 mm)
   when a foreign box is nearer than the own one. Ties fall to the slot order (above, below, left, right).
9. **Search.** Groups first: footprints of one library name, angle, side and field size on one row (one
   y) or column (one x), largest first, each on the cheapest slot that every member takes free and apart.
   Then the other parts greedily, fewest statically free candidates first. Then up to four repair rounds:
   a part without a free candidate takes one blocked by a single placed text when that text has another
   free candidate. c0175's best-response sweeps are replaced by the repair: the cost of a candidate does
   not depend on the other texts, so a sweep could not improve a free choice. Last, a part left without a
   place keeps its text, which then blocks the others; a placed text that meets one moves on or gives up.
10. **`--keep`.** Every current text that meets nothing (and no other kept text) stays and is an obstacle;
    only the others are placed, without groups.
11. **Check before write.** The written design is judged on its own: each placed field is boxed again from
    the field (decision 5) and checked against every obstacle and every other designator with the
    clearance, the material, the least height and stroke of the project (`min_text_height`,
    `min_text_thickness` of `.kicad_pro`, else 0.8 mm and 0.08 mm), the angle and the mirror. A miss is
    `silk.check-failed` (error) and nothing is written. `--drc` then runs `kicad-cli` DRC on copies before
    and after, as `tidy` does: a grown type is `silk.drc-new`, otherwise the reply is `KICAD-VERIFIED`.
12. **No placement record.** A rebuild that merges the board keeps its fields (`lens.fields.merge_fields`:
    a board's field wins over an unlocked request), so `silk-placements.toml` of c0175 is not written.
13. **The agent guide's generated budget grows to 700 lines.** The generated `commands` page lists every
    option of every command; with `silk` it holds 609 lines, and integrated on 2026-10-28 with the MCP
    commands of `dev` and the changes c0213 to c0224 it holds 661. The page is generated and read in parts,
    so the limit is raised rather than options hidden. For the same reason the skill folder may hold
    300 000 bytes instead of 260 000: with c0225 to c0227 it held 260 336.

## Risks / Trade-offs

- The glyph table and the layout constants are measured on 10.0.7. A KiCad release that changes the font
  or the layout makes `tools/measure_glyphs.py --check` and the oracle test fail; with a tool present the
  measurement is used anyway, so only estimates go stale.
- A text box is a rectangle around the ink, not the strokes: two texts may be kept apart by more than
  their glyphs need. That costs room, never a collision.
- The search is local: a dense board may leave parts unplaced that a global search would fit. Each is
  reported with what blocks its best place.

## Migration Plan

None: a new command and a new package.
