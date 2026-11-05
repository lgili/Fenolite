# c0409: Altium import fidelity

## Why

The coordinator converted a private Altium project with `fenolite import --to python` and
`fenolite convert --to kicad` and reported eight defects (B4 to B11). Only their descriptions enter this
change: no name, value, shape or file of that project. Every fixture is authored for Fenolite.

- **B8 (high, silent loss).** A footprint's own lines, arcs, circles and regions (silkscreen, courtyard,
  fabrication, mechanical) were read from Altium into the model (c0126), but the KiCad board writer wrote a
  created footprint's pads and fields only. The derived library footprints held no `fp_*` child and no issue
  said so.
- **B4 (high, rules).** The importer folded a one-sided rule "<class> x All" into
  `design.rules.minimum(netclass=)`, which is written last and governs every rule of its class (c0403, F2),
  over the pairwise rules Altium ranks above it. Every `rule()` priority was also renumbered from its place
  in the `.kicad_dru`, so the code lost Altium's numbers.
- **B5 (medium).** Altium PolygonConnect rules were kept as board extension pairs and wiped by the
  conversion: every zone got the default connection.
- **B6 (medium).** A zone's clearance was the 0.5 mm default, not the Altium clearance rule that governs the
  polygon.
- **B9 (medium).** `convert --to kicad` placed 3D models in the library footprints only; the board had none,
  so `import --to python`, which derives its library from the board, had none either.
- **B7 (medium).** A clearance rule scoped to items without a net (`InNet('No Net')`) was reported as
  unmapped: the DSL had no selector for netless items.
- **B10 (low).** Altium special strings (`.NAME`, `=NAME`) were written literally and the `[ParameterN]`
  entries of a `.PrjPcb` were not imported.
- **B11 (low, render).** `render --svg` plotted the board on the drawing sheet; a board at Altium's origin
  (negative Y) fell off the page and the views came out blank.

## What

- B8: the KiCad writer writes a created footprint's graphics as `fp_line`, `fp_arc`, `fp_circle`, `fp_rect`
  and `fp_poly` on the layer the conversion maps; the report counts `footprint-graphic` and
  `footprint-text`, a footprint's own text (not written by a created footprint) is a reported loss, and both
  kinds warn with `convert.lossy` when they lose items, so an import, which keeps the conversion's issues,
  says so too.
- B4: the importer keeps the source's rank. A rule is folded into `minimum()` only where the minimum keeps its
  rank (a board minimum governs least, a class minimum most); any other one-sided rule is written as
  `rule(where=select.netclass(...))` with its priority. A rule written by Fenolite (`fenolite_<p>_<name>`)
  gets its own number back when the numbers give the file's order.
- B5: the conversion maps the PolygonConnect rules that govern each zone to its `connection`,
  `thermal_gap` and `thermal_spoke_width`, and narrower scopes that disagree to a pad's `zone_connection`.
- B6: the conversion writes the governing Altium clearance of each polygon as its zone clearance.
- B9: the board's footprints carry the placed models, so both paths write `(model` entries, and the import
  vendors the model files.
- B7: `fenolite.dsl.select.no_net()` and a model leaf `no_net`; `InNet('No Net')` maps to it and KiCad lowers
  it to `A.NetName == ''`.
- B10: `[ParameterN]` entries become the project's text variables and a special string `.NAME` or `=NAME`
  of a project parameter becomes `${NAME}`.
- B11: `render --svg` plots the board area without the drawing sheet when the board does not lie inside the
  sheet, and `--page board` asks for it always.

## Impact

- Capabilities: design-conversion, imported-rules, design-dsl, import-python, manufacturing-exports.
- New public DSL name `select.no_net()` (agent guide line, AGENTS.md rule 6); new `render` option `--page`.
- No new FEN code, no new dependency. Board outputs of existing KiCad designs do not change: only created
  footprints with graphics (an Altium conversion) gain `fp_*` children.
- Source ids S-1680..S-1699.
