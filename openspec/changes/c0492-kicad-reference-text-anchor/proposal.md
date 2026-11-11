# c0492: an imported Altium text keeps its anchor in KiCad

Found on: reviewing a private maintainer board on 2026-11-11 (codes only; nothing from the board is in
this change).

## Why

A component text read from an Altium PCB document, such as a designator, takes the record's position as
its anchor. Altium places a stroke text from the lower-left corner of its text box. KiCad's own Altium
import does the same (`docs/formats/altium/pcb-records.md`, `H-A-PCBX-KICAD`).

`backends/altium/adapter/copper.py` builds the `FootprintField` (and the `Text`) with that position and
leaves `h_justify`/`v_justify` at their default, `center`. So a conversion to KiCad draws the text
centred on Altium's corner. Each text moves by half its box, and KiCad's silkscreen checks
(`silk_overlap`, `silk_over_copper`) then judge a layout that differs from Altium's.

The Altium writer has the opposite gap. It writes a field's model position as Altium's corner whatever its
justification (`lower.py`, `place`). A centred field built by a script, or a centred text edited in KiCad,
lands half a box away in Altium. A free board text with another justification is refused.

## What Changes

- The import gives each text and field of an Altium document `h_justify="left"`, `v_justify="bottom"`, so
  the model states the anchor the document uses. A mirrored text on the bottom side keeps its mirror, and
  KiCad mirrors the justification with it.
- The KiCad writer already writes the justification of a field and a text, so the conversion draws the
  text where Altium does. Task 1.1 measures this against `kicad-cli`'s own Altium import of the same
  authored document.
- The Altium writer writes the lower-left corner of the text box. For a text justified left and bottom
  that is its position. For any other justification it moves the position by the text box, measured with
  the stroke font metrics that `convert.strokefonts` and `silk.extents` already use, and turned by the
  rotation. A free board text with another justification is no longer refused.
- A round-trip test: Altium → KiCad → Altium writes every text record at the source's position, byte for
  byte. A centred field moved in KiCad is written at the corner that puts its ink in the same place.

## Impact

- `src/fenolite/backends/altium/adapter/copper.py` (component texts and fields, free texts).
- `src/fenolite/backends/altium/lower.py` (`place`, the free-text refusal at "no key for a justification
  other than centred"), `src/fenolite/backends/altium/pcbdoc.py` (`TextPlace`).
- `docs/formats/altium/pcb-records.md`, `docs/formats/altium/import.md` (the anchor row).
- KiCad boards converted from Altium before this change keep their centred fields until they are converted
  again.
