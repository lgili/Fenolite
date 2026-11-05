# c0414: an empty schematic Footprint field beside a board footprint

## Why

The c0401 census (`kicad-demo-9-0-9-1-pcb-01`, KiCad 10.0.6) leaves `8:render-pixels=1` on the
schematic page. The source symbol R2 has a visible, empty `Footprint` field, while its board footprint is
`custom_pads_test:DO-214AB`. A `Part` holds one footprint, and the drawn writer fills the schematic field
from it, so the rebuilt page draws a 0.762 mm text the source does not (872 of 37894 pixels).

The import already decides the other cases. A non-empty field that names another footprint basename
refuses (c0342, `FEN-3004`); a field naming the same basename in another library is kept as the part's
footprint alias. Only the empty field is silently replaced. c0326 rules out a generic text override for
reserved fields.

## What

- `DrawnSymbol.empty_footprint` (`schematic.toml`: `empty_footprint = true`): this unit's source
  `Footprint` field is empty while its part has a footprint. It is a flag, not a text.
- `drawn.extract` sets it only when told the footprint each reference builds with and that footprint is
  not empty; the import passes the footprints it writes.
- The KiCad drawn writer writes an empty `Footprint` field for a flagged unit. The part, its board
  footprint, the netlist and every other field stay as they are.

## Impact

- `src/fenolite/model/drawn.py`, `src/fenolite/model/_drawn_text.py`, `src/fenolite/lens/drawn.py`,
  `schemas/fenolite.drawn-schematic.v0.json`, `src/fenolite/backends/kicad/drawn.py`,
  `src/fenolite/importer/schematic.py`, `src/fenolite/importer/emit/design.py`.
- Docs: `docs/drawn-schematic.md` (the key), `CHANGELOG.md`, `docs/evidence/fidelity.md`.
- The schema id stays `fenolite.drawn-schematic.v0`: the key is optional and older files read unchanged.
- No DSL name, CLI argument or `FEN-` code changes. The Altium drawn writer ignores the flag (no Altium
  backend change); the flag affects only KiCad sheets.
