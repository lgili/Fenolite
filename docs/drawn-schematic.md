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
R2/R3 form the input pull-down to GND; the existing parent wire is explicitly named IN.
Only the two unused input pins U1-11/U1-12 carry intentional no-connect marks.

A KiCad project imported with `import --to python` carries this file and the source's embedded symbol
definitions. Its actual drawing is built and checked before staging, including hidden power-pin
connectivity. Incompatible embedded definitions, a missing source symbol or an unrepresentable source
pose refuse explicitly; the originals remain unchanged. Board-only imports keep generated symbols.
Property-only local snapshots use a required closed [context index](symbol-contexts.md) and full native
assets. Every occurrence retains its complete property nodes; the cache is keyed by sheet and digest.
Protected defaults, pin/body/flag differences, same-file duplicates and contextual inheritance refuse.
The actual written AST is checked before staging, including repeated and opaque properties.
Pinless native graphic symbols excluded from both board and BOM stay opaque, with their embedded
definitions preserved. An explicitly board/BOM-excluded instance may also stay opaque when its
non-power definition has only visible passive pins; its native export contributes no circuit nodes.
Hidden or active pins, power definitions, missing exclusions and missing definitions refuse.
The instance's explicit exclusions apply even when library defaults differ; those defaults stay intact.
Source-local bare embedded aliases use their original library namespace in the vendored project, or
`_Source` when the original id is also bare. Their native geometry stays unchanged; conflicting bodies
under the resulting identity still refuse.

A unit may select a different native library `symbol`, preserving source-local per-unit bodies. Its
logical pin numbers, names, types and hidden states must match that unit of the code's primary symbol;
pin positions and graphics may differ. Build/check/sync retain the binding relative to code, including
pin-pad variants, and the written-byte guard checks its actual connections. Missing, incompatible or
conflicting same-unit bindings refuse. Level S compares the per-unit binding too.

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
| `symbol` | `part`, `unit` (default 1), `at`, `rotation` (0, 90, 180, 270), `mirror` (`x`, `y` or none), `symbol` (optional library id), `fields` | one unit of a code component, named by its path relative to the module of the sheet's instance |
| `fields.<name>` | `at`, `rotation` (0 or 90), `justify` (words of `left`, `right`, `top`, `bottom`, `mirror`), `hide`, optional `font` | the pose of one field; a symbol with poses shows the posed fields only, the others hidden at its origin; without poses the writer places `Reference` and `Value` |
| `font` | optional `size`, `thickness`, `bold`, `italic`, `face` | a nonempty font value; `size` is `[width, height]` in mm with both axes positive; `thickness` is nonnegative mm; flags are booleans; `face` is a font name, never a font file |
| `power` | `symbol`, `net`, `at`, `rotation`, `mirror`, `fields` | a power symbol: a global connection named `net`, drawn with the library symbol `symbol`; optional `mirror` is empty, `x` or `y`; its `#PWR` reference is assigned by the writer |
| `wire`, `bus` | `pts` (two or more points) | a polyline; each pair of points is one segment |
| `bus_entry` | `at`, `size` | a bus entry from `at` to `at + size` |
| `junction` | `at`, `diameter` (optional) | a junction |
| `no_connect` | `at` | a no-connect flag |
| `label` | `kind` (`local`, `global`, `hierarchical`), `text`, `at`, `rotation`, `shape` (global and hierarchical: `input`, `output`, `bidirectional`, `tri_state`, `passive`), optional `font`, `justify`, `intersheet_refs` | a label; `intersheet_refs` is a field-pose table allowed only for a global label, with fixed native name/text |
| `bus_alias` | `name`, `members` | a bus alias of this sheet; on a bus, write it as `{NAME}` |
| `sheet_ref` | `key`, `sheet`, `module`, `name`, `file` (optional), `at`, `size`, `page`, optional `fields`, `properties`, `[[pin]]` | a reference to the drawn sheet `sheet`; `module` is the code module, relative to the module of the instance that holds the reference (`""`: the same module), whose parts that instance shows; property poses may name only `Sheetname` and `Sheetfile` |
| `properties.<name>` | required `text` and `at`; optional `rotation`, `justify`, `hide`, `font` | ordered custom sheet-reference metadata; empty text is preserved; names are unique and cannot be `Sheetname` or `Sheetfile` |
| `pin` | `name`, `shape`, `at`, `rotation`, optional `font`, `justify` | a sheet pin of a reference |
| `opaque` | `kicad` (one S-expression), `altium` (optional) | an item the model does not hold (text, graphics, images, tables), kept verbatim |

`fenolite.lens.drawn.write_drawn` writes the canonical form: the root keys, then the sheets in page order,
keys in the order of the table, items in their order, numbers as the shortest exact decimal of
millimetres, and a final newline. Reading and writing a canonical file gives its bytes.

Change c0326 adds `DrawnFont` in `fenolite.model.drawn` and the optional codec keys
above. Omission, explicit false and zero retain their exact canonical presence;
none of them promises a distinct native style state. Lengths remain integer nm.
For labels/pins, omitted justification keeps the legacy role-selected anchor,
while `justify = ""` explicitly centres the text. Other justification is written
as single-space-separated words without leading/trailing whitespace. Field poses
carry no text override: Reference, Value and Footprint remain code-owned.
Native font preservation and effective-style/render proofs are separate c0326
tasks; the model/codec checkpoint alone does not establish native support.

KiCad drawn read/write preserves these fonts on fields, labels, sheet pins and
sheet-name/file poses. Native extraction compares effective defaults proved by
the target observations; it does not turn canonical false/zero into invented
native tokens. The current schematic scene supports both size axes and text
justification. The authored stroke renderer supports explicit thickness, bold
weight and italic shear (c0337). Explicit thickness wins over automatic bold
weight; effective false/zero retains the default scene. Positive sub-µm thickness,
named faces and text mirror refuse with `FEN-3004` before a mask can pass.
Hidden field styles retain native data without visible ink. Style-sensitive
masks remain authored glyph-box envelopes, not a claim that Fenolite glyphs
match native KiCad raster shapes. Native-writing/S proofs remain separately
scoped to their actual level selection. Opaque free text also retains its
validated native RGB in the view; typed font colour stays unsupported. The
all-zero colour sentinel keeps the palette default. Native10 free-text export
ignores alpha in the recorded authored controls; original RGBA stays preserved.
Level8 uses BW geometric masks and does not judge RGB equality.

The exact model can hold positive sub-µm sizes; the current native/render boundary
refuses them explicitly. It never substitutes 1.27 mm after µm rounding, and a
1 µm axis stays small. Level 8 still compares the existing text envelopes with
unchanged thresholds; it is not an oracle proof of actual native glyph ink.

## Global-label inter-sheet reference fields

`intersheet_refs = { at = [15, 22], rotation = 90, justify = "right", hide = true }`
keeps the pose of one global-label `Intersheetrefs` property. Its native text is
always `${INTERSHEET_REFS}`; arbitrary names/text and duplicate properties refuse.
The table accepts the same optional font as a field pose. Canonical default
`DrawnLabel.intersheet_refs=None` is appended and omitted, preserving old values.
Only `global` labels may carry it. Hidden poses are preserved too: actual KiCad
project settings can display the field despite its stored hide flag.

The native pipeline writes the placeholder for KiCad to resolve from the project.
Effective viewer text additionally needs the actual project settings and selected
sheet instance. That contextual viewer work and exact-head validation are separate
pending c0348 gates; a typed native round trip alone does not certify that view.

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

Read KiCad sheets resolve `/` and `{slash}` spellings as one native connection name, including sheet
pins and bus members. Their extracted texts stay unchanged for level S and subsequent writing. This
target rule applies before connectivity resolution; the generic resolver keeps literal names, and
the written-byte guard still refuses distinct code nets that KiCad would join.

The KiCad connectivity view also matches corresponding members on a connected bus: top-level vector
positions in ascending index order and literal group members, while preserving qualified scalar labels.
Bus-only entry ends and junctions keep bus labels on the bus; overbar spans remain literal member text. Same-text scalar
local and hierarchical/global labels join on their own sheet without making another sheet's local label
global. Generic/Altium scope defaults stay unchanged. Authored native9.0.2 controls cover these rules,
disconnected buses, reversed nested-vector negatives, unequal names and missing members (S-1280).

Formatted group prefixes such as `BUS_{A}{D[0..3]}` preserve literal member names `BUS_{A}.D0` through
`BUS_{A}.D3`. Measured subscript, superscript and overbar spans, including nested formatting, do not
open the group. Formatting alone declares no members; malformed braces and unsupported nested groups
cannot fall through as vectors and invent joins. Native 9.0.9/10.0.6 controls retain all pins (c0343).

In the KiCad connectivity view, equal sheet bus ports on separate parent bus
islands do not create parent scalar labels by themselves. A physical bus
connection, an actual matching scalar label or corresponding explicit bus
labels retains the measured connection. One bus label on just one isolated
island does not name the other island's members. Original repeated-sheet
controls pass on native CLI 9.0.9 and 10.0.6; generic/Altium policy and the
extracted source drawing remain unchanged (c0320).
Raw labels, sheet pins and geometry remain unchanged for level S. The two read-only public diagnostics
now have equal complete pin partitions (313/2033pins); unknown-member and dangling warnings remain
visible. Wider native CI and complete conversion/fidelity proofs are separate gates.

## Building

Extraction also preserves a legacy `#PWR` instance without a power flag when its definition has exactly
one hidden power-input pin at the origin named by its value. Its existing hidden-pin connection supplies
the global net; extraction does not add a flag or classify other symbols by their reference alone.

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
| `drawn.coordinate-rounded` | warning | an Altium point rounded only with explicit `--allow-lossy` |
| `drawn.placements-ignored` | warning | `schematic-placements.toml` beside a script that loads a drawn schematic |
| `drawn.opaque-dropped` | info | an opaque item the target cannot carry (the Altium phase) |
| `drawn.frozen` | info | `--freeze-schematic` wrote the file |
| `drawn.altium-repeat-flattened` | info | a repeated sheet written once per instance for Altium (the Altium phase) |

## Corpus measurement

The [drawn census](evidence/drawn-schematic.md) records each manifest demo sheet's input hashes,
tool/format versions, item counts, source/lowered/native partitions, naming outcomes and refusals.
`uv run pytest tests/kicad/schematic/test_drawn_corpus.py -rA` writes per-case metadata before its
strict assertions; the KiCad jobs retain the reports even on failure. Native-only pins and open
singletons stay in the comparison. No CAD payload, accepted-difference list or loss flag is added.
Local measurements name their actual tool version and do not establish the other major's CI result.

The first two fields compare resolver outputs with the original native export.
`lowered_native_partition` instead compares the original native netlist with the
rewritten native export; it does not compare lowered-resolver names. The
[comparison subjects](evidence/drawn-schematic.md#comparison-subjects-retained-producer)
explain this distinction without changing the measurements.

## Altium

`build --target altium` writes drawn sheets in ASCII or binary native form and verifies the actual
native documents, units, shown pin tables, physical pin maps and logical connectivity before staging.
The guard runs again after templates. Compatible unit aliases carry their own bodies and native
library entries; their files bind reviewed plans. Unreadable or missing native content refuses.

Repeated sheets become separate native files. Under Automatic/Global scope, shared local names get
reported qualifications; unique names and Hierarchical/Flat names keep their text. This preserves the
tested pin partition, with explicit text and hierarchy changes. Opaque items without native text are
reported as dropped. A point outside the native fractional grid refuses unless `--allow-lossy`, which
reports every rounding. Source field justification and power field/mirror metadata are not represented;
component mirror geometry is written, with native mirror metadata still unverified. Bus alias declarations
and per-sheet title metadata have explicit unrepresented-metadata findings. Edit the drawing in
`schematic.toml`; Altium-to-drawn sync is unavailable.

New explicit drawn fonts, label/pin justification and sheet-name/file poses have no proved Altium
lowering. Strict builds refuse with `FEN-7001` before planning writes. An explicit `--allow-lossy`
retains one located `altium.not-lowered` finding for each omitted effect or sheet-property pose;
false/zero font members are still explicit source intent. Old absent styles keep the existing
writer path and bytes. This loss report does not establish native application support.

The behavior stays **INFERRED**. Later actual Altium 22.2.1
[compile/save/reopen observations](evidence/altium-drawn-native.md) retain equal
complete native pin partitions, the corrected alias control and all remaining
source ERC/raw name findings. The native kit's no-connectivity-message criterion
(`H-A-DRAWN-WRITE`) remains open. Neither own-reader checks nor these bounded
native observations establish complete application acceptance or drawing identity.

## Custom sheet properties (c0329)

`DrawnSheetProperty` in `fenolite.model.drawn` carries literal custom text and
its supported pose/font. Append values to `DrawnSheetRef.properties`; its empty
default adds no codec key or ordinary output. In `schematic.toml`, for example:

```toml
properties.AuthoredNote = { text = "Bench metadata", at = [5, 5], rotation = 0 }
```

This belongs inside a `[[sheet.sheet_ref]]` table. Quoted names, Unicode and
empty text round-trip exactly; property order is retained. Built-in `fields`
still carries only Sheetname/Sheetfile poses, whose text is taken from `name`
and the resolved `file`. Properties cannot override those built-ins or any
symbol text and do not change electrical connectivity.

KiCad lowering writes supported custom text and poses; S observes their names,
texts and effects, and the scene draws visible text under its existing font
limits. Unknown attributes, repeated names, unsupported display/autoplace
flags, inexact poses and text variables refuse before a plan can be staged.
Altium keeps these as explicit unproved losses under its existing loss policy.
The authored CLI controls expose conflicting meanings of format-9 custom text
`~`: native 9.0.9 draws literal paths, while 10.0.6 treats it as empty. Extraction
and scene rendering refuse that ambiguous legacy value. Format-10 literal tilde
is supported; writing literal tilde to target 9 refuses. These narrow measurements do not close a public corpus,
native application, full combined or exact-head CI gate.

Native empty title metadata is extracted as an explicit blank title pair
`title = ""` (c0339). This keeps an imported blank sheet blank when the board
has a date. Authored omission continues to inherit the board’s title metadata.
The existing pair representation and writer behavior are unchanged; source
absence is no longer mistaken for an authoring request to inherit.

One valid string `href` on opaque free text is preserved without changing its
measured nonvisual glyph rendering (c0337). The view adapts a clone, opens no
URL and adds no clickable-link feature; typed effects remain closed.
