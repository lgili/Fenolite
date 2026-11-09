# c0470: a converted schematic looks like its source

## Why

`fenolite convert` keeps a board item by item. It does not keep the schematic:

- **Altium to KiCad.** The converter regenerates the schematic from the circuit. The report has one row,
  `schematic changed 1` ("positions and wires are regenerated from the circuit"). Each component becomes a
  generic box on a grid, with a net label on every pin.
  - Lost: symbol graphics, positions, wires, junctions, ports, power objects, buses, harnesses,
    directives, free texts, drawings, the sheet format and the title block.
- **KiCad to Altium.** c0160 writes the source's own symbols, but not at the source's positions. Keeping
  the positions is one of c0160's non-goals.

A schematic that cannot be opened and edited in place of its source makes the conversion unusable.

Most parts exist already:

- **c0276:**
  - `DrawnSchematic` and its resolver;
  - the KiCad extractor;
  - writers for both backends.
- **c0278:** level S of `equivalent`, which compares two drawings item by item.

What is missing is a reader that gives the drawing of an Altium sheet. `importer.schematic.drawing_value`
returns `None` for any source that is not KiCad, and `convert` uses none of these parts.

## What

1. **Drawing of a read Altium sheet.** A new extractor turns read `SchDoc` sheets into a `DrawnSchematic`.
   It reads:
   - symbol poses and parts;
   - wires, junctions, net labels, ports and power ports;
   - sheet symbols and their entries;
   - buses and bus entries;
   - no-ERC markers, harness items, parameter sets and directives;
   - notes, texts and drawings;
   - the sheet's size, border and title block.
2. **Source symbols kept.** In both directions each component keeps its source symbol:
   - body graphics;
   - pins, with position, length, name, number, type and decorations;
   - display modes and parts.
3. **Convert writes the drawing.** In both directions a source with sheets is written through the existing
   drawn writers. A source without sheets is still written with the generated schematic.
4. **Carriers.** An item that the target cannot hold travels in a per-sheet carrier, as board storages do
   (c0450, c0467), and is written again on the way back. The report counts it as `changed`, with its
   reason.
5. **Report per object.** The single `schematic` row becomes one row per kind, from `sheet` and
   `schematic-symbol` to `harness`, `directive` and `title-block` (design D5).
6. **Verification.** The conversion runs level S between the source drawing and the drawing read back
   from the written files. It also checks the drawn netlist against the circuit. Any difference that the
   report does not explain is `convert.unexplained`.
7. **Import to Python keeps the drawing.** `fenolite import --to python` of an Altium project emits
   `schematic.toml` with the source drawing, as it does for a KiCad project, and the schematic built from
   the emitted code equals the source drawing at level S. Today `importer.schematic.drawing_value` returns
   `None` for any source that is not KiCad, so the code of an Altium project builds a generated schematic.
   The maintainer asked for this on 2026-11-07.

## Non-goals

- Formats other than Altium `SchDoc` and KiCad `.kicad_sch`.
- Managed components that the document does not embed. Each is reported as lost, with its reason.
- Glyph-identical font rendering. Text position, size, justification and style are kept.
- The generated schematic of a design written as code. This means a design authored as code, which has no
  source drawing; a design imported from Altium or KiCad keeps its source drawing (item 7).

## Evidence level required

- **KiCad target: `KICAD-VERIFIED`.**
  - `kicad-cli` 10.0.6 loads every written sheet.
  - The netlist equals the source's.
  - The ERC result by violation type equals the source's on the public KiCad demo projects.
- **Altium target:**
  - `CORPUS-VERIFIED` round trip, read back, on the public rows `altium-third-party-schdoc-01` to `-17`
    and the public project rows.
  - `ALTIUM-VERIFIED(kit)` before release: Altium compiles the written sheets, and its netlist and ERC
    equal the source's.
- **Format facts:** each new record fact goes into `docs/formats/altium/schematic-records.md` or
  `docs/formats/kicad/schematic.md`, with its public source in `docs/evidence/sources.md`.
