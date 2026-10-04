# The design DSL and `fenolite build`

`fenolite.dsl` describes a board in plain Python: parts, nets, net classes, interfaces, an outline and
placements. `fenolite build design.py --out DIR` runs the script and writes a KiCad 9.0 or 10.0
project from it, or, with `--target altium`, an experimental Altium project (see "Building for
Altium"). The DSL uses the standard library and Fenolite's own `core` and `model` only.

Python facts are cited from `docs/evidence/sources.md` (S-0070 … S-0074); KiCad facts from
`docs/formats/kicad/`. Everything else on this page is a Fenolite choice.

## Security: `build` executes the script

`fenolite build` runs `design.py` as the user's own code, in the same process. There is no sandbox:
the script can do anything the user can do. **Never run `build` on a script you do not trust.**
`fenolite build --help` says the same.

## API

```python
from fenolite.dsl import Design, Net, Part, Power, connect, mm

design = Design("blink")  # the name becomes the KiCad file stem
design.board(mm(50), mm(30))  # outline width and height; copper=2 (default) or 4

u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
design.add(u1, r1)  # objects join the design only through add()

vin, drv = Net("VIN"), Net("LED_DRV")
connect(drv, u1[1], r1[1])  # designators: pin numbers first, then pin names
design.add(Power(vin, Net("GND")))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin,))

u1.place(mm(14), mm(15), locked=True)
r1.place(mm(32), mm(9), rot=90, side="bottom")
```

- `Design(name)`, `Module(name)`: containers; `add(*objs)` adds parts, modules, nets and interfaces.
  There is no implicit "current design".
- `Part(ref, lib_id, footprint=None, value="", *, properties=None)`: `lib_id` is a symbol
  `Library:Name`; `footprint=None` falls back to the symbol's `Footprint` property, and `value=""` to
  its `Value` property. `properties` maps user property names to text ("User properties").
- `part[designator]` returns a pin handle; `connect(net, *pins)` joins pins to a net.
- `no_connect(*pins)` marks pins as intentionally unconnected ("No-connect marks").
- `Part.place(x, y, rot=0, side="top", locked=False)`, once per part.
- `Part.field(name, *, dx, dy, rot, layer, visible, size, thickness, justify, outside, gap, locked)`,
  once per field name: where the `Reference` or the `Value` of the part's footprint goes ("Field
  placement"). `fields(design)` returns the requests.
- `Design.moved(old, new)`: a path alias that keeps a renamed part's layout ("Path aliases").
- `Design.board(width, height, copper=2, planes=None)`, once per design. `planes={"In1.Cu": gnd}` (with
  `copper=4`) declares an inner layer as an internal plane on a net (a `Net` or a net name); a plane
  holds one net. It is a build parameter, as `copper` is: the model does not change. The Altium target
  writes the plane (`docs/altium.md`, "Copper"); the KiCad target keeps the signal layer and reports
  `build.plane-not-lowered`. `planes(design)` returns the mapping from layer name to net name.
- `Design.zone(net, *, layers, …)`: one copper zone (pour) per call ("Zones").
- `design.rules.netclass(name, *, clearance, track_width, via_diameter, via_drill, nets)`: every value
  is optional; a net belongs to at most one class.
- `Interface`, `Power(hv, lv)` and `DiffPair(p, n)`: named groups of nets kept in the model. A
  `DiffPair` is not lowered to KiCad (`build.interface-not-lowered`, info).
- `Harness(name, members)`: a named group of nets with different names, such as
  `Harness("SPI", {"MOSI": mosi, "MISO": miso, "SCK": sck})`. `name` is the harness type name and has no
  default; `members` maps an entry name to its net and may not be empty. The order of the entries carries
  no meaning. It is recorded as an interface of kind `harness`. A KiCad build keeps it in `.fenolite/`,
  gives no issue for it and writes the same files with or without it; the Altium build draws it as a
  signal harness with `--altium-sheets modules` (`docs/altium.md`, "Sheets and harnesses").
- `to_model(design)` and `placements(design)` turn a DSL design into a model `Design` and the
  placement requests; `build` calls them.

Nothing of the DSL is re-exported from the root `fenolite` package: the DSL `Design` and the model
`Design` are different classes.

### Names and paths

- A design name matches `^[A-Za-z0-9][A-Za-z0-9_.-]*$`. Module names and refs match `[A-Za-z0-9_.+-]+`.
- A module path is its name at the top and `<parent path>/<name>` below; a component path is
  `<module path>/<ref>`, or `<ref>` at the top.
- Net names are global and literal. A module-local net is named by the script, for example
  `Net(f"{m.path}/FB")`.
- Errors are raised as `DslError` at the offending call, so the traceback points at the script line:
  duplicate paths, duplicate net, class or interface names, two `Net` objects with one name, a net in
  two classes, a second `place()` or `board()`, `copper` other than 2 or 4, one designator on two nets,
  an unknown `side`, an invalid name. Equal refs in different modules are reported by
  `Design.validate()` (`model.duplicate-ref`).

## Units

- A length always carries a unit: `mm()`, `mil()`, `inch()` or `nm()` return an exact `Length` in
  integer nanometres, and a string such as `"2.54mm"` is read with no default unit. A bare number or
  a string without a unit raises `DslError` naming the argument.
- The helpers take `int`, `str` or `float`. A float is converted exactly from its `repr`, which is the
  shortest string that round-trips (S-0073); a value that is not a whole number of nanometres raises.
  So `mm(0.1) == nm(100_000)`, and `mm(1/3)` raises.
- `Length` supports `==`, hashing, `+`, `-`, unary `-`, and `*` and `//` by an `int`.
- Angles are degrees: an `int`, a string (`"30.5"` or `"30.5deg"`) or a float through its `repr`;
  whole microdegrees, normalised to [0°, 360°).

## Ids: the key table

Every object that `to_model` or the build creates gets `derived_id(prefix, "dsl", key)` from
`dsl.KEYS`. Ids depend on names and paths only, never on `--seed` or on the order of calls (see
`docs/design-model.md`, "Ids of design scripts").

| object | prefix | key |
|---|---|---|
| design header | `dsn` | `design` |
| board | `brd` | `board` |
| outline | `out` | `outline` |
| rule set | `rst` | `rules` |
| manifest | `mfn` | `manifest` |
| module | `mod` | `module:<path>` |
| component | `cmp` | `component:<path>` |
| pin | `pin` | `pin:<path>:<number>` |
| net | `net` | `net:<name>` |
| net class | `cls` | `netclass:<name>` |
| interface | `itf` | `interface:<kind>:<name>` |
| layer | `lay` | `layer:<KiCad name>` |
| zone | `zon` | `zone:<zone name>` |

Footprints and pads are keyed by the component path through the KiCad embedder.

## Frame and `BOARD_ORIGIN`

DSL coordinates are board-relative: the origin is the outline's top-left corner and Y points down.
`rot` is the stored footprint angle on both sides. The board is written at
`BOARD_ORIGIN = (100 mm, 100 mm)`, so `place(mm(14), mm(15))` puts the part at (114 mm, 115 mm) in
the KiCad file. This is a Fenolite choice: (0, 0) would put the board under the drawing-sheet border,
and centring on the paper would move every part when the paper size changes.

Parts without `place()` are staged in one row, in component-path order, 5 mm right of the outline and
top-aligned with it, 2 mm apart, on the top side at 0° and unlocked, each with a `layout.unplaced`
warning.

## Scripts

- The script runs with `runpy.run_path` and the run name `__fenolite_build__` (S-0070). While it runs,
  `sys.dont_write_bytecode` is set, `sys.argv` is the script path and the script folder is first on
  `sys.path` (S-0071). Afterwards these are restored, and modules the run imported from the script
  folder are removed from `sys.modules`, so no `__pycache__` is written and a second build sees edited
  sibling modules.
- The script must bind a module-level `design` of type `fenolite.dsl.Design`.
- Its stdout and stderr are captured (S-0074) into `result.script_output`, at most 4000 characters,
  ending in `…[truncated]` when cut, so stdout stays one JSON document.
- Any exception of the script, `SystemExit` and `DslError` included, and a missing `design` are
  `FEN-3004` (exit 3), with `line:<n>` of the deepest script frame as locator when there is one.
  `KeyboardInterrupt` propagates.

## Libraries and pins

- Libraries are resolved by KiCad's tables: `fp-lib-table` and `sym-lib-table` next to `design.py` are
  the recommended source; global and template tables follow `docs/formats/kicad/libraries.md`. Every
  unresolved lib id is listed in the refusal's `issues` (`FEN-3001`).
- Official libraries come from the environment (`KICAD<M>_FOOTPRINT_DIR`, `KICAD<M>_SYMBOL_DIR`), else from
  a verified library cache when `FENOLITE_LIBS_CACHE` names one, else from a local install, each of the
  target's major. The cache is the way to build an official-library design for target 9 on a machine
  with a 10.0 install: `uv run python tools/kicad_libs_fetch.py` makes it. The build never looks for a
  cache by itself.
- `result.libraries` gives the origin of the row that resolved each lib id: `project`, `global`,
  `template`, or `scan` for a row found by scanning a library folder that has no table (always the case
  for a cache). Whatever the table, the placed
  footprints are vendored into the output ("Vendored libraries").
- A designator is a pin number first; otherwise it names every pin with that name. A pin number that
  is also another pin's name gives `build.pin-ambiguous`, and the number wins.
- Pads get the net of the pin with their number. Hidden and power pins create no implicit nets.
- Net or class names that differ only in letter case are refused (`build.name-case-collision`).
  KiCad 9.0.9 and 10.0.6 compare net names in custom-rule conditions without regard to case
  (`H-K-DRU-COND`, `docs/formats/kicad/rules.md`); the build refuses such names whatever is measured.

## No-connect marks

```python
from fenolite.dsl import no_connect

no_connect(u1[11], u1[12])  # NRST and OSC_IN are left open on purpose
```

- `no_connect(*pins)` takes the pin handles that `connect` takes, of one part or of several. A call
  without arguments does nothing, and marking a designator twice keeps one mark. There is no `Part`
  method for marks, no automatic marking of unused pins and no way to remove a mark.
- **Errors.** Any argument that is not a pin handle raises `DslError`. Marking a designator that
  `connect` joined to a net raises `DslError` naming the ref, the designator and the net; connecting a
  marked designator raises `DslError` naming the ref and the designator. The earlier call stays in
  force, and a refused `no_connect` call marks nothing.
- **Stored form.** The designator is kept as written in `Part.no_connects` (`u1[11]` and `u1["11"]` are
  one mark). `to_model` writes `Circuit.no_connects`, one `PinRef(<component id>, <designator>)` per
  mark in `PinRef` order (`docs/design-model.md`), and changes nothing else. A mark belongs to its
  part: it joins the design when the part is added.
- **KiCad target.** The build resolves a mark like a net member: a pin number first, otherwise every
  pin of that name (`build.unknown-pin`, `build.pin-ambiguous`). A pin that is marked and on a net,
  for example by its name in one call and by its number in the other, gives `build.no-connect-on-net`
  (error, exit 5, nothing written). The resolved marks are kept in `.fenolite/circuit.json`. The build
  writes no schematic yet, so the board, project and rules files are byte for byte those of the same
  design without marks; the schematic writer of v0.2a lowers the marks to KiCad's no-connect flags.
- **Check.** `fenolite check` no longer reports `erc.lite.floating-pin` for a marked pin.
- **Altium target.** Each marked pin gets a No ERC directive and no wire stub (`docs/altium.md`,
  "No-connect marks").

## User properties

`Part(..., properties={"Part number": "PN-330", "Supplier code": "S-1"})` gives a part user properties,
such as a part number or a supplier code, as text.

- **Text rules.** Names and values are `str`. A name is non-empty, has no leading or trailing
  whitespace and is printable (`str.isprintable`, S-0105); a value is printable and may be empty. A tab
  or a newline is refused: a multi-line part number is a mistake, and CSV exports would have to quote it.
  Numbers are refused like elsewhere in the DSL (`{"Qty": 2}` is more likely a mistake than a field).
- **Reserved names,** compared after `str.casefold` (S-0105):
  - `Reference` and `Value` come from `ref` and `value`;
  - `Datasheet` and `Description` are fields of the footprint library: every mini footprint carries
    them, and a KiCad 10.0.6 re-save merges a second `Datasheet` node into the field
    (`H-K-VENDOR-DUPNAME`, `KICAD-VERIFIED (10.0.x)`);
  - `Footprint` is removed by a 10.0.6 re-save (`H-K-UUID-KEEP-2`);
  - the prefix `fenolite.` is Fenolite's namespace (`fenolite.path` holds the component path), and the
    prefix `ki_` holds KiCad's own names (`ki_fp_filters`).

  KiCad itself keeps `datasheet` apart from `Datasheet`, but BOM columns and agents would read them as
  one field, so two names equal after `casefold` are refused too. Errors are raised at the `Part` call.
- **Build checks.** The build checks the properties of any model `Design` again: a reserved name gives
  `build.property-reserved`, other invalid text `build.property-invalid`, and a property that the
  footprint library already holds with another value `build.property-conflict` (with the same value,
  nothing is appended). The DSL reads no library, so only the build can see the last case.
- **Order and form.** The properties are written after `fenolite.path`, in code-point order of names,
  each hidden on `F.Fab` at the footprint origin with a 1 mm font (on `B.Fab`, mirrored, for a bottom
  part). Adding one moves no other uuid. KiCad 9.0.9 and 10.0.6 load them without a library mismatch,
  and a 10.0.6 re-save keeps names, values and visibility (`H-K-VENDOR-PROPS`). `Component.properties`
  holds what `read_board` reads back.
- Position, layer, visibility and size of these fields cannot be set yet (field placement, c0030).

## Field placement

`Part.field("Reference", …)` and `Part.field("Value", …)` place the two text fields of the part's footprint.
Without a request a field stays where the footprint library puts it.

```python
u1.place(mm(40), mm(30), rot=90)
u1.field("Reference", outside="top")  # beside the courtyard, 0.25 mm away
u1.field("Value", visible=False)
r1.field("Reference", dx=mm(0), dy="-2.5mm", rot=0, justify="left", locked=True)
```

- **Names.** Only `Reference` and `Value`. Every other property keeps the library's placement; user
  properties are written hidden ("User properties").
- **Frame.** `dx` and `dy` are lengths in the board frame, measured from the part's placement point (the
  point of `place()`, or the staging point), and are given together. `rot` is the angle of the text on the
  board in degrees. Both are independent of the part's own rotation: "2.5 mm above the part, horizontal"
  stays true after `place(…, rot=90)`, and it is the frame in which KiCad's DRC reports a field. Y grows
  downwards, as everywhere in the DSL.
- **`layer`** is `"silk"` or `"fab"`, on the part's side: `F.SilkS` or `F.Fab` for a top part, `B.SilkS` or
  `B.Fab`, mirrored, for a bottom one.
- **`visible`** shows or hides the field. **`size`** is the glyph height and width; **`thickness`** is the
  stroke. Both are positive lengths.
- **`justify`** is `left` or `right`, then `top` or `bottom`, as one string (`"left"`, `"top"`,
  `"right bottom"`). The words are KiCad's and work in the reading frame of the text: from the anchor a
  `left` text runs to +X and a `bottom` text lies above it. A field of a bottom part is mirrored, so its
  `left` text runs to −X on the board (`H-K-FIELD-JUSTIFY`). Without a word the text is centred.
- **`outside`** is `"top"`, `"bottom"`, `"left"` or `"right"`: the field goes beside the box of the
  footprint's courtyard on that side of the board, horizontal, centred on the other axis, with its
  justification pointing away from the box (mirrored fields included). **`gap`** is the distance from the
  box, 0.25 mm by default; half the stroke is added. `outside` decides the position, so `dx`, `dy`, `rot`
  and `justify` cannot be given with it. It uses no font metrics: the text never crosses back over its
  anchor, but a long text beside a small part can still reach a neighbour or the board edge, and the side
  is the script's choice.
- **Keep-upright.** KiCad draws a field whose angle is above 90° and up to 270° turned by half a turn, so
  it never reads upside down, unless the library field is unlocked. `rot=180` therefore looks like
  `rot=0`; the stored angle is still the one given.
- **`locked`.** On a first build every request applies. On a rebuild over an existing board, a field
  edited in KiCad wins over an unlocked request; `locked=True` makes the request win (`docs/lens.md`,
  "Footprint fields").
- **Errors.** Another name, a second request for one field of one part, a request that sets nothing,
  `dx` without `dy`, a bare number for a length and any other value outside these rules raise `DslError`
  at the call. A footprint that has no such field is found by the build (`FEN-3004`).

## Vendored libraries

`fenolite build` copies every footprint it places into `lib/<nickname>.pretty/`, whatever the table row
that resolved it (project, global, template, scan), and writes one `fp-lib-table` row per nickname. A built
project therefore needs no global or template table: `kicad-cli`, which runs with an empty
configuration, and another machine both find every footprint (`H-K-VENDOR-GLOBAL`: one
`lib_footprint_issues` per footprint without vendoring, none with it, on 9.0.9 and 10.0.6).

- **Nicknames.** The copy keeps the row's nickname, so lib ids, the board and `.fenolite/` keep the
  design's names. In KiCad's library check the vendored project row hides a global row of the same
  nickname, and with it the global library's other items (`H-K-VENDOR-SHADOW`, measured for DRC on both
  majors). The GUI footprint chooser is expected to behave the same; this is not probed.
- **Only placed footprints:** no whole library, no 3D models (they stay at their `${KICAD…_3DMODEL_DIR}`
  paths), no symbols and no `sym-lib-table` before schematics (v0.2a).
- **Unsafe names.** A nickname holding `/`, `\` or a non-printable character, or two vendored paths
  that differ only in letter case, give `build.vendor-unsafe-name` and no file.
- **Library changes.** Every build copies the footprints again from their libraries. When a copy
  differs from the one the last build recorded, `build.library-changed` names it, so a library update
  shows in the `--dry-run` plan before `--confirm`. An untouched old copy is replaced; one edited by
  hand is protected like any output ("Edited outputs").
- **Stale copies** of removed parts stay in `lib/` ("Stale vendored files").
- **Licence.** The copies keep their library's licence. KiCad's official libraries are CC-BY-SA 4.0
  with an exception for designs that use them, and the exception does not cover redistributing the
  collection (S-0048). Fenolite gives no legal advice; copies are written only into `--out`.
- **Opt-out.** `fenolite build --vendor project` (or `build_design(..., vendor="project")`) copies only
  the footprints of project tables, as before c0027; the others give `build.global-library` and need
  the same global tables wherever the project is opened.

## Copper

A script can declare copper: tracks, single vias and stitching vias. It declares what to join, not where
the pads are. The build decides each placement after the script ran, and a footprint moved in KiCad keeps
its place, so the build resolves the copper after placement (`docs/copper.md`). The runnable example is
`examples/blink_routed/design.py`.

```python
design.track(
    "led_a", r1.pad(2), (mm(36), mm(9)), via_step(mm(36), mm(14), to="B.Cu"), d1.pad(2), width=mm(0.3)
)
design.via("gnd_tie", mm(20), mm(10), net=gnd, diameter=mm(0.6), drill=mm(0.3))
design.stitch("gnd_fence", net=gnd, pitch=mm(5), along=((mm(16), mm(26)), (mm(36), mm(26))))
```

| call | records |
|---|---|
| `part.pad(number, *, index=None)` | the pads of `part` with that number (a `str` or an `int`); `index` picks one when several share the number, else the build takes the nearest |
| `via_step(x, y, *, to, diameter=None, drill=None)` | a through via inside a track path, after which the track runs on the copper layer `to` |
| `design.track(key, *path, layer="F.Cu", width=None, net=None)` | a track along `path`: pad references, `(x, y)` points and via steps, starting on `layer` |
| `design.via(key, x, y, *, net, diameter=None, drill=None)` | one through via |
| `design.stitch(key, *, net, pitch, along=(), region=(), origin=None, diameter=None, drill=None, clearance=None, margin=None)` | through vias every `pitch` along a polyline, or on a grid inside a region |
| `copper(design)` | the intents as frozen dataclasses in key order (`TrackIntent`, `ViaIntent`, `StitchIntent`, with `PadEnd` and `ViaStep`), which the build resolves |

- **Points** are `(x, y)` pairs of lengths in the frame of `place()`: the origin is the board's corner.
- **Keys** name intents (`^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$`, one use each). Every id of the copper
  an intent creates derives from its key, so a rebuild keeps the ids, and the seed plays no part.
- **Nets.** A track takes the net of its pads; pads on two nets, or a pad on no net, is an error. `net=`
  is only needed for a track without a pad end, and must be a `Net`. Vias and stitches name their net.
- **Sizes.** A width, a via size or a stitch clearance that is not given comes from the class of the net;
  when the class sets none, the build reports `kicad.copper.size-missing`.
- **Errors at the call.** A malformed key, path, size or stitch raises `DslError` where it is written.
  What needs the board (an unknown pad, a pad without copper on the layer, two nets joined) is reported
  by the build, which then writes nothing.
- **The script owns its copper.** Each build regenerates it. Removing an intent removes its copper, and
  an edit of it in KiCad is replaced. Copper drawn in KiCad is the board's and is kept.
- `to_model` does not change: intents are not model objects.

## Zones

A script declares its copper pours with `Design.zone`, after `board()`:

```python
gnd = Net("GND")
design.zone(gnd, layers=("F.Cu", "B.Cu"), clearance=mm(0.3), connection="thermal")
design.zone(
    gnd, layers=("B.Cu",), name="GND_PAD", outline=((mm(5), mm(5)), (mm(15), mm(5)), (mm(15), mm(12)))
)
```

| argument | meaning | default |
|---|---|---|
| `net` | a `Net`, which joins the design, or `None` for a zone without a net | required |
| `layers` | the copper layers of the pour: `F.Cu`, `B.Cu`, and `In1.Cu`, `In2.Cu` with `copper=4` | required |
| `name` | names the zone across builds; unique in the design | the net's name; required when `net` is `None` |
| `outline` | at least three `(x, y)` points in the frame of `place()` | the board rectangle |
| `priority` | an `int` of at least 0; a higher priority is filled first | 0 |
| `clearance` | the distance the fill keeps from other nets (at least 0) | 0.5 mm |
| `min_thickness` | the smallest width of copper that a fill keeps (above 0) | 0.25 mm |
| `connection` | `solid`, `thermal`, `none` or `thru_hole_only` | `thermal` |
| `thermal_gap`, `thermal_spoke_width` | the gap and the spoke width of a thermal relief (above 0) | 0.5 mm, 0.5 mm |
| `islands` | `always` removes unconnected copper, `never` keeps it, `below_area` keeps islands of at least `min_island_area` | `always` |
| `min_island_area` | a string with the unit `mm2`, such as `"2.5mm2"`; only with `islands="below_area"` | 10 mm² |
| `locked` | the script wins over an edit of the zone in KiCad, and the zone is locked there | `False` |

- **Defaults are KiCad's.** A setting left out takes the value KiCad gives a new zone
  (`docs/design-model.md`, "Zone settings"). Hatched fills and corner smoothing are not DSL arguments;
  the model API sets them.
- **Lengths carry a unit**, as everywhere in the DSL: `clearance=0.3` is refused.
- **One zone, several layers.** A zone on two layers is one KiCad zone. A second zone on the same net
  needs its own `name=`.
- **Errors at the call.** A zone before `board()`, an unknown layer, a repeated name, a bad value or an
  area without `islands="below_area"` raises `DslError` naming the argument.
- **Clearance and rules.** KiCad keeps the larger of the zone's clearance and the clearance of the net
  class or of a custom rule, so a zone clearance below the class clearance has no effect.
- **Fills.** A build writes the zone without fills; KiCad fills it (press B in the board editor, or let a
  plot or DRC with refill do it). A rebuild keeps the fills while nothing they depend on changed
  (`docs/lens.md`, "Zones").
- **Rebuilds.** The zone edited in KiCad wins over the script unless the script says `locked=True`; a
  zone removed from the script is removed from the board (`docs/lens.md`, "Zones").
- **Pads.** A library footprint may set `(zone_connect N)` on a pad, for example a solid exposed pad in
  a thermal pour; the build keeps it. The DSL has no per-pad argument.
- **Altium.** `--target altium` writes the script's zones as unpoured polygon pours
  (`docs/altium.md`, "Copper"). With `--copper-from`, the zones of the routed board are written
  instead: that board already holds the script's zones.
- `to_model` puts one `Zone` per call into `Board.zones`, in name order, with the id
  `derived_id("zon", "dsl", "zone:<name>")`.

## Path aliases (`moved()`)

`design.moved(old, new)` records that the part at component path `new` was at `old` in an earlier
build, so a rebuild keeps its layout (`docs/lens.md`). `dsl.moves(design)` returns the aliases, new path
to old path. Both paths must be component paths (`R1`, `power/R1`); `old == new`, a malformed path and a
second alias with the same `old` or the same `new` raise `DslError` at the call. `moves` raises it when
`new` is not an added part or `old` still is one, so chains are refused; `fenolite build` reports this
as `FEN-3004`. Aliases are not model data: `to_model` and every id ignore them. One build is enough:
the footprint is re-placed under its new path, and the alias can then be removed.

## Determinism

A build is a pure function of the script and the Fenolite version: ids come from keys, files hold no
date, and sets are never iterated in hash order, so builds with different `--seed`, `--timestamp` and
`PYTHONHASHSEED` values (S-0072) are byte-identical. `--seed` and `--timestamp` are accepted and unused.

## Output layout

Under `--out DIR` (never the script folder):

- `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`;
- `fp-lib-table` with one row per vendored nickname, uri `${KIPRJMOD}/lib/<nickname>.pretty`, in the
  table form of the target (`docs/formats/kicad/libraries.md`, "Writing library tables");
- `lib/<nickname>.pretty/<entry>.kicad_mod`: every placed footprint, whatever the table that resolved
  it, copied byte for byte; with `--vendor project` only those of project tables ("Vendored libraries");
- `.fenolite/{meta,circuit,board,rules,manufacturing,findings}.json`: the model, as `dump_dir` writes it;
- `.fenolite/build.json`: `{"design", "files": {path: sha256}, "schema": "fenolite.build-record.v0",
  "target"}`, with every file outside `.fenolite/` that the build wrote, and no date.

The folder is self-contained and can be moved or copied whole.

## Edited outputs

A rebuild over an existing project keeps the work done in KiCad: the board, project and rules files are
merged, not replaced (`docs/lens.md`). The other outputs have no merge: before the plan is returned (so
`--dry-run` refuses too), `fp-lib-table` and each vendored footprint under `lib/` that already exists
must either have the planned bytes or the SHA-256 recorded in `.fenolite/build.json`. Anything else is
refused with `FEN-7001` (exit 7) and one `build.layout-exists` issue per file. `--discard-layout` builds
from scratch and replaces those files, keeping `.bak` copies unless `--no-backup`. Without a readable
record only identical bytes pass.

## Stale vendored files

A build writes files; it never deletes them. A footprint vendored by an earlier build stays in `lib/`
after its part is removed from the script, and is no longer listed in `build.json`. Delete the folder,
or `lib/`, to start clean.

## Building for Altium

`fenolite build design.py --out DIR --target altium` builds the same script into an experimental Altium
Designer project instead: a project file and an ASCII schematic with one generic body per part, net
labels and power ports on wire stubs, and a grid layout. Altium's engineering change order then creates
the PCB. This build reads no library, so lib ids and footprints name Altium library files
(`"MyParts.SchLib:LDO"`, `"MyParts.PcbLib:SOT23"`), and designators must be pin numbers. The board,
placements, net classes and diff pairs stay in `.fenolite/` only. See `docs/altium.md`.
