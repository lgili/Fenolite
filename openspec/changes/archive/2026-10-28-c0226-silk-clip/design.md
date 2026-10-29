## Context

c0175's design, package 8, plans `fenolite silk BOARD --clip`: cut silkscreen strokes at every mask
opening, with a margin, the footprints' own graphics too, so the change must reach the library. What
exists:

- `fenolite silk --designators` (c0212): the command, the mutation protocol, `--drc` before and after, the
  benches of `tests/_silkbench.py`, the codes `silk.*`.
- A board footprint keeps its `fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly` children as opaque
  slots written back verbatim; `backends.kicad.fpitems.footprint_items` projects them read-only (c0126).
  Board graphics (`gr_*`) are modelled `Graphic` entities.
- `backend.board_pads` gives each pad's copper per copper layer and its hole in the board frame;
  `Pad.mask_margin` holds a pad's `solder_mask_margin` (c0223).
- `fenolite library BOARD --out LIB.pretty` makes a library of the board's footprints, one per name, and
  `library.instances-differ` names a second footprint `<name>_2` when two instances differ; `--diff LIB`
  reports `silkscreen` drift (c0223).
- Exact thick shapes and `thick_closer_than` (`geometry.thick`).

## Decisions

1. **What KiCad measures (probed first).** With `kicad-cli` 10.0.7 on an authored one-pad board:
   `silk_over_copper` ("Silkscreen clipped by solder mask") is reported when silkscreen ink meets the
   copper of a pad that has a mask opening on that side; a stroke touching the copper is not reported, one
   1 µm over it is. A pad without the side's mask layer is not checked. The mask expansion (the pad's
   `solder_mask_margin` or the board's `pad_to_mask_clearance`, both drawn in the `F.Mask` plot) does not
   widen the check. The board's `min_silk_clearance` does not apply to it; a `silk_clearance` rule of the
   `.kicad_dru` does, and the report names its limit and the distance to the copper. Recorded in
   `docs/formats/kicad/drc.md`, "Silkscreen over pads" (`H-K-SILK-MASK`).
2. **An opening is what the fabricator clears.** For each side, every pad whose layers hold that side's
   mask (`F.Mask`, `B.Mask` or `*.Mask`): its copper on the side's outer layer, grown by its mask
   expansion when that is positive (the pad's `mask_margin`, else the board's `pad_to_mask_clearance`);
   and every pad's hole on both sides. This holds KiCad's copper, so the DRC is cleared, and also the
   grown opening that the fabricator clips anyway, so the board shows the ink that will be printed.
3. **Margin.** `--margin LENGTH`; by default the largest `min` of the `silk_clearance` rules of the
   `.kicad_dru` beside the board, else 0, since that rule is what KiCad applies (decision 1). The cut keeps
   the ink `margin + 1 µm` from every opening: the 1 µm absorbs the rounding of a cut end to the nanometre.
4. **The cut.** A stroke is cut on its centre line: a point stays when it lies at least `margin + 1 µm +
   width / 2` from every opening. A line is cut per piece of an opening's core (a capsule) and per filled
   region, in double precision (correctly rounded operations and square roots only, so every platform
   gives the same pieces; the 1 µm guard holds the error, and decision 6 checks each piece exactly); an arc or a circle on its polygon of 1 µm sagitta with the reach grown
   by the sagitta, each kept run written as an arc whose three points are its ends and middle projected
   on the true circle. The outline of a rectangle or a polygon is cut as its sides. A piece shorter than
   its stroke width is dropped. An uncut item is left as it is, byte for byte; a cut one becomes `line` and
   `arc` pieces with the original's stroke, layer and other children. A filled shape that meets an opening
   is not cut (`silk.clip-skipped`).
5. **Writing.** A board graphic is replaced in the model by its pieces, which take the original's slots
   without `fill`. A footprint's cut child is replaced, at its place among the footprint's opaque slots,
   by one `fp_line` or `fp_arc` per piece. Each piece gets the uuid `uuid5(FENOLITE_NS,
   "silk-clip:<old uuid>:<n>")`, so a run again gives the same bytes.
6. **Check before write.** Every written piece is judged again from what was written: its stroke as a
   thick shape (an arc on its polygon, widened by the sagitta) must not come within the margin of any
   opening of its side. A miss is `silk.check-failed` and nothing is written.
7. **The library stays in step.** A footprint's own graphics are cut first by the openings of its own
   pads only, once per group of instances that share the footprint name, side, silkscreen children (uuids
   aside) and pads, on the first of them in reference order, and the same pieces are written into every
   member. So `fenolite library BOARD --out LIB.pretty` makes one footprint of them, and `--diff LIB`
   reports its `silkscreen` drift against the old library. Each changed footprint name is one
   `silk.footprint-changed` (info) naming its references, and `result.library` holds the changed names
   and the command to run. The openings of other parts then cut the instance further; such a cut depends
   on the placement and makes that instance differ from the others (`silk.cut-by-other`, warning: the
   parts are too close, and `fenolite library` would derive `<name>_2`). The rebuild of a design script
   places footprints from the library, so the library must be written before the next rebuild; the board
   alone does not carry the cut back.
8. **With `--designators`.** The clip runs first, on the design as read; the designator search then reads
   the clipped strokes (`footprint_items` projects the new slots) and its own check runs as in c0212.
9. **Evidence.** Without `--drc`: `INFERRED` with `H-K-SILK-CLIP` and `H-K-SILK-MASK` (and the hypotheses of
   the designators when asked). With `--drc` and no new finding: `KICAD-VERIFIED`. The oracle test runs the
   clip on authored benches whose outlines cross their pads and their neighbours' pads, and asserts
   `silk_over_copper` before and none after, with `silk_overlap` and `silk_edge_clearance` not grown.

## Risks / Trade-offs

- A cut by another part's opening is right for the board and wrong for the library: it is reported, and
  the remedy is to move the parts apart.
- Arcs are cut on a polygon: a cut end may lie up to 1 µm earlier than an exact cut would put it.
- The grown opening (decision 2) cuts more than KiCad's DRC asks; it is what the fabricator removes.

## Migration Plan

None: new options of an existing command.

## Open questions

None.
