# Design: c0407

## Evidence

The authored document `tests/_altium_keepouts.py` holds three things on a 60 × 40 mm board:

- a ring of four keep-out tracks on layer 56, 1 mm wide;
- a keep-out track on Top, 0.5 mm wide;
- a `KIND=1` region on Top without a net.

KiCad 10.0.6's `pcb import` of that document (2026-11-05) gives six rule areas:

- each ring track: a band of its width with round ends, on `F.Cu` and `B.Cu`, where tracks, vias, pads and
  pours are not allowed;
- the Top keep-out track: the same band on `F.Cu` alone;
- the region: its outline on `F.Cu`, where only pours are not allowed.

The probe documents of `_altium_slotcases` show where KiCad puts a `KIND=1` region on the other layers. On
the Keep-Out (56) and Multi-Layer (74) layers it gives a pour-only area on every copper layer.
`tests/kicad/altium/test_keepout_import.py` compares KiCad's areas with Fenolite's: same layers, boxes
within 10 µm and areas within 1 %. The rows go to `pcb-records.md` as `ORACLE-VERIFIED(kicad-cli)`.

Public corpus: the two rows below now import as rule areas. Before this change each region was copper of
its layer, or a graphic of layer 74.

| row | `KIND=1` regions |
|---|---|
| `altium-third-party-pcbdoc-01` | Top 1, Bottom 1 |
| `altium-third-party-pcbdoc-06` | Top 8, Bottom 2, Multi-Layer 3 |

## Decisions

1. **The adapter makes the rule areas of copper keep-outs and cut-outs.** A keep-out on a copper layer is
   never copper, so the reader must not hand it on as copper for a later stage to repair.
   - `import --to python` and `convert --to kicad` share the adapter, so both get the fix.
   - The areas go to `Context.keepouts` and from there to `Board.keepouts`. The record functions keep their
     signatures.
   - A primitive of a component on copper becomes a rule area of the board in the board's frame. The model
     has no rule areas in a footprint.
2. **Drawings of the Keep-Out layer stay graphics in the adapter.** The import keeps the document's drawing
   on `Altium.KeepOut`, and `convert` makes the rule areas, as since c0375.
   - Each stroke is one area: the band of its width. KiCad writes it the same way, and a ring of tracks then
     keeps out only its own copper.
   - Only a filled shape (a region or a fill) is one area of its outline. So is a closed outline of width 0,
     which can only be an outline.
   - The joining of strokes into rings (`assemble_rings`) is gone.
3. **Restrictions.**
   - A polygon cut-out forbids pours alone (value 4).
   - A keep-out region on copper keeps its own value: `KEEPOUTRESTRICTIONS` first, then `KEEPOUTRESTRIC`.
   - A track, arc or fill holds no value and takes 31, every restriction, as KiCad does.
   - The pad bits follow the writer's `KEEPOUT_BITS`: pads are forbidden only when bits 8 and 16 are both
     set.
   - The Keep-Out layer drawings in `convert` keep their set (tracks, vias, pours); changing it is out of
     scope (proposal, "Not here").
4. **Bands in integers.**
   - `geometry.bands` offsets each point by half the width along the exact unit normal, rounded once to
     the nearest nanometre.
   - Each round end and each arc side is polygonised by `CurvedRing` within the conversion's chord error
     (5000 nm). The polygon is inscribed.
   - A circle is two half bands, because the model's rule area has no hole.
   - An arc whose radius is at most half its width has no band: the adapter counts it as bad geometry, and
     `convert` reports it as a loss.
5. **Slot widths.**
   - The model holds a slot as its width (`Pad.drill`) and its longer overall length. An Altium record may
     hold the slot length below the hole size, and the adapter keeps both numbers as read.
   - Level 3 compares `norm.drill_width`, the shorter of the two numbers, so a width is compared with a
     width.
   - Whether the adapter should swap the two numbers needs to know how Altium Designer reads such a record.
     No source says, so it is left for a kit case.

## Changed expectations

| test | before | after | reason |
|---|---|---|---|
| `test_to_kicad::test_altium_keepout_closed_and_open` | the 0.1 mm line was a loss | it is a band rule area, and a width-0 line is the loss | B1: a keep-out track keeps out its band |
| `test_convert_altium_census` `-01` | 20 `graphic` losses | none | B1: its 12 lines and 8 arcs on the Keep-Out layer are bands |
| `test_convert_altium_census` `-06` | 3 graphics of `Altium.74`, 3 `graphic` losses | none | B2: three polygon cut-outs on Multi-Layer are rule areas |
