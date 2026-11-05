# c0410: Keep-Out layer areas forbid pads; library keep-outs give no copper

## Why

c0407 left two follow-ups.

- **Pads.** `convert` turns each Keep-Out layer drawing of an Altium board into a rule area that forbids
  tracks, vias and pours, but not pads. KiCad 10.0.6's `pcb import` forbids pads as well, for keep-out
  tracks and for keep-out regions. Altium's documentation (S-1710) says a Keep-Out layer keep-out applies on
  every copper layer.
- **Library keep-outs.** A keep-out on copper in a PcbLib footprint, or a polygon cut-out there, becomes a
  copper graphic of the footprint. Every board that places the footprint then gets copper where Altium has a
  keep-out. `FootprintDef` holds no rule area, so the model cannot keep it as one yet.

## What

- The rule areas that `convert` makes of Keep-Out layer drawings also forbid pads.
- A keep-out track, arc, fill or region on copper, and a polygon cut-out on copper, Keep-Out or Multi-Layer,
  of a library footprint gives no graphic:
  - it is counted under the new census category `footprint-keepouts`;
  - the hint of `altium.import.unmapped` names change c0411, which adds rule areas to footprint
    definitions.
- New measurements, recorded in `pcb-records.md` (S-0161, S-0020, S-1710):
  - what `fp upgrade` 10.0.6 makes of a library's keep-outs;
  - what `pcb import` makes of the older unflagged Keep-Out drawings.
- Two oracle tests:
  - the board areas match KiCad's, restrictions included;
  - the library areas KiCad makes are pinned for c0411.

## Impact

- **Code:** `convert/altium_to_kicad.py` (`keepouts`) and `backends/altium/adapter/copper.py`
  (`definition_graphics`, `library_keepout`).
- **Issue output:** `backends/altium/adapter/codes.py` gains a hint on `altium.import.unmapped`.
- **Public surface:** no public name, CLI argument, issue code or model field changes.
- **Behaviour:** a converted Altium board's Keep-Out areas now also report pads inside them, and a PcbLib
  import loses those primitives as a reported loss instead of making copper.

## Not here

| item | owner |
|---|---|
| Rule areas in a footprint definition (`FootprintDef.keepouts`), their `.kicad_mod` and PcbLib writers, and carrying them when a definition is placed | c0411 (Fenolite) |
| The restrictions a Keep-Out layer region holds (`KEEPOUTRESTRICTIONS`, such as 24 for pads only): the adapter keeps such a region as a graphic, so `convert` forbids all four | a later change (Fenolite) |
| Level 3 comparing a slot's length and axis; the Altium kit case for a slot shorter than its hole | later (coordinator) |
