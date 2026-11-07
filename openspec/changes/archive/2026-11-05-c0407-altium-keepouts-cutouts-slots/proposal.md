# c0407: Altium keep-out tracks, polygon-cutout regions and slot drills

## Why

A rebuild of a private Altium board on 2026-11-05 found three import defects. One of them puts copper on
a fabricated board:

- **B2 (critical, fabrication).** A polygon cut-out (a region of `KIND=1`) on a copper layer without a net
  became a filled copper graphic. In Altium it only keeps poured copper away. `fenolite import` and
  `fenolite convert` then wrote solid copper there.
- **B1 (high).** A closed ring of keep-out tracks on the Keep-Out layer became one filled rule area over
  everything inside the ring. An Altium keep-out track keeps out the band its width covers. KiCad 10.0.6's
  `pcb import` writes one rule area per track, a band of the track's width with round ends.
- **B3 (low).** Level-3 `equivalent` reported `pad-drill` for slotted pads. The Altium record held a slot
  length (1.0 mm) below its hole size (2.15 mm). The model kept 2.15 mm as the drill. KiCad's file holds the
  same oval as 1.0 × 2.15 mm and reads back drill 1.0 mm. The check compared one side's length with the
  other side's width.

Reading the code turned up **B4**, the same fault as B2. A track, arc, fill or region whose keep-out flag
is set (second flag byte 2) on a copper layer became copper, both as a free primitive and as one of a
component.

## What

- The Altium adapter turns each of these into a rule area, never copper:
  - a polygon cut-out: a rule area that forbids poured copper. It is on its copper layer, or on every
    copper layer when it lies on the Keep-Out or Multi-Layer layer.
  - a keep-out primitive on copper:
    - a track or arc gives the band its width covers;
    - a fill or region gives its outline;
    - each is on its own layer. A region keeps its restriction value; the others take every restriction.
  - A keep-out primitive of a component becomes a rule area of the board.
- `convert` turns the drawings of the Keep-Out layer into one rule area per stroke on every copper layer:
  a line, arc or circle becomes the band of its width; a filled shape stays one area. A stroke of width 0
  covers no area and is reported as a loss.
- A new geometry module `fenolite.geometry.bands` gives the band of a segment or a three-point arc, in
  integers.
- Level 3 compares the width of each pad's hole. For a slot that is the shorter of `Pad.drill` and
  `Padstack.hole_length`.
- `pcb-records.md` records what KiCad 10.0.6 imports for each case (ORACLE-VERIFIED, 2026-11-05).

## Impact

- **Code:**
  - `backends/altium/adapter/copper.py`, `context.py` and `board.py`;
  - `convert/altium_to_kicad.py`;
  - `checks/equivalence/norm.py` and `levels.py`;
  - the new `geometry/bands.py`.
- **Imported boards:**
  - an Altium board now carries `Board.keepouts` from its cut-outs and copper keep-outs;
  - the ledger reason "a closed keep-out outline becomes a rule area" is replaced by two reasons (a filled
    shape, a track band);
  - "a keep-out line that encloses no area" becomes "a keep-out line that covers no area".
- **Public surface:** no public name, CLI argument, issue code or model field changes.

## Not here

| item | owner |
|---|---|
| The restrictions of a Keep-Out layer drawing in `convert`. Since c0375 they are tracks, vias and pours; KiCad 10.0.6 also forbids pads. A region's own `KEEPOUTRESTRICTIONS` is not carried through the graphic | a follow-up change (Fenolite) |
| A keep-out primitive on copper in a footprint of a library (`PcbLib`), whose model has no rule areas | a follow-up change (Fenolite) |
| Level 3 does not compare a slot's length or axis | a follow-up change (Fenolite) |
| The Altium adapter keeps a slot shorter than its hole as read; how Altium Designer reads such a record is not known from any source | Altium kit case (maintainer) |
