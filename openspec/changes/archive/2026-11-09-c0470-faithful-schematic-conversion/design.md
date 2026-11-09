# Design: c0470

## Context

- **Board.** `convert` carries a board item by item and proves it with `equivalent` at level 5. Items that
  one format cannot hold travel in carriers: board storages (c0450), the frame (c0467) and stroke fonts
  (c0460).
- **Schematic.** `convert` has no drawing:
  - `convert/altium_to_kicad.py` records `ledger.change("schematic", …, "positions and wires are
    regenerated from the circuit")` and writes `schgen.generate_schematic`;
  - `convert/to_altium.py` writes the source's symbols at generated positions (c0160, c0086).
- **What c0276 already gives:**
  - the value `fenolite.model.drawn.DrawnSchematic`;
  - the resolver `fenolite.model.drawn_connect.resolve`;
  - the KiCad extractor `backends/kicad/drawn.extract`;
  - the KiCad writer `backends/kicad/drawn.lower_drawn`;
  - the Altium writer `backends/altium/drawn.py`;
  - level S of `design-equivalence` (`checks/equivalence/drawn.py`, c0278), which compares two drawings item
    by item.
- **What is missing:**
  - an Altium extractor;
  - symbol graphics carried from an Altium source;
  - a conversion that uses these parts;
  - a per-object report;
  - level S run by `convert`.

## D1. Altium extractor

New module `fenolite.backends.altium.drawn_read`. Its public function is
`extract(sheets: Sequence[SheetInput], *, components: Mapping[str, str] | None = None) ->
tuple[DrawnSchematic, tuple[Issue, ...]]`.

- `sheets` are the read documents of `altium-schematic-reader` with their project paths, the input of
  `adapter.netlist.resolve`, which gives the sheet hierarchy and the designators. The extractor reads no
  file. (The proposal first named `ProjectSheets`; that type is the writer's plan, not a read sheet.)
- `components` maps a designator to its component path; without it the path is the designator.
- **Coordinates.** One Altium fraction unit is 127/50 nm (`schematic-records.md`). A drawn point is
  `x · 127/50` nm and `(H − y) · 127/50` nm, where `H` is the height of the sheet's drawing area: the drawn
  frame has Y down and its origin at the top left of the drawing area. A value that is not a whole number of
  nanometres is rounded to the nearest; `altium.import.inexact` counts the rounded values of each sheet. An
  opaque item keeps its exact record text, so only modelled items are rounded.
- **Item mapping:**
  - component: `DrawnSymbol` with pose, part (unit), mirror and display mode;
  - wire and bus: polylines;
  - junction: junction;
  - net label: local label;
  - port: global or hierarchical label, by the scope rules of `altium-import` ("Connectivity within a
    sheet");
  - power port: power item, with its style;
  - sheet symbol and sheet entries: `DrawnSheetRef` with pins;
  - no-ERC marker: no-connect;
  - every other record (harness connector, harness entry, signal harness, parameter set, directive, note,
    text frame, graphic, image): a typed opaque item that keeps its record fields, written back by D4.
- **Sheet.** Size, orientation, border, grid, title block fields and the document parameters go to the
  sheet's `paper` and `title_block`.
- An item the extractor cannot represent is an `error` issue. The conversion counts it as `lost`; it is
  never dropped silently.

## D2. Symbols of the source

- **Altium to KiCad.** Each component's embedded symbol, with all its parts and display modes, becomes a
  KiCad symbol in the project's symbol library. The writers are `backends/kicad/sym.py` and `symembed.py`, extended for:
  - Altium pin decorations (dot, clock, IEEE symbols): mapped where KiCad has an equivalent pin shape,
    otherwise carried as graphics and counted `changed`;
  - pin name and designator visibility and offsets.
- **Display modes.** A KiCad symbol has one or two body styles. A component's symbol is built from the
  display mode it shows; its other display modes are counted `changed` under `symbol-graphic` and their
  records travel in the carrier of D4.
- **Graphics.** Lines, polylines, polygons, rectangles and ellipses map to KiCad shapes. Arcs, elliptical
  arcs, round rectangles, Bézier curves and pie charts are written as polylines; texts in a symbol body and
  IEEE symbols are not drawn. Each is counted `changed` under `symbol-graphic`.
- **KiCad to Altium.** The path `--altium-symbols graphics` (c0086) becomes the default when the source has
  sheets.

## D3. Conversion

- **`convert/schematic.py`:**
  - `drawing_of(source)` returns the source's `DrawnSchematic`: the KiCad extractor, or the Altium
    extractor of D1;
  - `write_drawing(target, drawing, symbols)` calls `lower_drawn` or the Altium drawn writer.
- `altium_to_kicad.py` and `to_altium.py` call it for a source with sheets. `schgen` remains the path for a
  source without sheets (a PCB document alone).

## D4. Carriers

Both carriers are canonical JSON, one per sheet:

- **In KiCad:** `Fenolite.Altium.Sheet`, schema `fenolite.altium-sheet.v0`, stored in the sheet's
  title-block `comment 9`. A `.kicad_sch` holds no sheet property, and a root sheet has no sheet symbol to
  hold one. `kicad-cli` 10.0.6 keeps `comment 9` when it saves the sheet (`sch upgrade`), and KiCad's default
  worksheet draws comments 1 to 4 only (`pagelayout_default.kicad_wks`), so the carrier is not drawn. It holds
  the sheet record, the opaque Altium records of D1, and the Altium fields of modelled items (part display
  mode, port and power style), each with the uuid of the KiCad item that stands for it when there is one.
- **In Altium:** a document parameter `Fenolite.KiCad.Sheet`, schema `fenolite.kicad-sheet.v0`. It holds
  what an Altium record cannot hold: field styles, `exclude_from_sim` and similar fields.

The way back writes the carried records again, moved with the item that stands for them.

Implemented for the KiCad demo projects (task 5.4, 2026-11-07):

- **Joins Altium does not make.** KiCad joins a local label to the hierarchical label and to the power
  symbol of its name on its sheet, and a hidden power-input pin to the global net of its name. Altium joins a
  net label to neither a port nor a power port (`H-A-IMP-DUP-NAME`), and a hidden pin to nothing. Such a
  local label is written as a port or a power port, and such a pin gets a power port at its hot end. The
  carrier restores the label and drops the pin's port.
- **Carrier content.** The carrier also holds each label's kind and written text by position (a port by
  either hot end), the fields of sheet symbols and symbols (by `<designator>:<unit>`, with the lib id of a
  unit drawn by another symbol), and the KiCad sheet and file of a sheet copied per instance. A value
  longer than 60 000 characters is split into numbered parameters, since a record holds at most 65 535 bytes.
- **Reused sheets.** Altium needs one sheet per instance. The way back folds the copies into one KiCad sheet
  by the carried origin, and level S copies the read sheet per instance before it compares.
- **Parts.** Each symbol property besides `Reference`, `Value` and `Footprint` is a parameter of the part.
  A pin on whole mils off the 10-mil grid is written with `_FRAC` keys and a `PinFrac` entry. A pin off a
  whole mil stays refused (`FEN-7001`).
- **Losses kept as rows.** A DNP mark is the `dnp` loss of the Altium writer, also when only the schematic
  holds it. A BOM-only symbol stays refused (c0334), so `cm5_minima` is left out of the round trip.
- **No PCB document.** A KiCad project with an empty board writes no PCB document. Its verification reads the
  project's sheets and compares their circuit with the source schematic's. The way back takes
  `convert/schematic.py`, as `hier` does, since `convert` refuses a project without a PCB design (c0364).

## D5. Report and verification

- **Report.** `convert/report.py` gets the kinds `sheet`, `schematic-symbol`, `symbol-graphic`, `pin`, `wire`,
  `junction`, `label`, `port`, `power`, `bus`, `bus-entry`, `sheet-symbol`, `harness`, `no-connect`,
  `directive`, `schematic-text`, `schematic-graphic`, `image` and `title-block`, each with `source`, `written`,
  `changed` and `lost`. The reasons are constants
  in `convert/codes.py`.
- **Comparison.** `convert` runs the existing level S (`checks/equivalence/drawn.py`) between the source
  drawing and the drawing read back from the written files, through `extract_with_pins` for KiCad and the
  D1 extractor for Altium. Level S already matches symbols by component path and unit, wires by maximal
  collinear segments, and other items by kind, position and attributes. This change adds the attributes
  that D1 and D2 carry: part, display mode, port and power style, sheet and title-block fields, and the
  typed opaque Altium records.
  Implemented: the part is the symbol unit in the match key, the power style is the power `symbol`
  (`AltiumPower:<style>`), the port style is the label shape, the sheet fields are the paper and the
  title-block pairs, and an opaque item compares by the SHA-256 of its Altium text when it has one, so the
  KiCad text that stands for an Altium record may change. Display mode is not in the drawn model: the
  shown mode is drawn as KiCad body style 1 and the records of the other modes are reported under
  `symbol-graphic` (`drawn_symbols.CHANGED_MODE`), not compared.
- **Connectivity.** `drawn_connect.resolve` is checked against the circuit with the comparison of c0276
  ("Drawing compared with the circuit").
- Every difference must match a report row (`design-conversion`, "Differences matched to the report").

## D6. Import to Python

- `fenolite import --to python` of an Altium source converts it to KiCad in memory (c0429) and emits the
  converted project. With D3 the converted sheets hold the source drawing, so the import keeps the
  converted hierarchy and its embedded symbols, and `importer.schematic.drawing_value` extracts the drawing
  for an Altium source as it does for a KiCad one. The emitted `schematic.toml` names the components by the
  paths of the emitted code (`design.lock`).
- The emitted code calls `design.load_schematic("schematic.toml")`; a KiCad build lowers the drawing with
  `backends/kicad/drawn.lower_drawn`.
- **Verification.** A test imports `blink` and the Altium project built from `examples/altium_hier_board`
  (`hier` holds no PCB document, and an import needs one), builds the code, extracts the built sheets
  and runs level S against the drawing of D1.

## D7. Evidence per behaviour

| Behaviour | Level before merge |
|---|---|
| Altium extractor, read-back on the public SchDoc rows | CORPUS-VERIFIED |
| KiCad sheets written from an Altium drawing (load, netlist, ERC) | KICAD-VERIFIED (`kicad-cli` 10.0.6) |
| Altium sheets written from a KiCad drawing | CORPUS-VERIFIED read-back; ALTIUM-VERIFIED(kit) before release |
| Round trip of the carriers | CORPUS-VERIFIED |
| Altium import to Python keeps the drawing | CORPUS-VERIFIED (built, read back, level S) |
| KiCad keeps title-block `comment 9` on a save | KICAD-VERIFIED (`kicad-cli` 10.0.6 `sch upgrade`) |

## Risks

- **Symbol graphics that KiCad cannot draw** (some IEEE symbols, Bézier curves). Bézier curves are written
  as KiCad Bézier curves, and the other graphics as polylines, each counted `changed`.
- **Ports whose scope depends on project options** (net identifier scope). The extractor reads the
  project's option; it uses the rule of `altium-import` and reports `INFERRED` where the scope is inferred.
