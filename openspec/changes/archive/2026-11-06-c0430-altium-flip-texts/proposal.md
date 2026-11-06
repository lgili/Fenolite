# Altium flip moves the texts' long layer ids

## Why

The maintainer flips parts to the bottom with Fenolite's Altium edit session, then edits the board in Altium.
In Altium Designer 24.5, a part flipped that way reads Bottom Layer, but its designator and comment stay on
Top Overlay (S-1890, Part J case J9). The part looks as if it were still on the top, which blocks the
board editing.

The edit session flips a board that Altium saved. Altium saves a text record of 232 or 252 bytes with the
long layer id of its layer at offset 226. It saves a pad's fifth subrecord of 170 to 194 bytes with that id
at offset 114 (S-1891). Like a long track (case J23, S-1588), Altium shows the primitive on the layer its
long id names. `relayer` changed the layer byte of a text or a pad alone, so the designator and comment kept
Top Overlay. A saved SMD pad would also have kept Top Layer.

## What Changes

- `edit.records.LONG_LAYER` records the long layer id of a text (232 bytes and longer, offset 226) and of a
  pad (170 bytes and longer, offset 114). `SHORT_FORM` records the forms Fenolite writes (137 and 114),
  which hold none.
- `relayer` therefore moves the long layer id of a text and of a pad with its layer byte. That holds for
  `flip` and for every other layer move of a session. `on_layer` reads a saved text by its long id.
- Tests on authored saved forms: a flip from top to bottom and back, with every text and pad record
  restored byte for byte. Also a test that the Altium write puts a bottom part's designator and comment on
  Bottom Overlay, mirrored.
- Docs: `pcb-records.md` and `pcb-document.md` rows, sources S-1890 to S-1892, and the status of
  `H-A-EDIT-FLIP`.

The Altium writer and the KiCad writer already put a bottom part's fields on the bottom overlay, mirrored.
`place_footprint` puts them on `B.SilkS`, the KiCad writer writes `(justify mirror)`, and the Altium writer
writes each field on its layer with its mirror flag. Those paths change nothing here.

- **Mechanical pairs.** Altium's own J9 save keeps `D1`'s Mechanical 13 and 15 drawings where they were,
  because the board declares no mechanical pair. Fenolite's flip used to move them to Mechanical 14 and 16.
  `flip` now builds its layer map from long layer ids. Copper, overlay and Multi-Layer swap as before; a
  mechanical layer swaps only within a pair declared by `MECHPAIR<i>L1` and `L2` in `Board6`, including
  pairs above Mechanical 16. Any other mechanical layer stays where it is.
- **The DSL path.** A part placed with `side="bottom"` in a design script comes out of
  `fenolite build --target altium` with its designator and comment on Bottom Overlay, mirrored, in the
  137-byte form without a long id. Altium saves such a text with the long id of Bottom Overlay (S-1893).
  A test pins this path.

## Out of scope

- Paste and solder-mask primitives of a component are not in `FLIP_PAIRS`.
- The Altium writer declares no `MECHPAIR` for the mechanical layers that Fenolite uses for the front and
  back fab and courtyard (13/14, 15/16). Until it does, Altium's flip of a part written by Fenolite keeps
  those drawings on their layers.
