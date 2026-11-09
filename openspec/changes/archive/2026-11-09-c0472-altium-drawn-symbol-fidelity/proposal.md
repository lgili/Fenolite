# Proposal: c0472-altium-drawn-symbol-fidelity

## Problem
When an Altium project with drawn schematic sheets is imported (`import --to python`) or converted (`convert --to kicad` / `convert --to altium`) and built or converted back to Altium (`build --target altium` or `convert --to altium`), three visual defects appear on the generated Altium schematic sheets:

1. **Open multi-point polylines and arcs are closed into polygons (`RECORD=7`):**
   `drawn_symbols.graphic` maps Altium `Polyline` (`RECORD=6`), `Arc` (`RECORD=12`), `EllipticalArc` (`RECORD=11`), and `Bezier` (`RECORD=5`) to `SymbolGraphic("line", points)`. When `backends.kicad.sym` writes and reads back a `(polyline (pts ...))` with more than two points, `_Reader.graphic` classifies any polyline with `len(points) > 2` as `kind = "polygon"`, even when it is neither closed (`points[0] != points[-1]`) nor filled. Furthermore, `backends.altium.altsym.map_graphic` truncates `SymbolGraphic("line", points)` to `(points[0], points[1])` and `schdoc.graphic_fields` writes `AltiumGraphic("line", ...)` only as a two-point `Line` (`RECORD=13`). As a result, multi-segment resistor zigzags and inductor/fuse arcs are written to Altium as closed `Polygon` (`RECORD=7`) records with a closing chord across the symbol.
2. **Component `Comment` (value) fields are shadowed by hidden `Value` parameters:**
   In `backends.altium.drawn_read._fields`, both `child.name == "Comment"` and a custom parameter `child.name == "Value"` map to `name = "Value"`, and `if child.hidden and name != "Value": continue` keeps a hidden `Parameter(NAME=Value, ISHIDDEN=T)` that precedes the visible `Parameter(NAME=Comment)`, causing `seen` to skip the visible `Comment` field and hiding the component's value on the sheet.
3. **Hidden pin names and numbers on source symbols become visible:**
   `backends.altium.drawn_symbols.component_symbol` leaves `pin_names_hidden=False` and `pin_numbers_hidden=False` on every extracted `SymbolDef`, even when every shown `Pin` record of the component hides its name (`not pin.name_shown`) or designator (`not pin.designator_shown`), causing passive symbols to render unwanted pin numbers and names in KiCad and Altium.

## Scope
- Preserve open multi-point `(polyline (pts ...))` graphics as `SymbolGraphic("line", points)` in `backends.kicad.sym`, keep all points in `backends.altium.altsym.map_graphic`, and write `AltiumGraphic("line", ...)` with more than two points as an Altium `Polyline` (`RECORD=6`) in `backends.altium.schdoc.graphic_fields`.
- Ensure `backends.altium.drawn_read._fields` maps `Comment` to `"Value"` without allowing a custom `Value` parameter to shadow `Comment`, and skips hidden non-`Comment` parameters.
- Set `pin_names_hidden` and `pin_numbers_hidden` on `SymbolDef` in `backends.altium.drawn_symbols.component_symbol` when all shown pins of the component hide their names or designators.
