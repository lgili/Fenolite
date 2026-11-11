# Design: c0492

## D1 What Altium stores

A stroke text record holds a position, a height, a stroke width, a rotation and a mirror byte. No
justification key is known (`pcb-records.md`). KiCad's importer anchors the text at its lower-left corner
(row `H-A-PCBX-KICAD`, ORACLE-VERIFIED for free texts). Fenolite's reading of the same position is the same
point, so only the justification is missing.

Task 1.1 checks the rest with `kicad-cli pcb import altium` on an authored document of component texts at
0°, 90°, 180° and 270°, on both sides, mirrored and not. For each one it compares the ink box of KiCad's
import with the ink box of Fenolite's conversion. The tolerance is one stroke width until a closer bound is
measured. The rows go in `pcb-records.md` with `H-A-IMP-TEXT-ANCHOR`.

## D2 Import

In `adapter/copper.py`, the component-text loop (`FootprintField(...)` and `Text(...)`) and the free-text
reader set `h_justify="left"`, `v_justify="bottom"`. A TrueType text (font type 1, change c0460) uses the
same anchor unless task 1.1 measures another. If it does, that is recorded in the row and the import uses
the measured one.

Content ids do not change: the id takes the position, not the justification.

## D3 Altium writer

`lower.py`'s `place(item, …)` computes the corner from the item's justification:

- `left`/`bottom`: the position as is.
- otherwise: the offset from the anchor to the box's lower-left corner in the text frame, from the ink box
  of `silk.extents` (glyph table, the `estimate` measure, no tool needed), turned by the text's rotation and
  mirrored as the text is.

The free-text refusal "the text record has no key for a justification other than centred" is removed for
stroke texts. A TrueType text with another justification keeps a refusal until its box is measured.

## D4 Round trip

An Altium → KiCad → Altium conversion keeps the justification `left bottom`, so D3 writes the same
position, and the record bytes match the source's (`H-A-PCBX-KICAD` frame). A field that KiCad users
re-justify goes through D3.

## Hypotheses registered by this change

| id | statement |
|---|---|
| `H-A-IMP-TEXT-ANCHOR` | an Altium stroke text record's position is the lower-left corner of its unrotated, unmirrored text box, so a KiCad text justified left and bottom at that position draws its ink where Altium does |
