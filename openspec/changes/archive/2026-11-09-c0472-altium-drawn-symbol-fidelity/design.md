# Design: c0472-altium-drawn-symbol-fidelity

## D1: Open multi-point symbol lines in KiCad and Altium
- In `backends.kicad.sym._Reader.graphic`, a `(polyline (pts ...))` node with `len(points) > 2` is a `"polygon"` when `points[0] == points[-1]` (closed ring, as `write_symbol_library` writes `SymbolGraphic("polygon", ...)`) or when `fill_type in ("background", "outline")`. Otherwise it is a `"line"` with all its points kept.
- In `backends.altium.altsym.map_graphic`, `graphic.kind == "line"` keeps `tuple(points)` instead of `(points[0], points[1])`.
- In `backends.altium.schdoc.graphic_fields`, when `graphic.kind == "line"` has `len(graphic.points) == 2`, it continues to write `RECORD=13` (`Line` with `LOCATION` and `CORNER`). When `len(graphic.points) > 2`, it writes `RECORD=6` (`Polyline` with `OWNERPARTID`, `LINEWIDTH=1`, `COLOR=128`, `LOCATIONCOUNT`, and `X1..Xn`/`Y1..Yn`).

## D2: Component `Comment` field precedence in `drawn_read._fields`
- In `backends.altium.drawn_read._fields`, when a component has a `Parameter` with `name == "Comment"`, any custom `Parameter` literally named `"Value"` is ignored for `DrawnField` extraction so `"Comment"` always supplies the `"Value"` field pose and visibility. Hidden parameters other than `"Comment"` continue to be skipped.

## D3: Symbol-level pin name and number visibility in `drawn_symbols.component_symbol`
- In `backends.altium.drawn_symbols.component_symbol`, inspect the shown `Pin` children of the component:
  - `pin_names_hidden = bool(raw_pins) and not any(p.name_shown and p.name not in ("", "~") for p in raw_pins)`
  - `pin_numbers_hidden = bool(raw_pins) and not any(p.designator_shown for p in raw_pins)`
- Pass `pin_names_hidden` and `pin_numbers_hidden` to `SymbolDef`.
