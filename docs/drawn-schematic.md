# Drawn schematics

Fenolite draws every schematic itself unless the design loads a drawn one. A drawn schematic is a file,
`schematic.toml` beside the design script, that holds the drawing of the schematic: symbol poses, wires,
junctions, labels, buses, power symbols and sheets. It comes from KiCad (`fenolite sync --to-source`), from
the generator (`--freeze-schematic`), from another tool (the board-to-code importer of change c0275) or from
a person editing TOML.

**Code owns the nets, CAD owns the drawing.** The drawing never holds a value, a reference, a footprint or
a net. Every build and `fenolite check` prove, without any tool, that the drawing means exactly the
netlist of the script. Change c0276 adds the file; the normative text is the capability `drawn-schematic`
of `openspec/changes/c0276-drawn-schematic/`.

```python
from fenolite.dsl import Design, Net, Part, connect

design = Design("sensor")
u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="4k7")
design.add(u1, r1)
connect(Net("SDA"), u1[17], r1[1])
design.load_schematic("schematic.toml")  # the sheets come from the file, the nets from the lines above
```

`examples/drawn/` is a complete example: a root sheet with a bent wire, a junction, local and global labels
and a power symbol, and the sheet of the module `child` joined through a hierarchical label and a sheet
pin.

## The file

Schema `fenolite.drawn-schematic.v0` (`schemas/fenolite.drawn-schematic.v0.json` describes it for
editors; the reader `fenolite.lens.drawn.read_drawn` is normative). Lengths are millimetres, read as exact
decimals and stored as integer nanometres: a value that is not a whole number of nanometres is refused.
Angles are whole degrees. Any unknown key, missing key, wrong type or bad value is refused with
`FEN-3004` (exit 3), naming the file and a locator such as `sheet[0].wire[1].pts`.

Root keys: `schema` (exactly `fenolite.drawn-schematic.v0`), `root` (the key of the root sheet) and one or
more `[[sheet]]` tables.

| table | keys | meaning |
|---|---|---|
| `sheet` | `key`, `paper`, `title_block` (optional), `generated` (optional, default false) | one drawn sheet; `paper` is one of `A0`–`A5`, `Letter`, `Legal`, `Tabloid` |
| `title_block` | `title`, `date`, `revision`, `organization`, `doc_id`, `responsible`, `approver`, `params` | the sheet's own title block; without it the sheet takes the board's |
| `symbol` | `part`, `unit` (default 1), `at`, `rotation` (0, 90, 180, 270), `mirror` (`x`, `y` or none), `fields` | one unit of a code component, named by its path relative to the module of the sheet's instance |
| `fields.<name>` | `at`, `rotation` (0 or 90), `justify` (words of `left`, `right`, `top`, `bottom`, `mirror`), `hide` | the pose of one field; a symbol with poses shows the posed fields only, the others hidden at its origin; without poses the writer places `Reference` and `Value` |
| `power` | `symbol`, `net`, `at`, `rotation`, `fields` | a power symbol: a global connection named `net`, drawn with the library symbol `symbol`; its `#PWR` reference is assigned by the writer |
| `wire`, `bus` | `pts` (two or more points) | a polyline; each pair of points is one segment |
| `bus_entry` | `at`, `size` | a bus entry from `at` to `at + size` |
| `junction` | `at`, `diameter` (optional) | a junction |
| `no_connect` | `at` | a no-connect flag |
| `label` | `kind` (`local`, `global`, `hierarchical`), `text`, `at`, `rotation`, `shape` (global and hierarchical: `input`, `output`, `bidirectional`, `tri_state`, `passive`) | a label |
| `bus_alias` | `name`, `members` | a bus alias of this sheet; on a bus, write it as `{NAME}` |
| `sheet_ref` | `key`, `sheet`, `module`, `name`, `file` (optional), `at`, `size`, `page`, `[[pin]]` | a reference to the drawn sheet `sheet`; `module` is the code module, relative to the module of the instance that holds the reference (`""`: the same module), whose parts that instance shows |
| `pin` | `name`, `shape`, `at`, `rotation` | a sheet pin of a reference |
| `opaque` | `kicad` (one S-expression), `altium` (optional) | an item the model does not hold (text, graphics, images, tables), kept verbatim |

`fenolite.lens.drawn.write_drawn` writes the canonical form: the root keys, then the sheets in page order,
keys in the order of the table, items in their order, numbers as the shortest exact decimal of
millimetres, and a final newline. Reading and writing a canonical file gives its bytes.

## Repeated sheets

Two `sheet_ref`s may name one sheet. Each reference is one instance: the symbol `R1` of a sheet `channel`
that the references `ch0` and `ch1` show with the modules `ch0` and `ch1` stands for the components
`ch0/R1` and `ch1/R1`. KiCad writes the sheet once, with one `instances` path per reference; local labels
stay on their instance and global nets are shared. One symbol carries one value in KiCad, so the
components it stands for must have equal values and footprints (`drawn.repeated-value-differs`). A cycle of
references, a reference to no sheet and a sheet that nothing reaches are `drawn.sheet-unknown`.

## Connectivity

`fenolite.model.drawn_connect.resolve` gives the nets of a drawing from its geometry, with the pin points
the caller computes from the symbol definitions. The rules, measured against `kicad-cli sch export
netlist` 9.0.9 and 10.0.6 on the authored fixtures (`docs/formats/kicad/schematic.md`, "Drawn schematic
connectivity"):

- a wire joins its ends; wires join where their ends meet; a wire end inside another wire (a T) and a
  crossing join only through a junction on that point; a pin joins a wire at the wire's end only;
- a label joins the wire or pin its anchor touches; local labels join on one sheet instance, global labels
  and power symbols on every sheet, a hidden power-input pin joins the global net of its name, and a
  hierarchical label joins the sheet pin of its name;
- a bus carries the members of its labels and sheet pins (`D[0..3]`, `{SDA SCL}`, aliases); a member joins
  the local labels of its name, and a wire on a bus entry joins only through its own label;
- names: a global label or power symbol names its net; a net named only by local or hierarchical labels is
  `/<sheet names>/<text>`; ties go to the text that sorts first.

## Building

`fenolite build` reads the file (a missing or bad file exits 3 with `FEN-3004`) and draws the sheets from it
instead of generating them; every later step is the same. Before it plans a file, the build checks the
coverage (every unit of every component drawn once per instance: `drawn.symbol-missing`,
`drawn.unit-missing` for a unit with no pin on a net, `drawn.part-unknown`), writes the sheet texts in
memory, reads them back, resolves them and compares the nets with the script: a difference is
`build.schematic-netlist-differs` naming the first `REF-PIN`, and nothing is written.
`result.schematic.source` is `drawn` and `result.schematic.drawn` holds the file and the counts of wire
segments, junctions, labels, bus segments and opaque items; `.fenolite/build.json` records the drawn file.
`schematic-placements.toml` is not read beside a drawn schematic (`drawn.placements-ignored`): two files
must not own symbol positions. The writer cuts each wire at the junctions on it and each bus at its
junctions and bus entry ends, the form KiCad's editor keeps.

## Checking

The stage `schematic.drawn` of `fenolite check` reads the sheets of a built project as they are on disk,
resolves them and compares them with the recorded circuit. It is listed only for a build that recorded a
drawn schematic. A sheet edited in KiCad that still means the code passes; a changed connection fails with
`drawn.netlist-differs`, naming the pin, and a renamed label gives the warning `drawn.net-name-differs`.

## Synchronising and freezing

`fenolite sync DESIGN.py --out DIR --to-source` extracts the drawing of the built sheets
(`fenolite.backends.kicad.drawn.extract`) and plans `schematic.toml` when its canonical text differs. It
first compares the sheets with the recorded circuit: a sync never changes nets, so a connectivity
difference plans nothing and exits 5 with `drawn.netlist-differs`. Values, footprints and references edited
in KiCad stay the business of `edits.toml` (change c0250). The first sync of a hand-written file rewrites it
in its extracted form: one wire per segment and the field poses of every symbol.

`--freeze-schematic` writes `schematic.toml` from a generated schematic, with `drawn.frozen` and the hint to
add `design.load_schematic("schematic.toml")`; the script is never rewritten. A frozen schematic gives the
generated sheets again with the same symbols, references, positions and board, and new uuids for labels,
wires and flags, which take their ids from their sheet and index.

## Generated sheets inside a drawing

A sheet marked `generated = true` holds no item: the generator draws it, with the block rules of change
c0269 (hierarchical labels from the block's ports, block-local groups, one arrangement per block). For each
reference to it, the build writes the generator's sheet of that module instance at
`sheets/<module path>.kicad_sch` (with `.` between the segments), with the sheets of its sub-modules, byte
for byte as a generated build writes them. So a person can draw the top sheet and leave the blocks to the
generator:

```toml
[[sheet.sheet_ref]]
key = "ch0"
sheet = "channel"
module = "ch0"
name = "ch0 (channel)"
at = [101.6, 50.8]
size = [20.32, 10.16]
page = "2"

[[sheet.sheet_ref.pin]]
name = "VIN"
shape = "input"
at = [101.6, 53.34]
rotation = 180

[[sheet]]
key = "channel"
generated = true
```

The reference must carry the sheet pins the generator gives, by name and shape, at the drawing's positions;
a missing or extra pin is `drawn.sheet-pin-unmatched` (error). A generated sheet must show a module that
holds parts, from the sheet of its parent module (its place in the generated hierarchy), and one reference
of a repeated drawn sheet cannot show several modules; else `drawn.sheet-unknown`. A label on a sheet pin's
point joins the pin, as on a symbol pin.

## Codes

| code | severity | when |
|---|---|---|
| `drawn.netlist-differs` | error | a pin in another group in the drawing than in code, or open on one side only |
| `drawn.symbol-missing` | error | a unit with a pin on a net that the drawing lacks |
| `drawn.part-unknown` | error | a drawn symbol of no component, a unit drawn twice, a power symbol in no library |
| `drawn.sheet-pin-unmatched` | error | a sheet pin without its hierarchical label, or the reverse |
| `drawn.sheet-unknown` | error | a reference to no sheet, a cycle, an unreached sheet, a file outside the project |
| `drawn.repeated-value-differs` | error | the components of one symbol of a repeated sheet differ in value or footprint |
| `drawn.net-name-differs` | warning | equal groups whose labels do not carry the code net's name |
| `drawn.unit-missing` | warning | a missing unit with no pin on a net |
| `drawn.dangling` | warning | a wire end that joins nothing |
| `drawn.label-unconnected` | warning | a label on no wire and no pin |
| `drawn.bus-member-unknown` | warning | a bus member that no label carries or no alias defines |
| `drawn.placements-ignored` | warning | `schematic-placements.toml` beside a script that loads a drawn schematic |
| `drawn.opaque-dropped` | info | an opaque item the target cannot carry (the Altium phase) |
| `drawn.frozen` | info | `--freeze-schematic` wrote the file |
| `drawn.altium-repeat-flattened` | info | a repeated sheet written once per instance for Altium (the Altium phase) |

## Altium

Writing drawn sheets as SchDoc records is a later phase of change c0276 and is not implemented yet; until
then a drawn schematic is a KiCad build's.
