## Why

Fenolite draws every schematic itself. The generator of `kicad-schematic` (and its block form, c0269)
places units in rows, snaps satellites with short wires and joins nets through global labels. That is
right for a design written as code, but it cannot reproduce a schematic that a person drew: bent wires,
junctions, local and hierarchical labels, buses, bus entries, sheet pins and one sheet used by several
sheet symbols (repeated sheets) have no place in the DSL or in a build. The reader keeps them only as
opaque slots of a read sheet, which no writer can emit for a created sheet.

The research of 2026-10-29 (`docs/research/board-library.md`, section 1 "The schematic is generated, not
drawn", section 4.2 and row c0276 of section 5) needs this for the board library: a public board converted
to code (c0275) must keep its drawing, and the fidelity proof (c0278, level S) must be able to compare it
with the original. Users also ask for it: a schematic tidied by hand in KiCad should survive the next
build instead of being replaced (`build.schematic-replaced`).

The danger of a drawing beside code is drift: the drawing says one thing and `design.py` another. This
change keeps the code as the only source of connectivity and proves, at every build and in
`fenolite check`, that the drawing means exactly the code's netlist.

## What Changes

- **File `schematic.toml`, schema `fenolite.drawn-schematic.v0`.** Sheets keyed by name, each with symbol
  poses keyed by component path and unit (field poses included), wire and bus polylines, bus entries,
  junctions, no-connect flags, local, global and hierarchical labels, power symbols, bus aliases, sheet
  references with sheet pins, and verbatim opaque items (text, graphics) per target. A sheet referenced by
  several sheet references is a repeated sheet: each reference names the code module whose parts it shows.
  Lengths in millimetres read as exact decimals and stored as integer nanometres. The file holds no value,
  reference or footprint: those stay in code (and in c0250's `edits.toml`).
- **DSL.** `design.load_schematic("schematic.toml")` records the file. The generated schematic stays the
  default.
- **Model.** `Junction`, `BusWire`, `BusEntry` and `BusAlias` entities on `SchematicSheet`, beside `Wire`
  and c0269's `SheetPin`, and the value `DrawnSchematic` (`fenolite.model.drawn`).
- **Connectivity resolver** `fenolite.model.drawn_connect`: pure, no tool. Wires, junctions, labels by
  scope, power symbols, buses and bus entries, sheet pins and hierarchical labels, and repeated sheets give
  the nets of the drawing as component path and pin sets, with names.
- **Build.** A design that loads a drawn schematic gets its sheets from the file instead of the generator.
  The KiCad writer emits every drawn item. The build reads back what it wrote, resolves it and compares it
  with the circuit; a difference writes nothing (`build.schematic-netlist-differs`, exit 5).
  `schematic-placements.toml` is ignored then (`drawn.placements-ignored`).
- **Check.** A new stage `schematic.drawn` of `fenolite check` resolves the sheets of a built project,
  as they are on disk (possibly edited in KiCad), and compares them with the recorded circuit. Code and
  drawing cannot drift unnoticed.
- **Reading a KiCad schematic into the file.** `fenolite.backends.kicad.drawn.extract` turns read sheets,
  their opaque wire, junction, bus and text slots included, into a `DrawnSchematic`. c0275's importer and
  `fenolite sync --to-source` use it. A generated schematic can be frozen into a drawn one.
- **Altium.** A later phase of this change writes drawn sheets as SchDoc records (wires, junctions, net
  labels, ports, power ports, sheet symbols and entries, buses). It stays `INFERRED` until the
  maintainer's kit compiles a drawn example.
- **Mixed sheets.** A drawn sheet may be marked `generated = true`; its content then comes from the
  generator with c0269's block rules, and the drawn sheet reference must carry the pins it generates.

## Capabilities

### New Capabilities

- `drawn-schematic`: the file schema and its reading and canonical writing, sheets and repeated sheets,
  the lowering to sheets, the connectivity resolver, the comparison with the circuit, extraction from read
  KiCad sheets, freezing, generated sheets inside a drawing, codes, evidence and documentation.

### Modified Capabilities

- `design-dsl`: ADDED "Drawn schematic in the DSL", "Drawn schematic in a build", "Drawn schematic build
  guard" and "Drawn schematic build result".
- `design-model`: ADDED "Drawn schematic entities" and "Drawn schematic value".
- `kicad-schematic`: ADDED "Drawn sheets written", "Repeated sheets written" and "Drawn content of a read
  sheet".
- `altium-schematic-writer`: ADDED "Drawn sheets in Altium" and "Drawn items Altium cannot carry".
- `verification-loop`: ADDED "Drawn schematic stage" and "Drawn schematic stage issue codes".
- `layout-lens`: ADDED "Drawn schematic in the source tree" and "Drawn schematic sync refuses changed
  nets".

## Dependencies

- **c0269 block-schematic** (required): `SheetPin`, sheet pins and hierarchical labels in the KiCad writer,
  `sch.opaque_sheet_pins`, and the block rules a `generated` sheet uses.
- **c0250 manual-edit-merge**: values, footprints and references edited in CAD keep flowing through
  `edits.toml`. This change only adds the drawing, which is CAD-owned like the layout.
- **c0249 design-lock**: references come from code and the lock; the drawn file never holds them.
- Used by **c0275** (board-to-code writes `schematic.toml`) and **c0278** (level S compares drawings).
- Independent of c0277 (board coverage).

## Non-goals

- No schematic editor and no automatic routing of drawn wires. A drawing comes from a file read from a CAD
  tool, from the generator (freeze), or from a person editing TOML.
- No connectivity in the drawing that code lacks: a drawing is never a source of nets.
- No modelled schematic text, graphics or images: they stay verbatim opaque items in v0.
- No net class flags, rule areas or directive symbols beyond keeping them as opaque items.
- No Altium schematic read into a drawn schematic in this change (a follow-up, after c0040's reader keeps
  wire geometry).

## Evidence level required

- Resolver nets against `kicad-cli sch export netlist`: `KICAD-VERIFIED (9.0.x, 10.0.x)` once the KiCad CI
  job finds equal nets on the authored drawn fixtures and the demo rows (`H-K-DRAWN-CONNECT`,
  `H-K-DRAWN-BUS`, `H-K-DRAWN-REPEAT`). Net names: `INFERRED` until `H-K-DRAWN-NAMES` is measured; a
  name difference is a warning, never a connectivity error.
- Written drawn sheets: `KICAD-VERIFIED (9.0.x, 10.0.x)` once `kicad-cli` loads them and ERC reports no new
  violation (`H-K-DRAWN-WRITE`).
- Altium: `INFERRED` until the kit (`H-A-DRAWN-WRITE`).
- File schema, extraction and comparison: `INFERRED`, unit-tested.

## Impact

- New: `src/fenolite/model/drawn.py`, `src/fenolite/model/drawn_connect.py`, `src/fenolite/lens/drawn.py`
  (file reading and writing), `src/fenolite/backends/kicad/drawn.py` (lowering and extraction),
  `src/fenolite/backends/altium/drawn.py`, `src/fenolite/checks/drawn.py` (stage),
  `schemas/fenolite.drawn-schematic.v0.json`, `docs/drawn-schematic.md`, the authored fixtures
  `tests/data/drawn/` (CC0, authored for Fenolite), `examples/drawn/`, and tests under `tests/unit/model`,
  `tests/unit/lens`, `tests/unit/backends/kicad`, `tests/unit/backends/altium`, `tests/unit/checks` and
  `tests/kicad/schematic`.
- Changed: `model/schematic.py`, `dsl/design.py`, `lens/build.py`, `lens/sync.py`, `backends/kicad/sch.py`,
  `checks/stages.py`, `cli/cmd_build.py`, `cli/cmd_check.py`, `cli/cmd_sync.py`, `explain.toml`,
  `docs/dsl.md`, `docs/schematic.md`, `docs/formats/kicad/schematic.md`, `docs/hypotheses.md`, the guide
  pages `design-script.md` and `checks.md`, `CHANGELOG.md`.
- Size: about 15 design-days (L).
