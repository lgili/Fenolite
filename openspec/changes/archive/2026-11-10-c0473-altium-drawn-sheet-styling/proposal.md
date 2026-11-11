# Proposal: c0473-altium-drawn-sheet-styling

## Problem
When an Altium project with schematic sheets is imported (`import --to python`) or converted (`convert --to kicad`) and built or converted back to Altium (`build --target altium` or `convert --to altium`), several visual defects remain on the generated Altium schematic sheets:

1. **Port (`RECORD=18`) geometry, colors, and fills:**
   `backends.altium.drawn._Sheet.identifier` ignores the carried `ITEM_FIELDS["label"]` (`WIDTH`, `HEIGHT`, `STYLE`, `ALIGNMENT`, `BORDERWIDTH`, `AREACOLOR`, `TEXTCOLOR`, `COLOR`, `FONTID`) and writes every non-harness port with `WIDTH=10` (100 mil), `COLOR=8388608`, and omitted `AREACOLOR` and `TEXTCOLOR` (which default to `0` = black in Altium and `fenolite view`), shifting left-side ports rightwards by `orig_width - 10` so their text overflows the 100-mil box and overlaps adjacent `NetLabel`s.
2. **Overlapping `SheetName` (`RECORD=32`) and `SheetFileName` (`RECORD=33`) and misplaced `NetLabel` (`RECORD=25`) / empty `Comment` (`RECORD=41`):**
   - `backends.altium.drawn._Sheet.reference` writes both `RECORD=32` (`SheetName`) and `RECORD=33` (`SheetFileName`) at the exact same `(LOCATION.X, LOCATION.Y)` coordinate (`self.height - y`), causing the sheet title and file name to overlap on every `SheetSymbol`, and drops the carried `SheetSymbol` `AREACOLOR`, `SheetEntry` `TEXTFONTID`, and `SheetName`/`SheetFileName` positions and `FONTID`s.
   - `backends.altium.drawn_read` and `backends.altium.drawn` drop `JUSTIFICATION` and `COLOR` on `NetLabel` (`RECORD=25`), causing right-justified net labels (`JUSTIFICATION=2` or `5`) to flip to left-justified and overlap adjacent components.
   - `backends.altium.drawn_symbols.component_symbol` omits `"Value"` from `SymbolDef.properties` when a component's `Comment` is empty (`""`), causing `backends.kicad.sym` to default `"Value"` to `symbol.name` (`SYM_<ref>`) and `lens.altium` to write `SYM_<ref>` onto the sheet.
3. **Sheet font table (`RECORD=31`), `Template` (`RECORD=39`), and component body graphic colors/fills:**
   - `importer.schematic` discards `AltiumSheet.sheet` (`RECORD=31` font table / `AREACOLOR` and `RECORD=39` `Template` border/title-block graphics) and `AltiumSheet.fields` when writing `schematic.toml`, and `backends.altium.drawn` does not apply them.
   - Component body graphics on the sheet lose their source `COLOR`, `AREACOLOR`, `ISSOLID`, `TRANSPARENT`, and primitive shapes (`RoundRectangle`, `Arc`, `EllipticalArc`, `PieChart`, `IeeeSymbol`, and child `Label`) as well as `Designator`/`Comment` `FONTID`.

## Scope
- Carry `AltiumSheet` (`sheet` and `fields`) through `importer.schematic` (as a `Fenolite.Altium.Sheet` carrier opaque record in `schematic.toml`, unpacked by `sheet_carrier.put_drawing` and `backends.altium.drawn.lower_drawn`) and pass `sheet_records` alongside `fields` in `convert.to_altium`.
- Record `NetLabel` justification/color/font, `SheetSymbol`/`SheetEntry`/`SheetName`/`SheetFileName` positions/colors/fonts, `PowerPort` color/font, and component body graphic records and `Designator`/`Comment` `FONTID` in `drawn_read.extract_with_pins`.
- Apply carried `Sheet` (`RECORD=31`), `Template` (`RECORD=39`), `Port` (`RECORD=18`), `NetLabel` (`RECORD=25`), `PowerPort` (`RECORD=17`), `SheetSymbol` (`RECORD=15` / `16` / `32` / `33`), and `Component` (`RECORD=1`) body graphics and fonts in `backends.altium.drawn`, while keeping existing bytes unchanged when no Altium carrier/fields are present.
- Preserve empty `Comment` (`""`) as `properties["Value"] = ""` in `drawn_symbols.component_symbol`.
