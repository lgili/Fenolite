# Delta for altium-schematic-writer

## MODIFIED Requirements

### Requirement: Symbol graphics in libraries and bodies
`backends.altium.altsym.from_symbol_def(symbol, *, lib_ref, footprint, issues, unmodelled=(), bodies="graphics", parents=())` SHALL, with `bodies="graphics"`, map the graphics of a `SymbolDef` to schematic records of their kind, in the symbol's frame, for the library and for the body on the sheet alike. `altsym.SymbolBodies` is `Literal["generic", "graphics"]` and `altsym.DEFAULT_BODIES` is `"graphics"` (decision of the maintainer, 2026-10-06).
- `GRAPHIC_KINDS` MUST be the kinds of `model.library.SymbolGraphic`, which all have a record: `line` (record 13 for two points, record 6 `Polyline` for three or more points), `rect` (record 14), `polygon` (record 7, closed) and `circle` (record 8, an ellipse of two equal radii). The fill is kept as a flag (`ISSOLID=T` when filled), never as a colour; every graphic holds `LINEWIDTH=1`, `COLOR=128` and, when it can be filled, `AREACOLOR=11599871`, in the key order of `docs/formats/altium/schematic-records.md` ("Graphics the writer draws").

#### Scenario: Open multi-point line graphic
- **GIVEN** a symbol with an open multi-point `line` graphic of three or more points
- **WHEN** it is written to a KiCad symbol library, read back, mapped to an `AltiumSymbol`, and written to a schematic library or sheet
- **THEN** the KiCad reader preserves `kind == "line"` with all points, and the Altium writer emits `RECORD=6` (`Polyline`) with all points and no `AREACOLOR`
