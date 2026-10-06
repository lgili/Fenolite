## Why

The Altium schematic that a build writes is correct in its nets and poor in everything a reader of the sheet sees. Every symbol is a rectangle with pins, whatever the KiCad symbol or the catalog symbol draws. Hierarchy stops at one level. Sheet entries and ports carry no direction, so Altium's compiler cannot check them. Buses of the model are flattened. A text with a character outside 7-bit ASCII stops the build. These limits were acceptable for the first board; they are not for the write side of a second backend.

Since c0058 and c0060 the model holds symbol graphics (`SymbolGraphic`) and since c0070 the KiCad schematic is one sheet per module at any depth with a readable layout. The Altium writer still uses the model of 2026-10-02.

## What Changes

- **Symbol graphics.** Schematic libraries and the bodies on the sheet draw the symbol's own graphics (lines, rectangles, polylines, arcs, circles, texts) instead of a synthesised rectangle; a symbol without graphics keeps the rectangle.
- **Hierarchy at any depth**, one sheet per module, with the sheet tree and the layout rules of c0070 where they apply to Altium's objects.
- **Directions.** Ports and sheet entries carry the I/O type that follows from the pin types on the net; the rule is closed and documented.
- **Buses.** A bus of the model is drawn as a bus with its members' net labels, and a bus port or bus sheet entry where it crosses a sheet.
- **Text beyond ASCII**, in both forms: the binary form with the code page and the UTF-8 companion fields that the reader already reads, the ASCII form where its encoding is documented, and a refusal that names the character otherwise.
- **Component parameters**: the properties of a part become parameters of its component, hidden by default.

Size: 9.5 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-schematic-writer`: ADDED "Symbol graphics in libraries and bodies", "Sheets of a module tree", "Port and sheet-entry directions", "Bus records", "Text outside ASCII", "Component parameters"; these supersede the limits of "Generic component bodies", "Generic library symbols", "Sheets of a hierarchical project" and "Text the ASCII form cannot carry".
- `altium-build`: ADDED "Readable schematic in an Altium build"; supersedes the limits of "Module sheets in an Altium build".

## Non-goals

- No variants (the roadmap has them in v0.5b; see the open decision).
- No repeated sheets written: a module used several times is written once per use, as separate sheets or as one sheet with several sheet symbols, never with `Repeat`.
- No alternate display modes, no De Morgan bodies, no IEEE symbols of pins beyond the edge codes already written.
- No wires routed between arbitrary pins: connectivity stays by net labels, ports and the snap wires of c0070's rule.
- No images, no notes, no drawing sheet (c0087 writes the sheet template).
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- Own readback of every new record against the model: `INFERRED` under `H-A-SCHX-READBACK`.
- KiCad's importer on the written sheets and libraries, for what it reads (graphics, hierarchy, buses): `ORACLE-VERIFIED(kicad-cli 10.0.x)` for those facts.
- That Altium opens, compiles and runs the change order without a message: `INFERRED` until Part Y is reported.

## Decision of the maintainer (2026-10-06): v0.5b, as written below

- **Question.** Variants: in v0.4 with the schematic writer, or in v0.5b as the roadmap has them?
- **Default written here.** v0.5b. This change writes no variant and the project file lists none.
- **Alternative.** Write assembly variants (fitted / not fitted per variant) into the project file in v0.4.
- **To switch.** Add one requirement "Variants in the project file" to this change's `altium-schematic-writer` delta with a task and a Part Y step; the model already carries `dnp`, so only per-variant `dnp` would be new, which makes it a model change that needs its own design note.

## Impact

- Changed: `backends/altium/{altsym,symbols,schdoc,schlib,hierarchy,layout,ascii,binary,project}.py`, `lens/altium.py`.
- Pages: `docs/altium.md` ("Schematic", "Hierarchy", "Limits"), `docs/formats/altium/{schematic-records,schematic-library,schematic-ascii,schematic-binary}.md`, `docs/evidence/altium-schematic.md`.
- Samples under `tests/data/altium/` change where symbols now have graphics; each regenerated file is listed in the change.
- Depends on: c0032, c0033, c0034, c0036, c0037 (schematic writers); c0040 (the reader that proves readback); c0058 and c0060 (symbol graphics in the model); c0070 (sheet tree and layout). Nothing else of v0.4.
