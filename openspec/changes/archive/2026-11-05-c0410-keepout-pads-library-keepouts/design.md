# Design: c0410

## Evidence (KiCad 10.0.6, 2026-11-05)

- **`pcb import`** of the c0407 document: the band of each flagged Keep-Out track forbids tracks, vias, pads
  and pours. So does a flagged Keep-Out region that holds only Altium's `KEEPOUTRESTRICTIONS=24`, because
  KiCad reads `KEEPOUTRESTRIC` and takes 31 when that key is absent.
- **The older form**, a Keep-Out layer track or arc without the keep-out flag: KiCad imports it as a band
  that forbids nothing. A region there without the flag or keep-out keys becomes copper polygons on `F.Cu`
  and `B.Cu`.
- **`fp upgrade`** of an authored PcbLib makes rule areas of the footprint:
  - a flagged track on Top: a band on `F.Cu`, every restriction;
  - a flagged track on Keep-Out: a band on every copper layer, every restriction;
  - a `KIND=1` region on Top: a pour-only area on `F.Cu`;
  - a flagged region on Bottom with `KEEPOUTRESTRIC=3`: tracks and vias on `B.Cu`;
  - an unflagged Keep-Out track: a band forbidding nothing.

## Decisions

1. **Every Keep-Out layer area forbids tracks, vias, pads and pours,** flagged or not.
   - Altium says a Keep-Out layer keep-out applies on every copper layer (S-1710).
   - KiCad's import of the form Altium writes now (flagged) forbids all four.
   - For the older unflagged form, KiCad's import is no guide: it forbids nothing, or makes copper. Fenolite
     keeps the Altium reading, recorded as `INFERRED`.
   - `test_keepout_import` compares the restrictions of all six areas with KiCad's.
2. **Library keep-outs are a reported loss until c0411.**
   - The adapter tests each library primitive before it makes a graphic, with the same predicates as the
     board import (`is_keepout`, `is_polygon_cutout`).
   - A match is skipped under `footprint-keepouts`. The census already turns every skipped category into
     one `altium.import.unmapped`; a category-to-hint table adds the c0411 hint when that category is
     present.
   - Drawings of the Keep-Out layer in a footprint stay graphics of `Altium.KeepOut`, as on a board.
3. **The `fp upgrade` result is pinned by a test now.** The authored library and the expected areas then
   carry over to c0411's proof without a new measurement.

## Changed expectations

The keep-out tests of c0407 now also check pads: the unit test asserts `no_pads`, and the oracle test
compares the full restriction tuples.

c0407's own consequence was missed by its focused run and is fixed here:

| test | before | after | reason |
|---|---|---|---|
| `test_altium_import::test_footprint_items_conserve_the_census` | graphics + fields + texts == carried | the same sum plus the component keep-outs and cut-outs made rule areas == carried | c0407: a keep-out of a component on a signal layer is a board rule area; `-04` holds two keep-out arcs on Top (315 = 280 + 30 + 3 + 2) |
