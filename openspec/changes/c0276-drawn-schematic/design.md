## Context

- **Source.** `docs/research/board-library.md` (2026-10-29), section 1 ("The schematic is generated, not
  drawn"), section 4.1 (the `schematic.toml` of an imported board), section 4.2 and row c0276 of section 5.
  KiCad file facts come from the public format page (S-0367) and the schematic editor manual (S-0046, read
  again for this change: wires, junctions, labels and their scope, buses, bus entries, bus aliases, sheet
  pins, power symbols, hidden power pins). Altium facts come from its documentation (S-0185) and the
  records already documented under `docs/formats/altium/`. No parser, grammar or file of another tool is
  copied.
- **What exists on `dev` (0.6.0).**
  - The model's `SchematicSheet` holds `symbols`, `labels` (local, global, hierarchical), `no_connects`,
    `wires` (two-point `Wire`, only on created sheets), `sheets` (`SheetRef`) and `pages`.
  - The reader keeps `wire`, `junction`, `bus`, `bus_entry`, `bus_alias`, `text`, `polyline` and the other
    graphic heads as opaque slots of the sheet root ("Modelled schematic content"). `sch.opaque_wires` gives
    the points of the opaque wires; nothing else is read from those slots.
  - The writer writes created sheets: symbols, global labels, wires, no-connect flags and pinless sheet
    references. c0269 adds `SheetPin`, sheet pins and hierarchical labels for block sheets.
  - The build always calls `schgen.generate_schematic`. Its guard (`sch_netlist.own_netlist`) reads only the
    narrow grammar of generated sheets: global labels, straight two-pin wires, no junction, no bus.
  - A schematic edited in KiCad is replaced by the next build (`build.schematic-replaced`), and symbol
    positions survive only through `schematic-placements.toml`.
  - `fenolite equivalent` reads a hand-drawn KiCad schematic as a side through `kicad-cli sch export
    netlist`, because the own netlist refuses its grammar.

## Goals / Non-Goals

**Goals**

- A drawn schematic survives builds byte for byte where the target allows, for KiCad and later Altium.
- Code stays the only source of connectivity. Every build and `fenolite check` prove that the drawing
  means the code's netlist, without any tool.
- A read KiCad schematic, hand-drawn or generated, becomes a `schematic.toml` with nothing dropped
  silently: what the model does not hold stays a verbatim opaque item.
- Block sheets of c0269 still work inside a drawing.

**Non-Goals**

- See the proposal.

## Decisions

### 1. Today vs proposed

```python
# Today: the schematic is always generated from the circuit
from fenolite.dsl import Design, Net, Part, connect

design = Design("sensor")
u1 = Part("U1", "Fenolite:MCU_QFN32", footprint="Fenolite:QFN32_5x5", value="MCU")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="4k7")
connect(Net("SDA"), u1["12"], r1[1])
connect(Net("+3V3"), r1[2])
# build: schgen lays out U1 and R1, joins SDA and +3V3 with global labels

# Proposed: the same code, plus a drawn schematic kept beside it
design.load_schematic("schematic.toml")
# build: the sheets come from schematic.toml; the build proves they mean the nets above
```

The `schematic.toml` that goes with it (excerpt):

```toml
schema = "fenolite.drawn-schematic.v0"
root = "root"

[[sheet]]
key = "root"
paper = "A4"

[[sheet.symbol]]
part = "U1"
unit = 1
at = [101.6, 76.2]
rotation = 0

[[sheet.symbol]]
part = "R1"
unit = 1
at = [127.0, 63.5]
rotation = 90
fields.Reference = { at = [129.54, 62.23], rotation = 0, justify = "left" }

[[sheet.wire]]
pts = [[111.76, 68.58], [127.0, 68.58], [127.0, 67.31]]

[[sheet.junction]]
at = [120.65, 68.58]

[[sheet.label]]
kind = "local"
text = "SDA"
at = [115.57, 68.58]

[[sheet.power]]
symbol = "power:+3V3"
net = "+3V3"
at = [127.0, 55.88]
```

### 2. The file `fenolite.drawn-schematic.v0`

- **Root keys:** `schema` (exactly `fenolite.drawn-schematic.v0`), `root` (the key of the root sheet),
  `[[sheet]]` (one or more). Unknown keys, missing keys and wrong types raise `FormatError` (`FEN-3004`)
  naming the file and the locator (`sheet[2].wire[5].pts`).
- **Numbers.** Read with `tomllib` and `parse_float=Decimal`, as `schematic-placements.toml` is. Positions
  and sizes are millimetres; each value times 10^6 must be a whole number of nanometres, else
  `FormatError`. Rotations are 0, 90, 180 or 270 degrees for symbols, labels, sheet pins and power
  symbols (the frames the writer emits); field rotations are 0 or 90.
- **Sheet keys** match the module-name pattern; `root` is free. Each `[[sheet]]` holds:

| table | keys | meaning |
|---|---|---|
| sheet | `key`, `paper`, `title_block` (optional), `generated` (optional, default false) | one drawn sheet |
| `symbol` | `part`, `unit`, `at`, `rotation`, `mirror`, `fields.<name>` (`at`, `rotation`, `justify`, `hide`) | a unit of a code component, keyed by its path relative to the instance's module |
| `power` | `symbol`, `net`, `at`, `rotation`, `fields.<name>` | a power symbol: a global connection named `net`; its `#PWR` reference is assigned by the writer |
| `wire`, `bus` | `pts` (two or more points) | a polyline; each pair of points is one segment |
| `bus_entry` | `at`, `size` | a bus entry from `at` to `at + size` |
| `junction` | `at`, `diameter` (optional) | a junction |
| `no_connect` | `at` | a no-connect flag |
| `label` | `kind` (`local`, `global`, `hierarchical`), `text`, `at`, `rotation`, `shape` (global and hierarchical) | a label |
| `bus_alias` | `name`, `members` | a bus alias of this sheet |
| `sheet_ref` | `key`, `sheet`, `module`, `name`, `file` (optional), `at`, `size`, `page`, `[[pin]]` (`name`, `shape`, `at`, `rotation`) | a sheet reference to a drawn sheet; `module` is the code module path, relative to the parent instance's module, whose parts the instance shows |
| `opaque` | `kicad` (one S-expression), `altium` (optional record text) | an item the model does not hold, kept verbatim |

- **Repeated sheets.** Two `sheet_ref`s may name the same `sheet`. Each reference is one instance; its
  symbols are the components `<module>/<part>`. The drawn sheet is written once per target where the target
  supports it (KiCad: one file with one `instances` path per reference) and once per instance otherwise
  (Altium in this change, decision 10).
- **What the file never holds:** values, references, footprints, properties other than field poses, and
  nets as such. Labels carry text because the drawing needs it; their meaning is checked (decision 6).
- **Canonical form.** `fenolite.lens.drawn.write_drawn(drawn) -> str` writes keys in the order of the
  table above, sheets in page order, items in file order, numbers as the shortest exact decimal of
  millimetres, and ends with a newline. Reading and writing a canonical file gives its bytes.
- **Schema file.** `schemas/fenolite.drawn-schematic.v0.json` describes the TOML as JSON (for editors);
  `tests/consistency` checks it against the reader's closed key sets.
- **Alternatives considered.**
  - JSON (`schematic.json`). Rejected: the research and the other source-tree files (`placements.toml`,
    `edits.toml`, the lock) are TOML, and people edit it.
  - Python (`design.wire(...)` calls). Rejected: thousands of segments in `design.py` bury the circuit,
    and the drawing is CAD-owned (decision 9), so a tool rewrites it; rewriting Python is a non-goal of
    c0250.
  - Integer nanometres in the file. Rejected for readability; exact decimals give the same values.

### 3. Model

- `fenolite.model.schematic` gains `Junction(position, diameter=0)`, `BusWire(start, end)`,
  `BusEntry(position, size)` and `BusAlias(name, members)`, entities with the common header, and
  `SchematicSheet` gains `junctions`, `buses`, `bus_entries` and `bus_aliases`, ordered and omitted when
  empty. Only created sheets hold them; a read sheet keeps them as opaque slots, as it does wires.
- `fenolite.model.drawn` holds the value of the file: `DrawnSchematic(root, sheets)`, `DrawnSheet`,
  `DrawnSymbol`, `DrawnPower`, `DrawnLabel`, `DrawnSheetRef`, `DrawnPin`, `DrawnOpaque` and the field pose
  `DrawnField`, frozen, integer nm and µdeg. It is the input of the lowering, the resolver and level S of
  c0278. It names components by path, never by reference.
- **Alternatives considered.** Lowering the file directly to `SchematicSheet`s and resolving those.
  Rejected: a `SchematicSheet` needs references, values and embedded symbols, which come from the build;
  the resolver and the extraction need a value that both a file and a read sheet give.

### 4. The connectivity resolver

`fenolite.model.drawn_connect.resolve(drawn, pins, *, design_name) -> DrawnNetlist` is pure: no file, no
tool, no float. `pins` gives, for each drawn symbol, the connection points of its unit's pins in the sheet
frame (number, point, electrical type, hidden), computed by the caller from the symbol definition with the
existing "Pin connection points" function of `kicad-schematic`.

Rules, each recorded in `docs/formats/kicad/schematic.md` with S-0046 or S-0367 and its label:

| item | joins | label |
|---|---|---|
| wire segment | the points at its two ends, and a label anchor or a junction lying on its inside; segments join where their ends meet | `INFERRED` until `H-K-DRAWN-CONNECT` |
| T and crossing | a segment end lying on another segment's inside (a T), and crossing segments, join only through a junction on that point; a pin joins a wire at the wire's end only (`H-K-SCH-WIRE-END`) | measured locally with `kicad-cli` 9.0.9 and 10.0.6 on 2026-10-29; `INFERRED` until `H-K-DRAWN-CONNECT` passes in CI |
| junction | every segment end, segment inside and pin point at its position | `INFERRED` until `H-K-DRAWN-CONNECT` |
| local label | groups of one sheet instance with labels of the same text | `INFERRED` until `H-K-DRAWN-CONNECT` |
| global label, power symbol | groups of every sheet with the same text (power: its net) | KiCad manual (S-0046); measured by `H-K-DRAWN-CONNECT` |
| hidden `power_in` pin | the global net named by the pin name | KiCad manual (S-0046) |
| hierarchical label | the sheet pin of the same name on the reference of that instance | `INFERRED` until `H-K-DRAWN-CONNECT` |
| bus, bus entry, bus label | bus members `NAME[a..b]` and groups `{A B}` (aliases expanded) carry member nets between sheets through bus labels and sheet pins; a wire on a bus entry joins only through its own label | `INFERRED` until `H-K-DRAWN-BUS` |
| repeated sheet | one set of nets per instance; global nets shared | `INFERRED` until `H-K-DRAWN-REPEAT` |
| no-connect flag | marks a pin as intentionally open | S-0367 |

- **Result.** `DrawnNetlist.nets`: per net, the members as `(component path, pin number)`, the name the
  resolver gives it, and the items that name it. Also: pins in no net (open), dangling segment ends, labels
  on no group, sheet pins without a label, bus members that no label carries.
- **Names.** The name of a net follows `H-K-DRAWN-NAMES`: a global label or power net keeps its text; a net
  named only by local or hierarchical labels is `/<sheet names from the root>/<text>`; an unnamed net takes
  the existing rule of "Names of unconnected-pin nets" and `netnames`. Ties go to the label text that sorts
  first. Until the hypothesis is measured, names are compared as warnings only.
- **Order independence.** The result does not depend on the order of items or on how a wire is split into
  segments (a property test splits and joins segments).
- **Alternatives considered.**
  - Widening `sch_netlist.own_netlist`. Rejected: its grammar is a proof that the generator stays simple,
    and the build's guard for generated sheets must keep refusing anything else.
  - Always using `kicad-cli sch export netlist`. Rejected for builds and checks: they stay hermetic. The
    tool is the oracle of the resolver in CI (task 7.1), not a dependency.
  - Placing the resolver in `fenolite.schematic`. Rejected: that package is presentation-only and must not
    import the model ("Allowed import edges").

### 5. The build

- `Design.load_schematic(path)` records the path, relative to the script's folder, once per design
  (`DslError` on a second call, an absolute path or a path outside the script's folder). `to_model` is
  unchanged.
- `cmd_build` reads the file with `lens.drawn.read_drawn` (a `FormatError` exits 3) and passes the value to
  `build_design(..., drawn=...)`.
- `build_design` replaces the `schgen.generate_schematic` call with
  `backends.kicad.drawn.lower_drawn(drawn, design, parts, name=, target=, vendor=, allow_lossy=)`, which
  returns a `GeneratedSchematic` like the generator, so every later step is unchanged: symbols and
  libraries, `sym-lib-table`, `lower_for_schematic`, the board's footprint paths.
- **Coverage.** Before lowering, every unit of every component with a resolved symbol must be drawn exactly
  once per instance (`drawn.symbol-missing`, error), and every drawn part must exist in code
  (`drawn.part-unknown`, error). A missing unit of a multi-unit symbol that has no pin on a net is a warning
  (`drawn.unit-missing`).
- **Guard.** After writing the texts in memory, the build reads them back with `read_schematic`,
  extracts them (decision 8), resolves them and compares the nets with the circuit (decision 6). Any
  connectivity difference gives `build.schematic-netlist-differs` (the existing code) and no file. The
  guard therefore proves the bytes that would be written, not only the file that was read.
- `schematic-placements.toml` is not read when a drawn schematic is loaded, and its presence gives
  `drawn.placements-ignored` (warning): two files must not own symbol positions.
- `result.schematic` gains `source` (`generated` or `drawn`) and `drawn` (the file name and the counts of
  wires, junctions, labels, buses and opaque items), both `null` for generated schematics.
- **No byte change** for designs that do not call `load_schematic`.

### 6. Code and drawing cannot drift

`fenolite.model.drawn_connect.compare(netlist, circuit) -> tuple[Issue, ...]` compares the drawn nets with
the circuit's nets as partitions of `(component path, pin number)`, restricted to components with a drawn
symbol:

| code | severity | when |
|---|---|---|
| `drawn.netlist-differs` | error | a pin that the drawing puts in another group than code, or that code connects and the drawing leaves open, or the reverse; the message names the first `REF-PIN`, both nets and the reason (`split`, `merged`, `open`) |
| `drawn.net-name-differs` | warning | equal groups whose drawn name differs from the stored name of the code net |
| `drawn.symbol-missing` | error | a unit of a code component with a resolved symbol that the drawing lacks |
| `drawn.part-unknown` | error | a drawn symbol whose part is not a component of code |
| `drawn.unit-missing` | warning | a missing unit with no pin on any net |
| `drawn.dangling` | warning | a segment end that joins nothing |
| `drawn.label-unconnected` | warning | a label on no group |
| `drawn.sheet-pin-unmatched` | error | a sheet pin without a hierarchical label of its name in the instance's sheet, or the reverse |
| `drawn.sheet-unknown` | error | a `sheet_ref` naming no sheet, a sheet cycle, or a sheet that no reference reaches |
| `drawn.repeated-value-differs` | error | components shown by one symbol of a repeated sheet whose values or footprints differ (a KiCad repeated sheet carries one value per symbol, `H-K-DRAWN-REPEAT`) |
| `drawn.bus-member-unknown` | warning | a bus label member that no alias or vector defines |
| `drawn.placements-ignored` | warning | `schematic-placements.toml` beside a script that loads a drawn schematic |
| `drawn.opaque-dropped` | info | an opaque item the target cannot carry (Altium, decision 10) |

- Errors stop a build (exit 5) and fail the `schematic.drawn` stage. Warnings are reported.
- Codes live in `fenolite.model.drawn_connect.ISSUE_CODES` and join the build's closed set and
  `explain.toml`. There is no new `FEN-` code: a bad file is `FEN-3004`, findings exit 5.

### 7. The check stage `schematic.drawn`

- `fenolite.checks.drawn.drawn_stage(netlist, circuit) -> StageResult` runs `compare` on a netlist the
  command computes and injects, as the roles stage takes its judge, so `checks` imports no backend.
- `cmd_check` computes the netlist for built input whose `.fenolite/build.json` records
  `schematic.source == "drawn"`: it reads the project's sheets as they are on disk, extracts and resolves
  them. The stage is then part of the default set; for any other input it is not listed.
- A sheet edited in KiCad that still means the code passes. One whose connectivity was changed fails with
  `drawn.netlist-differs`, naming the pin, so the user changes the code (or `fenolite edit`) or reverts the
  drawing.

### 8. Reading a KiCad schematic into the file

`fenolite.backends.kicad.drawn.extract(root, children, *, components) -> tuple[DrawnSchematic,
tuple[Issue, ...]]` takes read sheets (`read_schematic` and `sheet_files`) and the map from instance path and
reference to component path:

- Modelled items map directly: symbol instances (pose, unit, field poses from their property slots), labels,
  no-connect flags, sheet references with their pins (c0269's `sch.opaque_sheet_pins`).
- Opaque root slots with the heads `wire`, `bus`, `bus_entry`, `junction` and `bus_alias` are parsed into
  drawn items by `sch.opaque_drawing`, as `sch.opaque_wires` already parses wires; a slot whose numbers are not whole nanometres
  stays an opaque item with `kicad.sch.inexact-length`.
- A symbol whose reference starts with `#` and whose definition is a power symbol becomes a `power` item
  named by its value. A power flag stays a `power` item of the flag library.
- A symbol whose reference maps to no component gives `drawn.part-unknown` and stays an opaque item, so
  nothing is lost and the user sees it.
- Every other root slot (`text`, `text_box`, `polyline`, `rectangle`, `image`, `table`, `netclass_flag`,
  `rule_area`, and unknown heads) becomes an `opaque` item with its fragment verbatim and its minimum
  version.
- Sheets referenced several times become one drawn sheet with several `sheet_ref`s.
- **Frozen bytes.** Decided 2026-10-29: a frozen generated schematic, lowered again, gives the generated
  texts with the same symbols, fields, references, positions, sheets and board; labels, wires, junctions,
  no-connect flags and power flags get new uuids, because the file holds no uuid and drawn items take their
  ids from their sheet and index (decision 12). The value is a fixed point: extracting the lowered texts
  gives the frozen value again.
- **Sheet pins.** c0269 is not merged: this change adds the minimal stub it specifies (`SheetPin` with
  `name`, `shape`, `position`, `rotation`; `SheetRef.pins`; the writer's `pin` child; `sch.opaque_sheet_pins`),
  to be reconciled with c0269 when it lands.
- **Users.** c0275's importer writes the result as `schematic.toml`. `fenolite sync --to-source` writes it
  for a design that loads a drawn schematic (decision 9). Freezing a generated schematic is the same call
  on the sheets the generator wrote.

### 9. Ownership: CAD owns the drawing, code owns the nets (c0250)

- The drawing is CAD-owned, like the layout: `fenolite sync DESIGN --out DIR --to-source` reads the built
  project's sheets, extracts them and plans `schematic.toml` beside the script when its text differs. It
  first resolves the sheets and compares them with the recorded circuit; a connectivity difference refuses
  the write (exit 5, `drawn.netlist-differs`), because a sync never changes nets.
- Values, footprints and references edited in KiCad's schematic editor keep c0250's three-way merge into
  `edits.toml`; the drawn file holds none of them, so the two files never disagree.
- `fenolite sync ... --to-source --freeze-schematic` writes `schematic.toml` from a generated schematic and
  gives the info `drawn.frozen` with the hint to add `design.load_schematic("schematic.toml")`. The script
  is never rewritten.
- **Alternatives considered.** A three-way merge of drawing items. Rejected for v0: items have no stable
  identity across tools, and the drawing has one owner.

### 10. Altium (later phase of this change)

- `fenolite.backends.altium.drawn.lower_drawn(...)` writes one sheet per drawn sheet instance: wires and
  buses as polylines, junctions, local labels as net labels, hierarchical labels as ports, sheet references
  as sheet symbols with sheet entries, power symbols as power ports, global labels as power ports of the
  label's text (power ports are global in every scope, S-0185), bus entries, and no-connect directives.
- Coordinates map through the writer's existing unit conversion. A coordinate that has no exact Altium form
  is a lossy write: refused with `FEN-7001` (exit 7) unless `--allow-lossy`, which rounds and reports each
  rounding.
- Repeated sheets are written once per instance in this change (`drawn.altium-repeat-flattened`, info).
  Multi-channel sheet symbols with an annotation file are a follow-up (open question 3).
- Opaque items are dropped with `drawn.opaque-dropped` (info) unless they hold an `altium` record text.
- Evidence `INFERRED` until the kit compiles `examples/drawn/` with the nets of code (`H-A-DRAWN-WRITE`).
- If the maintainer prefers, this phase is cut to a follow-up change; phases 1 to 6 do not depend on it.

### 11. Generated sheets inside a drawing (c0269)

- A drawn sheet with `generated = true` holds no items of its own. For each `sheet_ref` that names it,
  the build runs the generator for that module instance with c0269's block rules (hierarchical labels from
  ports, groups, shared arrangement) and writes the file `schgen.sheet_file(<module path>)`.
- The drawn `sheet_ref` must carry the sheet pins the generator gives, by name and shape; a missing or
  extra pin is `drawn.sheet-pin-unmatched`. Their positions on the box are the drawing's.
- So a person can draw the top sheet and leave blocks to the generator, and a block sheet can be frozen
  later (decision 9).

**Decided 2026-10-30 (implementation):** the generator runs once on the whole design, as a generated build
runs it, and each instance of a `generated` sheet takes the generator's sheet of its module and of its
sub-modules unchanged, so those files are byte-equal to a generated build's. Their symbols' paths are the
generator's, so the instance must stand where the generator puts the module (its reference in the sheet of
the parent module, with the generator's uuid, which the drawn reference already takes when it is the only one
of its module); else `drawn.sheet-unknown`. The block sheets put labels on the sheet pins of their
sub-blocks without a wire; the resolver joins a label to a sheet pin at its point, as to a symbol pin
(measured equal to `kicad-cli` 10.0.6 on the block example).

### 12. Writer additions for KiCad

`sch.write_schematic` writes the new entities of created sheets in the form of S-0367 for both targets:
`junction` (`at`, `diameter`, `color`, `uuid`), `bus` (`pts`, `stroke`, `uuid`), `bus_entry` (`at`, `size`,
`stroke`, `uuid`), `bus_alias` (`members`), local labels (`label`), power symbols as symbol instances of
their embedded power definitions, and opaque items verbatim through `versions.check_emittable`. Root order:
no-connect flags, junctions, bus entries, wires, buses, labels, symbols, sheet references, opaque items
(in their drawn order), then `sheet_instances`. Ids derive from the design name, the sheet key, the item
kind and its index in the drawn sheet, so a rebuild gives the same uuids (`pcb.kicad_uuid`).

**Decided 2026-10-29 (implementation):** the writer cuts each wire at the junctions on it and each bus at
its junctions and bus entry ends, the form KiCad's editor keeps. `kicad-cli` 9.0.9 loses the corner of a
wire whose inside holds a junction, and leaves bus entries on an uncut bus unjoined; the cut form is joined
by 9.0.9 and 10.0.6 alike and joins nothing the junction did not join. A slanted wire segment is written as
an opaque `wire` item, since the model's `Wire` stays horizontal or vertical. A drawn symbol with field
poses shows its posed fields only and hides the others at its origin. Ids of drawn symbols are the
generator's (`<name>:<component path>#<unit>`), and a sheet reference keeps the generator's id
(`<name>:sheet:<module>`) when its instance is the only one of its module, so a frozen schematic keeps the
board's footprint paths; labels, wires, junctions and flags take their ids from the sheet key and index.

### Data flow

```
design.py ──to_model──▶ Circuit ───────────────┐
schematic.toml ─read_drawn─▶ DrawnSchematic ─lower_drawn─▶ SchematicSheets ─write─▶ .kicad_sch texts
                                                                                     │ read back
                              DrawnSchematic ◀─extract── read sheets ◀───────────────┘
                                     │ resolve (pins from symbol definitions)
                                     ▼
                              DrawnNetlist ──compare──▶ issues (build guard, check stage, sync)
```

## Codes introduced

The `drawn.*` codes of decision 6, plus `drawn.frozen` (info, decision 9) and
`drawn.altium-repeat-flattened` (info, decision 10). Existing codes reused:
`build.schematic-netlist-differs`, `FEN-3004`, `FEN-7001`, `kicad.sch.inexact-length`.

## Hypotheses registered by this change

| id | statement | settled by |
|---|---|---|
| `H-K-DRAWN-CONNECT` | The resolver's nets (wires, T joints, crossings, junctions, local, global and hierarchical labels, power symbols, hidden power pins) equal `kicad-cli sch export netlist` on the authored drawn fixtures and the demo rows | KiCad CI job, 9.0.x and 10.0.x |
| `H-K-DRAWN-NAMES` | The resolver's net names equal the names of KiCad's netlist export | KiCad CI job |
| `H-K-DRAWN-BUS` | Bus members carried by bus labels, entries, aliases and sheet pins give the nets KiCad exports | KiCad CI job |
| `H-K-DRAWN-REPEAT` | A sheet file named by several sheet references gives one set of local nets per instance, references per `instances` path, and one value per symbol | KiCad CI job |
| `H-K-DRAWN-WRITE` | A drawn sheet written by Fenolite loads in `kicad-cli`, its netlist equals the source's, and ERC reports no violation that the source lacks | KiCad CI job |
| `H-A-DRAWN-WRITE` | Altium compiles the written drawn example with the nets of code and no connectivity message | maintainer's kit |

## Evidence level per behaviour

| behaviour | level before merge |
|---|---|
| file reading, canonical writing, schema | `INFERRED`, unit and property tests |
| resolver | `INFERRED`; `KICAD-VERIFIED (9.0.x, 10.0.x)` per hypothesis once the CI job passes |
| KiCad writing | `KICAD-VERIFIED (9.0.x, 10.0.x)` once `H-K-DRAWN-WRITE` passes |
| extraction | `INFERRED`; level S of c0278 compares extract(write(extract(x))) with extract(x) |
| Altium writing | `INFERRED` until `H-A-DRAWN-WRITE` |

## Risks / Trade-offs

- **KiCad's connectivity has corners** (labels on wire insides, pins on wire insides, bus label syntax,
  hierarchical net names). Mitigation: connectivity errors are partitions, which the CI oracle checks on
  every demo row; names are warnings until measured; an unknown construct stays opaque and the extracted
  sheet then fails the comparison loudly instead of guessing.
- **Large files.** A real board's drawing has thousands of segments. Mitigation: one table per item kind,
  numbers short, canonical order; the reader is linear. Measured on the demo rows (task 7.2).
- **Repeated sheets and per-instance values.** A KiCad repeated sheet holds one value per symbol. Code may
  give instances different values; that is refused with `drawn.repeated-value-differs` and a hint to split
  the sheet.
- **Ownership surprises.** A user moves a wire in KiCad and forgets `sync`: the next build restores the
  drawing from the file. Same rule as the layout; `build.schematic-replaced` still warns and keeps the
  backup.
- **Generated sheets inside a drawing** give two layouts on one project. Accepted: it is opt-in per sheet.

## Open Questions

1. **May a drawing introduce a net name the code lacks** (a label naming an unnamed code net)? Recommended:
   yes, as `drawn.net-name-differs` warning; the board keeps code names.
   Decided 2026-10-29: yes, as the warning `drawn.net-name-differs`; the board keeps the code's names. A
   drawn net whose labels include the code net's name gives no warning.
2. **Should text and graphics become model entities** instead of opaque items? Recommended: later, with
   c0269's open question 2; opaque items already round-trip for KiCad.
   Decided 2026-10-29: later; they stay verbatim opaque items in v0.
3. **Altium repeated sheets**: write multi-channel sheet symbols and an annotation file, or one sheet per
   instance? Recommended: one sheet per instance now, multi-channel after a kit case.
   Decided 2026-10-29: one sheet per instance when the Altium phase is written; multi-channel after a kit
   case.
4. **Cut the Altium phase into its own change?** Recommended: keep it as phase 6, cut it if the kit is not
   available within the release.
   Decided 2026-10-29: keep it as phase 6 of this change, left open in this batch (tasks 6.1 and 6.2); cut it
   to a follow-up if the kit is not available within the release.
5. **Freeze by default for imported boards only?** Recommended: yes; designs written as code keep the
   generator unless the user freezes.
   Decided 2026-10-29: yes; designs written as code keep the generator unless the user runs `sync
   --to-source --freeze-schematic`.

## Relation to the other changes of this batch

- **c0275 board-to-code:** calls `extract` and writes `schematic.toml` and `design.load_schematic(...)`.
- **c0277 dsl-board-coverage:** board items only; its opaque-item rule for boards matches decision 2.
- **c0278 fidelity-proof:** level S compares two `DrawnSchematic`s and uses `resolve` for drawn
  connectivity.
- **c0279 board-library:** every library board carries a `schematic.toml` and passes the drawn stage.
- **c0269 block-schematic:** provides sheet pins; decision 11 reuses its block rules.
- **c0250 manual-edit-merge:** decision 9.
- **c0249 design-lock:** references in the lock, never in the drawing.
- **c0264 library-import, c0266 device-packs and c0279 fenolite-library:** power and part symbols of a drawing resolve like any part
  symbol, so a vendored `lib/` or an item vendored by `fenolite get` provides them.
