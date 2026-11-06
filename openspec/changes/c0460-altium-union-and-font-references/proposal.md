# c0460: union members and TrueType texts keep their references through KiCad

## Why

c0450 carries `UnionNames` and `EmbeddedFonts6` through KiCad byte for byte. In Altium Designer 24.5, the
round trips of rows `-01` and `-04` still list no union and no TrueType text (S-2180): the storages
come back, but nothing refers to them any more. The census of the eight public rows (S-2190) shows where
the references live:

- **Union members.** A via holds its union index as a 32-bit value at offset 70 of its record. 596 vias in
  four rows do (`-02` 160, `-04` 22, `-06` 7, `-08` 407). A region of `Regions6` and of
  `ShapeBasedRegions6` holds it as `UNIONINDEX` (rows `-01`, `-05`, `-08`), and so does a component of
  `Components6` (`-08`, 7). The round trip writes 0 in every one of them.
- **Smart unions.** Rows `-02`, `-03`, `-04`, `-06`, `-07` and `-08` hold `SmartUnions` records: via
  stitching definitions with placement coordinates in the source's frame (`PLACEHOLDERX`). Nothing carries
  or counts them.
- **TrueType texts.** A text of font type 1 names its font (offset 43 the type, 46 the name). Rows `-01`,
  `-02`, `-04`, `-06`, `-07` and `-08` hold such texts, as designators, footprint texts and free texts. The
  import ignores the font type, so each becomes a stroke text. The writer refuses a text with a font face.

## What

- **TrueType texts keep their font.** The import gives a text, a footprint text and a designator or comment
  field of font type 1 the font name as `face`, with its bold and italic bytes. The writer writes a text
  with a `face` as font type 1 with that name, bold and italic, in the record's long form, and no longer
  refuses it.
- **Union members keep their union.** The import records a via's, a region's and a component's non-zero
  union index in the item's `altium` bag. The conversion to KiCad carries the index of every member as one
  board property `Fenolite.Altium.UnionMembers`, by the KiCad uuid of the item. The conversion back writes
  each index into its member's record. An item KiCad no longer holds is a member no more.
- **Smart unions are counted lost.** `SmartUnions` is frame-bound (c0459): it is not carried, and each one
  that holds data is counted lost under `altium-storage`.

## Impact

- Specs: `altium-import`, `altium-pcb-writer`, `design-conversion`.
- Code: `backends/altium/adapter/copper.py`, `backends/altium/adapter/board.py`,
  `backends/altium/pcbdoc.py`, `backends/altium/pcbrecords.py`, `convert/altium_storages.py`,
  `convert/to_kicad.py`, `convert/to_altium.py`.
- Docs: `pcb-records.md`, `docs/hypotheses.md`, `docs/evidence/sources.md` (S-2190 onwards), CHANGELOG.
