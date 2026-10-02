# Drawing-sheet figures (paper sizes, frames, title blocks)

The figures that Fenolite's shipped sheet examples (`src/fenolite/templates/examples/`) may use, written
in Fenolite's own words. Each row cites a source registered in `docs/evidence/sources.md`. The ISO
5457:1999 and ISO 7200:2004 public previews (S-0077, S-0078) are copyrighted documents shown by a
distributor: their figures are read as facts only, and no text or figure of a standard is reproduced.
Full copies of the standards found elsewhere are never consulted, and no KiCad sheet (its default sheet
or the kicad-templates sheets) is read. No example claims conformance with any standard.

## Paper sizes

Width × height in millimetres, portrait. `fenolite.model.presentation.PAPER_SIZES` holds the same
values in nanometres; inches are converted at exactly 25.4 mm.

| size | width × height (mm) | source |
|---|---|---|
| A0 | 841 × 1 189 | S-0077 |
| A1 | 594 × 841 | S-0077 |
| A2 | 420 × 594 | S-0077 |
| A3 | 297 × 420 | S-0077 |
| A4 | 210 × 297 | S-0077 |
| A5 | 148 × 210 | S-0079 |
| Letter | 215.9 × 279.4 (8.5 × 11 in) | S-0079 |
| Legal | 215.9 × 355.6 (8.5 × 14 in) | S-0079 |
| Tabloid | 279.4 × 431.8 (11 × 17 in) | S-0079 |

## Frame and reference zones

| figure | value | source |
|---|---|---|
| border on the filing (left) edge | 20 mm | S-0077 |
| border on the other edges | 10 mm | S-0077 |
| frame line width | 0.7 mm | S-0077 |
| length of a reference field | 50 mm | S-0077 |
| height of the field letters and numerals | 3.5 mm | S-0077 |
| width of the reference grid lines | 0.35 mm | S-0077 |
| field letters run top down and skip I and O; numerals run left to right | — | S-0077 |
| title block in the bottom right corner (A0 to A3), in the lower part for A4 | — | S-0077 |

Fenolite choices, not taken from a source: the zone band (the strip between the frame and the inner
rectangle that holds the field labels) is 5 mm; field labels are numbered from the frame corners, not
from the centring axes that ISO 5457 measures from (one corner-anchored sheet must serve every listed
size); numerals are drawn on both horizontal bands and letters on both vertical bands on every size;
centring marks are not drawn.

## Title-block labels

The data field names of ISO 7200 that the examples use as cell labels, and the neutral token each cell
shows. The title-block width (180 mm in the examples) is a Fenolite choice: the S-0078 preview text
does not give it.

| label | token | source |
|---|---|---|
| Title | `{title}` | S-0078 |
| Identification number | `{doc_id}` | S-0078 |
| Revision index | `{revision}` | S-0078 |
| Date of issue | `{date}` | S-0078 |
| Legal owner | `{organization}` | S-0078 |
| Responsible department | `{responsible}` | S-0078 |
| Approval person | `{approver}` | S-0078 |
| Segment/sheet number | `{sheet}` | S-0078 |
| Paper size | `{paper}` | S-0078 |
