# The design DSL and `fenolite build`

`fenolite.dsl` describes a board in plain Python: parts, nets, net classes, interfaces, an outline and
placements. `fenolite build design.py --out DIR` runs the script and writes a KiCad 9.0 or 10.0
project from it, or, with `--target altium`, an experimental Altium project (see "Building for
Altium"). The DSL uses the standard library and Fenolite's own `core` and `model` only.

## Authored footprints (c0055)

The DSL exposes `Footprint` for declaring a project-local definition and `Design.add_footprint()` for
registering it. Assign it using the existing exact ID field on `Part`:

```python
from fenolite.dsl import Design, Footprint, Part, mm

d = Design("example")
fp = Footprint("Local", "TwoPad", kind="smd")
fp.pad("1", at=(mm(-1), mm(0)), size=(mm(1), mm(1)))
fp.pad("2", at=(mm(1), mm(0)), size=(mm(1), mm(1)))
fp.pad("2", at=(mm(1), mm(1)), size=(mm(2), mm(2)), shared=True)  # second land on pad 2
fp.rect((mm(-2), mm(-1)), (mm(2), mm(1)), layer="F.SilkS", width=mm(0.12))
d.add_footprint(fp)
part = Part("R1", "Device:R", footprint=fp.lib_id)
d.add(part)
```

The builder validates identifiers, dimensions, pad numbers, drill rules, and supported primitives. By
default, pad numbers are unique; use `shared=True` only for an additional physical land belonging to
the same electrical pad number. Its definition is separate from the canonical design model. Both
supported build paths resolve the exact
registered ID first: the KiCad target writes the `.kicad_mod` into its project `.pretty` library and
places it on the board; the experimental Altium target lowers the supported subset into `.PcbLib` and
uses it in `.PcbDoc` when the design has an outline.

**Generated fields (c0077).** A KiCad footprint carries a `Reference` and a `Value` property, and
`Footprint` declares neither. The KiCad build generates both, for an authored footprint and for a
footprint of the built-in catalog, in the `.kicad_mod` of the project library and on the board:

| field | library text | board text | layer | anchor |
|---|---|---|---|---|
| `Reference` | `REF**` | the part's reference | `F.SilkS` | 1 mm above the footprint's extent box, on the centre of its X range |
| `Value` | the footprint's name | the part's value | `F.Fab` | 1 mm below the box, on the same X |

The extent box is the box of the `F.CrtYd` graphics, else of the pads. Both fields are visible, centred
and horizontal, with glyphs of 1 mm by 1 mm and a stroke of 0.15 mm; on a bottom part they are on
`B.SilkS` and `B.Fab`, mirrored. `Part.field` moves or hides either one ("Field placement"). The placement
is a Fenolite choice; that KiCad accepts such a project is `H-K-FP-FIELDS`. The Altium build names its
components from the part and reads none of this.

Python facts are cited from `docs/evidence/sources.md` (S-0070 … S-0074); KiCad facts from
`docs/formats/kicad/`. Everything else on this page is a Fenolite choice.

## Authored symbols (c0058)

`Symbol` declares a project-local one-unit symbol without reading any files. Add pins with exact DSL
lengths, then attach the definition to the design. A KiCad build resolves matching `Part.lib_id`s from
these definitions and plans a `.kicad_sym` library and `sym-lib-table` row:

```python
from fenolite.dsl import Design, Part, Symbol, mm

d = Design("example")
header = Symbol("Local", "Header2", reference="J", footprint="Local:Header2")
header.pin("1", "VIN", etype="power_in", at=(mm(-2.54), mm(0)), length=mm(2.54), rotation=180)
header.pin("2", "GND", etype="power_in", at=(mm(2.54), mm(0)), length=mm(2.54))
header.rect((mm(-1), mm(-1)), (mm(1), mm(1)))
d.add(header, Part("J1", header.lib_id))
```

Symbol IDs are `library:name`, and their `Footprint` property supplies the component footprint when
`Part.footprint` is omitted. The target remains board-only; this library artifact makes the authored
symbols available to KiCad project consumers. KiCad file facts follow S-0043 in
`docs/formats/kicad/libraries.md`.

`Symbol.line`, `Symbol.rect`, `Symbol.circle` and `Symbol.polygon` add ordered symbol-local graphics
in integer nanometres. When present, these draw the symbol body; the generated pin-bounds rectangle
is retained only for older definitions without explicit graphics.

## Security: `build` executes the script

`fenolite build` runs `design.py` as the user's own code, in the same process. There is no sandbox:
the script can do anything the user can do. **Never run `build` on a script you do not trust.**
`fenolite build --help` says the same.

## API

```python
from fenolite.dsl import Design, Net, Part, Power, connect, mm

design = Design("blink")  # the name becomes the KiCad file stem
design.board(mm(50), mm(30))  # outline width and height; copper=2 (default), 4, 6 or 8

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
- `Design.sheet(paper, …, drawing_sheet=…)` and `Design.title_block(…)`: the paper, your drawing sheet and the title block ("Drawing sheet and title block").
- `Design.moved(old, new)`: a path alias that keeps the layout of a renamed part or module ("Path
  aliases"); `Design.moved_net(old, new)`: the same for a renamed net.
- `Design.board(width, height, copper=2, planes=None)`, once per design. `copper` is 2, 4, 6 or 8
  (`fenolite.dsl.design.COPPER_COUNTS`); any other value, a `bool` or a `float` included, is a
  `DslError` that names the counts. `design.board(mm(50), mm(30), copper=6)` declares the layers `F.Cu`,
  `In1.Cu`, `In2.Cu`, `In3.Cu`, `In4.Cu` and `B.Cu`. `Design.copper_layers` gives those names for the
  declared count, top to bottom (`("F.Cu", "B.Cu")` before `board()`), and
  `fenolite.dsl.design.inner_layers(copper)` the inner ones. Both KiCad targets get the layer table that
  KiCad itself writes for the count (`docs/formats/kicad/board.md`, "Created boards").
  `planes={"In1.Cu": gnd}` declares an inner layer as an internal plane on a net (a `Net` or a net
  name); it takes any inner layer of the count, so `planes={"In4.Cu": gnd}` is valid with `copper=6` and
  `In5.Cu` is not. A plane holds one net. It is a build parameter, as `copper` is: the model does not
  change. The Altium target writes the plane (`docs/altium.md`, "Copper"). The KiCad target gives each
  plane layer the row type `power` in the board it writes, also on a rebuild, after the layout merge
  (change c0107); it never removes a type, so a layer typed in KiCad's board setup stays a plane layer
  when the script names no plane on it. The copper of a plane is a zone: a plane whose net has no zone on
  its layer gives `build.plane-zone-missing` (warning), whose hint names the script call that draws that
  copper, `design.zone(<net>, layers=("<layer>",))`. `fenolite route` keeps tracks off a plane layer and
  joins the SMD pads of its net to the plane (`docs/routing.md`). `planes(design)` returns the mapping
  from layer name to net name.
- `Design.zone(net, *, layers, …)`: one copper zone (pour) per call ("Zones").
- `protect(…)`, `protection=` on `Design.via`, `via_step` and `Design.stitch`, and
  `Design.via_protection(protection, *, locked=False)`: how vias are tented, covered, plugged, capped
  and filled ("Via protection").
- `Design.rules.rule(name, kind, *, where, between, layers, min, opt, max, severity, priority)` and
  `fenolite.dsl.select`: one design rule with selectors ("Rules with selectors").
- `design.rules.netclass(name, *, clearance, track_width, via_diameter, via_drill, diff_pair_width,
  diff_pair_gap, diff_pair_via_gap, nets)`: every value is optional; a net belongs to at most one class.
- `design.rules.pair(pair, *, gap_min, gap_max, clearance, uncoupled_max, skew_max, length_min,
  length_max, severity, priority)` and `select.pair(pair)`: the rules of one differential pair
  ("Differential pairs").
- `design.rules.minimum(*, clearance, track_width, via_diameter, via_drill, hole_size, edge_clearance,
  netclass=None)`: design-rule minimums for the board, or for one net class ("Design rules").
- `Interface`, `Power(hv, lv)` and `DiffPair(p, n)`: named groups of nets kept in the model. A
  `DiffPair` reaches KiCad through its two net names and the rules that select it; one that no rule
  selects gives `build.interface-not-lowered` (info).
- `Harness(name, members)`: a named group of nets with different names, such as
  `Harness("SPI", {"MOSI": mosi, "MISO": miso, "SCK": sck})`. `name` is the harness type name and has no
  default; `members` maps an entry name to its net and may not be empty. The order of the entries carries
  no meaning. It is recorded as an interface of kind `harness`. A KiCad build keeps it in `.fenolite/`,
  gives no issue for it and writes the same files with or without it; the Altium build draws it as a
  signal harness with `--altium-sheets modules` (`docs/altium.md`, "Sheets and harnesses").
- `I2C(sda, scl)`, `SPI(sck, mosi, miso, cs=(...))`, `UART(tx, rx)` and `USB2(dp, dn, vbus=None, gnd=None)`:
  buses with fixed roles, each with `attach(part, ...)` ("Typed interfaces").
- `Quantity` and `ohm()`, `farad()`, `henry()`, `volt()`, `amp()`, `hertz()`, `watt()`, `second()`: exact
  electrical values ("Quantities").
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
  two classes, a second `place()` or `board()`, a `copper` that is not 2, 4, 6 or 8, a plane or a zone
  on a layer that the count does not have, one designator on two nets,
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

## Quantities

- `ohm("4k7")`, `farad("100n")`, `henry("4u7")`, `volt("3.3")`, `amp("500m")`, `hertz("16M")`,
  `watt("250m")` and `second("10u")` return a `Quantity`: a unit and an exact `fractions.Fraction` of it.
  Fenolite ships no value: every one comes from the script.
- **Input.** An `int`, a `Fraction`, or a text: a decimal number, an optional prefix (`p`, `n`, `u` or `µ`,
  `m`, `k`, `M`, `G`) and optionally the unit's symbol (`Ω`, `ohm` or `R`; `F`; `H`; `V`; `A`; `Hz`; `W`;
  `s`), with blanks allowed after the number; or the letter code of IEC 60062, where the prefix letter, or
  `R` for ohms, stands for the decimal point (`4k7`, `2R2`, `1n5`). A `float`, a `bool`, another unit's
  symbol or a text that does not parse raises `DslError` naming the input. Only volts and amperes may be
  negative.
- **Comparison.** `ohm("4k7") == ohm("4.7k") == ohm("4.7 kΩ") == ohm(4700)`, with one hash. Ordering needs
  one unit (`TypeError` otherwise). `+` and `-` take two quantities of one unit; `*` and `/` take an `int`
  or a `Fraction`.
- **Text.** `text()` scales the value by the largest prefix from `p` to `G` that keeps it at least 1 and
  prints the shortest exact decimal, the prefix (`u` for micro) and the symbol: `4.7kΩ`, `100nF`, `3.3V`,
  `16MHz`. A value that is not a terminating decimal (`ohm(1) / 3`) raises `DslError` when printed.
  `text(code=True)` prints the letter code for ohms, farads and henries (`4k7`, `100n`, `2R2`); farads and
  henries of 1 or more without a prefix have none and raise.
- **Parts.** `Part(..., value=ohm("4k7"))` stores `4.7kΩ`, so two spellings of one value are one value in
  the model and in the outputs. Pass `value=q.text(code=True)` for ASCII, or a plain string as before. A
  quantity never reaches the model or `.fenolite/`.

## Typed interfaces

```python
from fenolite.dsl import I2C, SPI, UART, USB2

bus = I2C(sda, scl)
design.add(bus)
bus.attach(u1, sda=u1["PB7"], scl=u1["PB6"])
bus.attach(u2, sda="SDA", scl="SCL")  # a designator is read as u2["SDA"]

uart = UART(a_tx, a_rx)  # the nets are named from device A
uart.attach(u1, side="a", tx=u1["TX"], rx=u1["RX"])
uart.attach(u3, side="b", tx=u3["TX"], rx=u3["RX"])  # crossed: U3 TX joins a_rx

spi = SPI(sck, mosi, miso, cs=(cs_flash, cs_adc))
spi.attach(u1, role="controller", sck="SCK", mosi="MOSI", miso="MISO", cs=("CS0", "CS1"))
spi.attach(u4, role="peripheral", sck="SCK", mosi="SDI", miso="SDO", cs="CS", cs_index=1)
```

- **Kinds and roles.** `I2C` is the kind `i2c` with `sda` and `scl`; `SPI` is `spi` with `sck`, `mosi`,
  `miso` and `cs0` … for the nets of `cs` in order; `UART` is `uart` with `tx` and `rx`; `USB2` is `usb2`
  with `dp` and `dn`, and `vbus` and `gnd` when given. The default name is the first two net names joined
  by `/`. The nets of one interface are distinct; a net may be in several interfaces.
- **`attach(part, ...)`** connects pins of one part by role through `connect`, so its rules hold. Every pin
  is a pin handle of that part or a designator of it; a handle of another part raises `DslError`, and
  nothing is connected when one argument is refused.
  - `UART.attach(part, side=, tx=, rx=)`: side `a` is straight, side `b` is crossed.
  - `SPI.attach(part, role=, sck=, mosi=, miso=, cs=, cs_index=)`: a `controller` gives one `cs` pin per
    chip-select net, in order; a `peripheral` gives one `cs` pin and the index of its net. MOSI joins MOSI.
  - `USB2.attach(part, dp=, dn=, vbus=None, gnd=None)`: a role the interface has no net for raises.
- **KiCad build.** The interfaces are kept in `.fenolite/circuit.json`; the other files do not depend on
  them. KiCad files hold no pair object: a `diff_pair` or `usb2` interface reaches KiCad through its two
  net names and through the rules that select it ("Differential pairs" below). A pair that no rule of the
  design selects gives `build.interface-not-lowered` (info): KiCad then knows it by its names only.
- **Checks in a build** (warnings):
  - `build.diff-pair-name`: the two nets of a `DiffPair` or of a `USB2` (`dp`, `dn`) are not a differential
    pair for KiCad. KiCad pairs two names that are equal except for one character, `P` then `N` or `+`
    then `-`, which only digits and underscores may follow, the same in both names; letter case counts.
    `USB_P`/`USB_N`, `USB+`/`USB-`, `USB_DP`/`USB_DN` and `D_P0`/`D_N0` are pairs; `USB_DP`/`USB_DM` and
    `D_P0`/`D_N1` are not (measured, `docs/formats/kicad/rules.md`). The hint proposes a name.
  - `build.diff-pair-gap-shadowed`: the nets of a pair are in a class with a `diff_pair_gap`, and KiCad
    would report two tracks laid at that gap ("Differential pairs" below).
  - `build.i2c-pullup-missing`: an I2C line has no part of exactly two pins between it and the `hv` net of
    a `Power` interface. A pull-up on another board, or in a resistor array, is not seen: ignore the
    warning then.
- **Altium build.** The four kinds are kept in the model and named in the `altium.not-lowered` info for
  interfaces; their nets are written as plain nets.

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
| rule | `rul` | `rule:<kind>` (board minimum), `rule:<kind>:<class name>` (class minimum), `rule:named:<rule name>` (a rule of `rule()`) |
| rule area | `kpo` | `area:<area name>` |
| board text | `txt` | `text:<drawing key>` |
| board graphic | `gfx` | `graphic:<drawing key>` |
| dimension | `dim` | `dimension:<drawing key>` |
| stack-up | `stk` | `stackup` |
| stack-up entry | `sly` | `stack_layer:<k>`, k from 0, top to bottom |

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
  (error, exit 5, nothing written). The resolved marks are kept in `.fenolite/circuit.json`. Each
  mark becomes a no-connect flag of the generated schematic (`docs/schematic.md`), so KiCad's ERC
  does not report the pin; the board, project and rules files are byte for byte those of the same
  design without marks.
- **Check.** `fenolite check` runs KiCad's own ERC on the generated schematic (stage `erc.kicad`). A
  marked pin is not reported; an unmarked pin on no net is `kicad.erc.pin-not-connected` (error), located
  as `REF-PIN`.
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
Without a request a field stays where the footprint library puts it. A footprint of the built-in catalog
or of `dsl.Footprint` has no library file: its two fields are generated 1 mm above and below the
footprint ("Authored footprints"), and a request moves or hides them like any other. A library footprint
that lacks one of the two gets it at the same place, with the info `build.field-added`.

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
- **Only placed footprints:** no whole library and no 3D models (they stay at their
  `${KICAD…_3DMODEL_DIR}` paths).
- **Symbols** follow the same rule: the symbols the schematic uses are written to
  `lib/<nickname>.kicad_sym` with a `sym-lib-table` row each, flattened and never a whole library
  (`docs/schematic.md`, "The symbols and their libraries"). The licence note below applies to those
  copies too: a symbol copied from a library keeps that library's licence.
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

A script can declare copper: tracks with straight segments and arcs, single vias and stitching vias. It declares what to join, not where
the pads are. The build decides each placement after the script ran, and a footprint moved in KiCad keeps
its place, so the build resolves the copper after placement (`docs/copper.md`). The runnable example is
`examples/blink_routed/design.py`.

```python
design.track(
    "led_a", r1.pad(2), (mm(36), mm(9)), via_step(mm(36), mm(14), to="B.Cu"), d1.pad(2), width=mm(0.3)
)
design.via("gnd_tie", mm(20), mm(10), net=gnd, diameter=mm(0.6), drill=mm(0.3))
design.stitch("gnd_fence", net=gnd, pitch=mm(5), along=((mm(16), mm(26)), (mm(36), mm(26))))
# a bend: from (8, 8) through a quarter circle to (9, 7), then straight on
design.track(
    "bend",
    (mm(8), mm(12)),
    (mm(8), mm(8)),
    arc_to((mm("8.292893"), mm("7.292893")), (mm(9), mm(7))),
    (mm(20), mm(7)),
    net=gnd,
    width=mm(0.3),
)
# on a board with copper=4: a blind via from the top layer to the first inner layer
design.track(
    "inner",
    (mm(24), mm(3)),
    via_step(mm(28), mm(3), to="In1.Cu", kind="blind", diameter=mm(0.6), drill=mm(0.3)),
    (mm(32), mm(3)),
    net=gnd,
    width=mm(0.3),
)
design.via(
    "core",
    mm(20),
    mm(20),
    net=gnd,
    kind="buried",
    layers=("In1.Cu", "In2.Cu"),
    diameter=mm(0.6),
    drill=mm(0.3),
)
# copper that belongs to a part: a fan-out via 1 mm below pad 9 of U1, and a thermal array in pad 33
design.via("fan9", u1.pad(9).at(mm(0), mm(1)), net=vin, diameter=mm(0.6), drill=mm(0.3))
design.track("fan9_stub", u1.pad(9), u1.pad(9).at(mm(0), mm(1)), width=mm(0.3))
design.stitch("ep", net=gnd, pitch=mm(1), region=u1.pad(33), diameter=mm(0.6), drill=mm(0.3), margin=mm(0.1))
```

| call | records |
|---|---|
| `part.pad(number, *, index=None)` | the pads of `part` with that number (a `str` or an `int`); `index` picks one when several share the number, else the build takes the nearest |
| `part.pad(number).at(dx=None, dy=None)` | an anchor: the point `(dx, dy)` from the position of those pads, in the frame of the part's footprint; a length left out is 0 |
| `part.at(dx=None, dy=None)` | an anchor measured from the origin of the part's footprint |

`Part(..., pad_map={"symbol pin": "physical pad"})` assigns physical footprint pad numbers per component. Pins omitted from `pad_map` keep identity mapping; net connections and no-connect declarations still use symbol pin designators. A pin that is bonded to several pads lists them in a tuple or a list (change c0123): `Part("U1", "Lib:LDO", footprint="Lib:SOT-223", pad_map={"2": ("2", "4")})` puts the net of pin 2 on the pad 2 and on the tab 4. The first pad is the one the schematic symbol shows; a pad belongs to one pin, and a pad listed for two pins, an empty tuple and a pad listed twice are refused when the part is created. `part.pad_map` reads back a string for one pad and a tuple for several. Both build targets apply the map: an Altium build puts each net on every mapped pad of the PCB document, checks script copper and a `--copper-from` board against the mapped pads, and writes the map into the footprint model of the schematic (and of its library, when every part of the symbol links the footprint the symbol names). The releases 0.1.0 and 0.2.0 ignored `pad_map` in an Altium build (fixed in 0.2.1, change c0135): build such a project again. Both targets refuse a map that names a missing pin or pad, or that leaves one pad to two pins (`pad_map={"1": "2"}` on a part that has a pin 2: map pin 2 as well); the Altium build reports it as `altium.pin-pad-map-invalid`, the KiCad build as `build.pin-pad-map-invalid`, each beside the model's `model.pin-pad-map`. `fenolite check` on an Altium project built with a map compares the schematic and the board through the map and reports nothing for the mapped pins (the release 0.2.1 compares the schematic by pin and the board by pad, and reports `netlist.assignment-differs`). A part of an anode-first catalog symbol (`Fenolite:LED`, `Fenolite:Diode`, `Fenolite:Zener_Diode`, `Fenolite:Schottky_Diode`, `Fenolite:Photodiode`: pin 1 `A`, pin 2 `K`) on a catalog land whose pad 1 is the cathode (`Fenolite:LED0603_Kingbright_APT1608SURCK`, `Fenolite:LED0805_Kingbright_APT2012SURCK`, `Fenolite:SOD128_Nexperia_CFP5`) that gives no `pad_map` gets the catalog's default map `{"1": "2", "2": "1"}` in both build targets, and the build reports it with the warning `build.pad-map-default` (change c0147); an explicit `pad_map` always wins, and a design that authors the symbol or the land under the same lib id gets no default. The releases 0.2.0 and 0.2.1 kept pin 1 on pad 1 there: a design that wired such a part by pin number has its two pad nets swapped on the next build, and keeps the old pads with `pad_map={"1": "1", "2": "2"}`. Authored through-hole pads accept `drill_shape="slot"` with `drill` as width, `drill_length` as overall slot length, and `drill_rotation` as its axis in the footprint frame. KiCad output supports horizontal and vertical oval drills; Altium output currently refuses slots.
| `via_step(x, y, *, to, diameter=None, drill=None, kind="through")`, `via_step(point, *, to, …)` | a via inside a track path, after which the track runs on the copper layer `to`; `kind` is `through`, `blind`, `buried` or `micro`. The point is two lengths, or one argument: an `(x, y)` pair or an anchor |
| `arc_to(mid, end)` | an arc inside a track path: from the point of the element before it through `mid` to `end`, each an `(x, y)` point or an anchor; the path continues from `end` |
| `design.track(key, *path, layer="F.Cu", width=None, net=None, locked=False)` | a track along `path`: pad references, `(x, y)` points, anchors, arc steps and via steps, starting on `layer` |
| `design.via(key, x, y, *, net, diameter=None, drill=None, kind="through", layers=None, locked=False)`, `design.via(key, point, *, net, …)` | one via, at two lengths or at one point (an `(x, y)` pair or an anchor); a via that is not a through via names its two copper layers in `layers` |
| `design.stitch(key, *, net, pitch, along=(), region=(), origin=None, diameter=None, drill=None, clearance=None, margin=None, locked=False)` | through vias every `pitch` along a polyline, or on a grid inside a region; `region=part.pad(number)` is the copper of that pad (a thermal array) |
| `copper(design)` | the intents as frozen dataclasses in key order (`TrackIntent`, `ViaIntent`, `StitchIntent`, with `PadEnd`, `Anchor`, `ViaStep` and `ArcStep`), which the build resolves |

- **Points** are `(x, y)` pairs of lengths in the frame of `place()`: the origin is the board's corner.
- **Anchors** are points in a part's frame, for copper that belongs to a part: `part.pad(n).at(dx, dy)`
  is measured from a pad, `part.at(dx, dy)` from the origin of the footprint. The offset is given as the
  footprint's library draws it (X to the right, Y down), so it keeps its place among the pads when the
  part is turned, and it is mirrored with the part on the bottom side. An anchor stands wherever a
  point does: a waypoint of a track, `mid` and `end` of `arc_to`, the point of `via_step` and of
  `design.via`, and the `along` points, the `region` points and the `origin` of a stitch. The build
  resolves it after placement, so anchored copper follows a part that was moved in KiCad or by
  `fenolite place` at the next build, with the same ids. Start from a pad anchor: it needs no library
  coordinates. In this section the word "anchor" always means such a point in a part's frame.
- **An anchor is a point, not a connection.** `part.pad(9)` in a path joins the pad and gives the
  track its net; `part.pad(9).at()` is only the place where the pad is. A track still takes its net
  from its pad ends, and a via or a stitch names its net. `part.pad(…)` where a point is expected is
  refused with a hint to `.at()`. A via of another net anchored inside a pad is a short: the copper
  guard of `build` refuses it (KiCad's own DRC does not report it, `docs/copper.md`).
- **Thermal arrays.** `design.stitch(key, net=…, pitch=…, region=part.pad(n))` lays its grid from the
  pad's position in the part's frame, keeps the vias whose disc plus `margin` lies inside the pad's
  copper on the part's side, and does not count that pad as an obstacle. The pad must be on the
  stitch's net. `origin` is left out, or is an anchor that moves the grid; a board-point `origin` is
  refused with a pad region. The vias are through vias.
- **Locks.** `locked=True` on `design.track`, `design.via` or `design.stitch` asks that the copper of
  the intent be written locked: `(locked yes)` on each of its segments, arcs and vias, which KiCad's
  editor then refuses to move. The value must be `True` or `False`; anything else is a `DslError` that
  names the intent. Script copper is unlocked by default, and `fenolite route --rip` never removes
  script copper, locked or not. This is the **copper lock**; `Part.place(..., locked=True)` is another
  thing, the placement lock of a part.
- **Keys** name intents (`^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$`, one use each). Every id of the copper
  an intent creates derives from its key, so a rebuild keeps the ids, and the seed plays no part.
- **Nets.** A track takes the net of its pads; pads on two nets, or a pad on no net, is an error. `net=`
  is only needed for a track without a pad end, and must be a `Net`. Vias and stitches name their net.
- **Sizes.** A width, a via size or a stitch clearance that is not given comes from the class of the net;
  when the class sets none, the build reports `kicad.copper.size-missing`.
- **Arcs.** `arc_to(mid, end)` is the three-point form that KiCad stores: the arc starts where the path
  is, passes through `mid` and ends at `end`. The three points must be distinct and must not lie on one
  line. There is no radius or fillet argument: the tangent points of a fillet are not whole
  nanometres, so compute them, round them and pass the three points. An arc ends at a point; to end
  it on a pad, give the pad's position (`fenolite pads`, below) and put the pad end after it.
- **Via kinds.** `through` (the default) spans the board. `blind` joins an outer layer and an inner
  one, `buried` two inner layers, `micro` an outer layer and the layer next to it. A via step takes
  its two layers from the path (the layer the track is on, and `to`); a single via names them in
  `layers`. Layers that do not fit the kind are `kicad.copper.bad-layer`. A `buried` via needs
  `--kicad-version 10`: the board writer refuses it for KiCad 9 (exit 7). A `micro` via takes its
  sizes from the call, else from `via_diameter` and `via_drill` of the net's class, as any via.
  Stitching vias stay through vias.
- **Where is a pad?** `fenolite pads build/blink D1 --origin 100mm,100mm --json` lists the pads of `D1`
  with their positions, layers and nets. `--origin 100mm,100mm` is `BOARD_ORIGIN`, so the positions
  are in the frame of `place()` and can be written into `design.track` as they are. `index` in the
  reply is the value `part.pad(number, index=…)` takes (`docs/cli-contract.md`, "pads").
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
| `layers` | the copper layers of the pour, any of `Design.copper_layers`: `F.Cu`, `B.Cu` and the inner layers `In1.Cu` … `In<copper − 2>.Cu` of the count (`In6.Cu` is the deepest with `copper=8`); a refused name lists the board's layers | required |
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
- **Pads.** `part.zone_connection(number, connection, *, index=None, locked=False)` says how zones
  connect to the pads of a part with that number, whatever the zone's own `connection` is:

  | `connection` | the pad in a pour of its net |
  |---|---|
  | `solid` | covered by the fill, without a relief: an exposed pad that must lose heat |
  | `thermal` | joined by the spokes of a thermal relief |
  | `none` | not joined by the fill at all |
  | `thru_hole_only` | a relief when the pad is a through-hole pad, solid otherwise |

  `u1.zone_connection(33, "solid")` names every pad numbered 33; `index=` names one of several that
  share the number, in the footprint's pad order (`fenolite pads` shows the index). One request per
  pad: a second request for the same pad, or one with an index beside one without, raises `DslError`.
  A number or index the footprint does not have is `kicad.pad.zone-unknown-pad`, and the build writes
  nothing. A pad that no request names keeps what its library footprint says, for example the
  `(zone_connect N)` of a solid exposed pad. On a rebuild, a setting made in KiCad wins unless the
  request says `locked=True`, as for zones (`docs/lens.md`, "Pad zone connections"). `--target altium`
  does not read these requests, as it does not read field requests.
- **Altium.** `--target altium` writes the script's zones as unpoured polygon pours
  (`docs/altium.md`, "Copper"). With `--copper-from`, the zones of the routed board are written
  instead: that board already holds the script's zones.
- `to_model` puts one `Zone` per call into `Board.zones`, in name order, with the id
  `derived_id("zon", "dsl", "zone:<name>")`.

## Stack-up

`design.stackup(*entries, finish=None, impedance_controlled=False, locked=False)` declares the build-up of
the board from its top face to its bottom face (change c0101). It is called after `board()`, and once.
The entries come from `fenolite.dsl.stack`:

```python
from fenolite.dsl import Design, mm, stack

design = Design("blink")
design.board(mm(50), mm(30), copper=4)
design.stackup(
    stack.mask("10um", color="Green"),
    stack.copper("35um"),
    stack.prepreg("0.2mm", material="FR4", epsilon_r="4.5", loss_tangent="0.02"),
    stack.copper("17.5um"),
    stack.core("1.2mm", material="FR4", epsilon_r="4.5"),
    stack.copper("17.5um"),
    stack.prepreg("0.2mm"),
    stack.copper("35um"),
    stack.mask("10um"),
    finish="ENIG",
)
```

| entry | arguments |
|---|---|
| `stack.silkscreen(*, color="")` | no thickness |
| `stack.mask(thickness, *, material="", epsilon_r=None, loss_tangent=None, color="")` | a thickness of at least 0 |
| `stack.copper(thickness)` | a thickness above 0 |
| `stack.core(thickness, *, material="", epsilon_r=None, loss_tangent=None, color="")` | a thickness above 0 |
| `stack.prepreg(…)` | the arguments of `core` |

- A thickness is a length with a unit (`"35um"`, `mm("0.2")`). `epsilon_r` and `loss_tangent` are an
  `int`, a `fractions.Fraction` or a decimal text, never a `float`; they are stored as the shortest plain
  decimal (`"4.50"` gives `"4.5"`). `epsilon_r` is above 0; `loss_tangent` may be 0.
- The order is: at most one silkscreen, then at most one mask; one `copper()` per copper layer of
  `board(copper=…)`, with at least one `core()` or `prepreg()` between neighbours; then at most one mask
  and at most one silkscreen. Several dielectrics in one gap are the sheets of one dielectric and are all
  of one kind. Any other sequence raises `DslError` naming the position (from 0) of the first entry out of
  place.
- The copper entries take the names of the board's copper layers from the top (`F.Cu`, `In1.Cu`, …,
  `B.Cu`), the dielectrics of the gap below the j-th copper layer the name `dielectric <j>`, masks and
  silkscreens `F.Mask`, `B.Mask`, `F.SilkS` and `B.SilkS`: the names KiCad gives the same rows, so a
  rebuild compares equal names.
- Fenolite supplies no thickness, material, dielectric constant or finish. A mask the script leaves out is
  written with the thickness 0 (KiCad would count 0.01 mm for a row without one), and the board thickness
  is the sum of the entries.
- `to_model` gives the board a `Stackup` (`docs/design-model.md`, "Stack-up"); a design without
  `stackup()` has none and builds the files it built before. `stackup_locked(design)` returns `locked`.
- On a rebuild the board's stack-up wins over an unlocked script stack-up that differs
  (`kicad.stackup.overridden`), and `locked=True` makes the script's replace it (`kicad.stackup.forced`):
  `docs/lens.md`, "Stack-up across rebuilds".
- `stack.preset(name)` and `stack.PRESETS` are reserved for stack-ups taken from public fabricator pages;
  no preset ships yet, so every name raises `DslError`.

## Via protection

A via may be tented (covered by solder mask), covered, plugged, capped and filled. `protect()` says how,
per via or for the whole board (change c0112):

```python
from fenolite.dsl import protect

design.via_protection(protect(tenting=True))  # the board default: every via tented on both sides
design.via("tp1", mm(5), mm(5), net=gnd, protection=protect(tenting=False))  # a test point, open
design.stitch("pad", net=gnd, pitch=mm(1), region=ring, protection=protect(filling=True, capping=True))
design.track(
    "a", r1.pad(2), via_step(mm(8), mm(8), to="B.Cu", protection=protect(tenting="front")), d1.pad(2)
)
```

- `protect(*, tenting=None, covering=None, plugging=None, capping=None, filling=None)` returns a
  `ViaProtection` of the model (`docs/design-model.md`, "Via protection"). `tenting`, `covering` and
  `plugging` have two sides and take `True` (both sides), `False` (neither), `"front"` or `"back"` (that
  side, the other not) or `None`; `capping` and `filling` take `True`, `False` or `None`. Any other value
  raises `DslError`. `None` means "not stated here": on a via the feature follows the board default, and in
  the board default it is KiCad's own (tented on both sides, nothing else). A value for one side with
  `None` for the other is built with `ViaProtection(...)` of `fenolite.model.board`.
- `protection=` on `Design.via`, `via_step` and `Design.stitch` takes that value (or `None`); every via of
  a stitch carries it. Anything else raises `DslError` naming the copper key.
- `Design.via_protection(protection, *, locked=False)`, at most once, declares the board default. A script
  without it, and without any `protection=`, builds every file with the bytes it had before.
- **Rebuilds.** Script vias take the protection of their intent at every build: a protection set in KiCad
  on a script via is replaced, with `kicad.copper.regenerated` (info). The board default follows the rule
  of zones and of the stack-up: an edit in KiCad's Board Setup wins over an unlocked default
  (`kicad.via.protection-overridden`, info), and `locked=True` makes the script's replace it
  (`kicad.via.protection-forced`, warning): `docs/lens.md`, "Via protection across rebuilds".
- **What each target holds.** KiCad 10 holds all five features, per via and as defaults. KiCad 9 holds
  tenting only: `--kicad-version 9` refuses a covering, plugging, capping or filling of `True` with exit 7
  (`kicad.board.via-protection-too-new`; `--allow-lossy` does not drop it), and writes nothing for `False`
  and `None`. A target-9 board opened in KiCad 10 is converted by KiCad, which then tents the side that a
  via's 9.0 child does not name; `fenolite build --kicad-version 10` keeps the mask that KiCad 9 plots.
  The Altium target writes the tenting where the design states it and names the rest (`docs/altium.md`,
  "Via protection").
- **What reaches the fabrication files.** The solder mask plots follow tenting alone. Covering, plugging,
  capping and filling reach only the drill side files and the IPC-2581 export of `kicad-cli` 10.0.6, and
  only for the vias that carry the value themselves: a board default adds none. A build whose default
  gives such a feature to vias that do not carry it says so with `kicad.via.protection-not-exported`
  (info); set it with `protection=` on those vias, or state it in the fabrication notes. Fenolite supplies
  no protection the script does not give, and checks none.

## Design rules

A net class says what the copper of its nets should be; a minimum says what the design-rule check must
refuse. `design.rules.minimum(...)` declares minimums, and the build writes them where KiCad's DRC reads
them:

```python
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))

# Board minimums: what the fab can make.
design.rules.minimum(
    clearance=mm(0.15), track_width=mm(0.15), via_diameter=mm(0.45), via_drill=mm(0.2),
    hole_size=mm(0.3), edge_clearance=mm(0.3),
)  # fmt: skip
# Class minimums: the nets of PWR never go below these.
design.rules.minimum(clearance=mm(0.2), track_width=mm(0.4), netclass="PWR")
```

- **Keywords.** One per rule kind of the model: `clearance`, `track_width`, `via_diameter`, `via_drill`,
  `hole_size` (any drilled hole) and `edge_clearance` (copper to the board edge). Each is optional; a call
  gives at least one.
- **Lengths carry a unit**, as everywhere in the DSL, and are above 0: `clearance=0.2` is refused.
- **Scope.** Without `netclass` the minimums hold for the whole board. With `netclass="PWR"` they hold
  for the nets of that class, which must be declared first with `design.rules.netclass`.
- **Several calls.** `minimum()` may be called more than once, but a kind is declared once per scope.
  The order of the calls does not matter.
- **Errors at the call.** No length, a bare number, a value of 0 or less, an undeclared class or a kind
  given twice for one scope raises `DslError`, and the call records nothing.
- **Model.** `to_model` writes one `Rule` per minimum into `rules.json`: `min_<kind>` on every object
  with priority 0, or `min_<kind>_<class>` on the class with priority 1. The id is
  `derived_id("rul", "dsl", "rule:<kind>")` or `derived_id("rul", "dsl", "rule:<kind>:<class>")`.
- **KiCad.** The build writes each minimum as a custom rule of `<name>.kicad_dru`
  (`fenolite_0_min_<kind>`, then `fenolite_1_min_<kind>_<class>` with the condition
  `A.NetClass == '<class>'`), and the board minimums also as the board-setup minimums of
  `<name>.kicad_pro` (`docs/formats/kicad/rules.md`, `docs/formats/kicad/project.md`). `kicad-cli pcb drc`
  and the board editor enforce both; `kicad-cli` 9.0.9 and 10.0.6 report a build that breaks a minimum
  and accept one that respects it (`H-K-DSL-MINIMUM`).
- **Class over board.** KiCad applies the last matching rule, and class minimums are written last. So a
  class minimum governs the copper of its class, whether it is above or below the board minimum. The
  board-setup minimum of a kind is the least of both, so it never hides a lower class minimum.
- **Board clearance against class clearance.** A board `clearance` minimum is a custom rule on every
  object, and KiCad applies a custom rule over the clearance of a net class. A class whose clearance is
  above the board minimum is then checked against the board minimum only, and the build warns
  (`kicad.project.class-shadowed`). Restate the class value as a class minimum, as the example above
  does for `PWR`. Fenolite changes no value on its own.
- **Rebuilds.** Fenolite's rules are replaced on every build; rules added to the `.kicad_dru` by hand,
  under names that do not start with `fenolite_`, are kept after them (`docs/lens.md`, "Project and rules
  files").
- **Beyond minimums.** `minimum()` covers six kinds on the board or on a class. Everything else is a
  `rule()` (below): the other kinds, severities, `opt` and `max`, layers and selectors. The rules of a
  differential pair are a `pair()` ("Differential pairs"). Custom expressions are not modelled.
- **Altium.** `--target altium` writes a minimum into the PCB document when Altium's rule holds that
  one limit: `clearance` and `edge_clearance`. A `track_width`, `via_diameter`, `via_drill` or `hole_size`
  minimum is reported with one `altium.not-lowered` warning (`where` = `design-rules/<kind>`), because
  Altium's record also holds a maximum (and a preferred value): declare it with `rule()` and all its
  limits (`docs/altium.md`, "Rules"). Every rule stays in `.fenolite/rules.json`.

### Rules with selectors

`design.rules.rule(name, kind, ...)` declares one rule of any kind of the model, for the items a selector
names:

```python
from fenolite.dsl import select

design.rules.rule("pitch", "hole_to_hole", min=mm(0.3))  # the whole board
design.rules.rule("ring", "annular_width", where=select.item("via"), min=mm(0.12))
design.rules.rule("court", "courtyard_clearance", where=select.ref(u1), min=mm(0.5))
design.rules.rule(
    "mains", "creepage", where=select.netclass("HV"), between=select.netclass("LV"), min=mm(6.4)
)  # your value, not Fenolite's
```

- **Kinds.** The six of `minimum()`; `hole_to_hole`, `hole_clearance`, `annular_width`,
  `courtyard_clearance`, `silk_clearance` and `creepage`; and the pair and length kinds `diff_pair_gap`,
  `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length` ("Differential pairs"). Fenolite ships no
  value for any of them.
- **Selectors** come from `fenolite.dsl.select`: `net(name or Net)`, `netclass(name)`, `ref(reference or
  Part)`, `item("track" | "via" | "pad" | "zone")`, `area(name or RuleArea)`, `pair(pair interface, or a
  base name, or "*")` and `ALL` (the default). `&`, `|` and `~` combine them;
  `ALL` stands alone. A name may hold `*`. A class named in a selector must be declared first, except
  `Default`.
- **`between`** names the second item of a `clearance` or `creepage` rule. No other kind takes it.
- **`no_tracks`** keeps a selection off some copper layers (change c0107):
  `design.rules.rule("sig-outer", "no_tracks", where=select.netclass("SIG"), layers=("In1.Cu", "In2.Cu"))`.
  It takes no limit (`min`, `opt` and `max` are refused) and needs `layers`; `where` is `ALL`, or nets and
  classes. KiCad checks it (`disallow track`, target 10 until the probe of 9.0 is recorded), `route` routes
  the selected nets on the other layers, and an Altium build reports it as not lowered. It is the rule
  kind, and not the `no_tracks` flag of a keep-out, which forbids tracks inside an outline whatever their
  net.
- **`select.area(area)`** selects the items whose copper reaches into a rule area ("Rule areas"), on one
  of the area's layers: an item that only crosses the area's edge is selected too. It is written as
  `A.intersectsArea('<name>')`. The name is compared with letter case and may hold `*`. The call does not
  check that the area exists, because an area may be drawn and named in KiCad: the build checks, after
  it merged the existing board, that the board it is about to write holds a rule area of that name, and
  stops with `build.area-unknown` (exit 5) otherwise, since KiCad would load the rule and apply it to
  nothing. Every kind takes an area but `courtyard_clearance`, `silk_clearance`, `creepage`,
  `no_tracks` and the five pair and length kinds ("Differential pairs"). The
  selector is written for the KiCad majors on which its probe is recorded (`docs/formats/kicad/rules.md`).

  ```python
  bga = design.rule_area("BGA", [(mm(10), mm(10)), (mm(20), mm(10)), (mm(20), mm(20)), (mm(10), mm(20))])
  design.rules.rule("neck", "track_width", where=select.area(bga), min=mm(0.1), priority=1)
  design.rules.rule("hv", "clearance", where=select.area("HV"), min=mm(2))  # an area drawn in KiCad
  ```
- **Limits** carry a unit. `min` may be 0 (a courtyard rule of 0 forbids overlap); `opt` and `max` are above
  0; the limits rise from `min` to `max`. Which limits a kind takes is in `docs/formats/kicad/rules.md`: the
  six new kinds take `min` only.
- **`severity`** is `error` (default), `warning` or `ignore`. **`priority`**: 0 is written first and governs
  least; among the others, 1 governs most, because KiCad applies the last matching rule.
- **`layers`** is a tuple of KiCad layer names, for the kinds that take a layer clause.
- **What each kind takes.** `courtyard_clearance` takes references only and selects whole footprints;
  `silk_clearance` is board-wide; `creepage` takes nets and classes on both sides; the three hole and ring
  kinds take any selector on one side and no layers.
- **Errors at the call** (`DslError`, nothing recorded): an unknown kind, no limit, a bare number, a
  negative `min`, falling limits, `between` on another kind, a repeated name, an undeclared class, an unknown
  severity.
- **Errors at the build.** What depends on the KiCad major is judged when the rules are written, and stops
  the build with exit 7: a selector or limit the kind does not take, and a kind the target does not check.
  `creepage` is written for KiCad 10 only, because `kicad-cli` 9.0.9 loads such a rule and reports nothing
  for it; `--allow-lossy` leaves the rule out with `rules.dropped-for-target`.
- **Model.** One `Rule` per call, after the minimums, with the id `derived_id("rul", "dsl",
  "rule:named:<name>")`. The build writes it as `fenolite_<priority>_<slug of the name>`.
- **Altium.** Written into the PCB document by kind and scope, exactly or not at all; a rule that is
  not written gives one `altium.not-lowered` warning with its reason (`docs/altium.md`, "Rules").

### Differential pairs

A pair is a `DiffPair` or a `USB2`. Its width, gap and via gap are values of the net class of its two
nets, and its limits are rules that `design.rules.pair()` declares in one call:

```python
from fenolite.dsl import USB2, select

usb_p, usb_n = Net("USB_P"), Net("USB_N")
usb = USB2(usb_p, usb_n, name="USB")
design.rules.netclass(
    "USB", clearance=mm(0.2), diff_pair_width=mm(0.2), diff_pair_gap=mm(0.15), nets=(usb_p, usb_n)
)
design.rules.pair(
    usb,
    gap_min=mm(0.13),
    gap_max=mm(0.2),
    clearance=mm(0.15),
    uncoupled_max=mm(5),
    skew_max=mm(0.5),
    length_max=mm(60),
)  # your values, not Fenolite's
```

- **Net names.** KiCad has no pair object: two nets are a pair by their names (the rule is under "Typed
  interfaces", `build.diff-pair-name`). `select.pair(usb)` and `pair(usb, …)` take the base from the two
  names (`USB_` here, `USB_D` for `USB_DP`/`USB_DN`) and raise `DslError` when the names do not pair.
- **Class values.** `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap` of `netclass()` are
  lengths, written into the class of `<name>.kicad_pro`. KiCad's pair router lays a pair with them; none
  is a limit that the DRC checks. One of them changes a check: a `diff_pair_gap` below the class
  `clearance` lowers the clearance between the two nets of each pair of the class, in KiCad and in
  `fenolite check` alike, where no clearance rule governs them.
- **`pair(pair, …)`** records one rule per group that is given, named `pair:<pair name>:<group>`, and adds
  the pair to the design:

  | given | rule kind | what KiCad checks |
  |---|---|---|
  | `gap_min`, `gap_max` | `diff_pair_gap` | the edge-to-edge gap of the coupled tracks |
  | `clearance` | `clearance`, with the pair on both sides | the clearance between the two nets of the pair |
  | `uncoupled_max` | `diff_pair_uncoupled` | the length the pair runs uncoupled |
  | `skew_max` | `diff_pair_skew` | the length difference between the two nets |
  | `length_min`, `length_max` | `length` | the routed length of each net |

  A call that gives no limit, or whose values `rule()` would refuse, raises `DslError` naming `pair()` and
  records nothing. `pair()` takes no target value: a target (`opt`) is written with `rule()`, and KiCad's
  DRC never checks it.
- **Order.** The rules have priority 1 by default, like the class minimums of `minimum(netclass=…)`.
  Rules of one priority are written in name order, and `pair:` sorts after `min_`, so a pair's rules come
  later in the file and govern its items over a class minimum. A rule of your own with priority 1 and a
  name after `pair:` governs instead.
- **`select.pair(x)`** is the selector for `rule()`: `x` is a pair interface, a base name, or `"*"` for
  every pair. It combines with `&`, `|` and `~` as the other selectors do, and the base keeps its letter
  case. `design.rules.rule("every skew", "diff_pair_skew", where=select.pair("*"), max=mm(0.5))` holds for
  every pair of the board; `skew` (without `diff_pair_`) matches a group of nets against its longest net.
- **What KiCad measures.** A length counts each via by the board stack-up. Parallel tracks of a pair count
  as coupled at any distance, so `gap_max` is what bounds how far a pair spreads.
- **`build.diff-pair-gap-shadowed`** (warning). A design often has a board-wide clearance rule
  (`minimum(clearance=…)`), and KiCad applies a custom clearance rule over the pair gap of a class. A pair
  whose class gap is below such a rule would be reported when laid at its gap. The build warns, and the
  hint names the fix: `pair(…, clearance=…, gap_min=…)` writes a clearance rule and a gap rule for the
  pair, after the rules that shadow it. Fenolite writes no such rule on its own.
- **Targets.** The pair kinds and the pair selector are written for the KiCad majors on which their
  probes are recorded (`docs/formats/kicad/rules.md`): KiCad 10 today. For another major the build stops
  with exit 7 (`rules.kind-unchecked`), and `--allow-lossy` leaves the rules out.
- **Altium.** `--target altium` keeps the pair rules, the class pair values and the pair interfaces in
  `.fenolite/` and names each in an `altium.not-lowered` message; it writes none of them
  (`docs/altium.md`, "Differential pairs").

## Rule areas

`design.rule_area(name, outline, *, layers=None, forbid=())` declares one rule area and returns its
`RuleArea` record. It is the one call for rule areas and keep-outs: a keep-out is a rule area that forbids
something.

```python
design.rule_area(
    "ANT",
    [(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(10)), (mm(40), mm(10))],
    forbid=("tracks", "vias", "pours"),
)
hv = design.rule_area("HV", [(mm(0), mm(0)), (mm(20), mm(0)), (mm(20), mm(30))], layers=("F.Cu",))
```

- **`name`** matches `^[A-Za-z0-9_.+-]+$` and is unique. Two names that differ only in letter case are
  refused: KiCad compares area names with letter case, so a rule written for one would miss the other.
- **`outline`** holds at least three `(x, y)` points in the frame of `place()`. An outline is a polygon: a
  round keep-out is a polygon around the circle.
- **`layers`** are copper layers of the board; `None` means every copper layer.
- **`forbid`** takes `tracks`, `vias`, `pads` and `pours`. With an empty `forbid` the area forbids nothing
  and only rules select it (`select.area`, "Rules with selectors"). Areas that forbid footprints are not
  declared here.
- **In the model** each area is a `Keepout` with its `name`, in name order, with the id
  `derived_id("kpo", "dsl", "area:<name>")`. `design.rule_areas` holds the records by name.
- **What a keep-out does.** KiCad's DRC reports a track (one that only crosses the edge too), a via or a
  pad in an area that forbids it as `items_not_allowed`, on the area's layers only, and its filler leaves
  an area that forbids pours out of every fill. Fenolite's copper check reports the same tracks, vias and
  pads as `copper.keepout`, so the copper guard stops the build before KiCad sees the board
  (`--copper-check warn` writes anyway). Stitch vias of `stitch()` stay out of areas that forbid vias.
- **Rebuilds.** A script area is derived output: every build writes it again from the script, with a
  marked uuid (`docs/lens.md`, "Board items declared in the script"). An edit made to it in KiCad is
  undone, with `kicad.board-item.regenerated`; an area drawn in KiCad is never touched.
- **Altium.** An area that forbids something is written as a keep-out with its restrictions; its name has
  no place in the record and is reported, and an area that forbids nothing is reported and not written
  (`docs/altium.md`, "Rule areas, texts and dimensions").

## Board drawings

Seven calls declare texts, graphics and dimensions of the board. Each takes a key first, which matches
the pattern of copper keys and is unique across the seven calls; the key names the drawing across builds.

```python
design.text("rev", "REV A", (mm(5), mm(28)), justify="left bottom")
design.line("fab/mid", (mm(0), mm(15)), (mm(50), mm(15)), layer="F.Fab", width=mm(0.1))
design.rect("mask/window", (mm(1), mm(1)), (mm(4), mm(3)), layer="F.Mask", width=mm(0), fill=True)
design.circle("mark", (mm(45), mm(25)), (mm(46), mm(25)), layer="F.SilkS", width=mm(0.12))
design.arc("bend", (mm(0), mm(0)), (mm(1), mm(1)), (mm(2), mm(0)), layer="Dwgs.User", width=mm(0.1))
design.polygon("flag", [(mm(10), mm(2)), (mm(12), mm(2)), (mm(11), mm(4))], layer="B.SilkS", width=mm(0.1))
design.dimension("width", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-5))
```

- **Layers.** A drawing goes on a silkscreen, solder-mask, fabrication or user layer: `F.SilkS`, `B.SilkS`,
  `F.Mask`, `B.Mask`, `F.Fab`, `B.Fab`, `Dwgs.User`, `Cmts.User`, `Eco1.User` and `Eco2.User`. Copper is
  refused: the copper check cannot see glyphs, KiCad reports a copper text across a track as a short, and
  it does not report a copper line across a track at all. `Edge.Cuts` belongs to the outline of `board()`.
- **`text(key, text, at, *, layer="F.SilkS", size=None, thickness=None, rot=0, justify=None)`**: one
  printable line, 1 mm high with a 0.15 mm stroke unless `size` and `thickness` say otherwise. `justify`
  is `left` or `right`, then `top` or `bottom`; without it the text is centred on `at`. A text on a back
  layer is mirrored. A centred label close to the board edge reaches it: KiCad then warns with
  `silk_edge_clearance`.
- **`line(key, start, end)`, `rect(key, start, end)`, `circle(key, center, edge)`, `arc(key, start, mid,
  end)` and `polygon(key, points)`** take `layer` and `width`; `rect`, `circle` and `polygon` take
  `fill=False`. `width` is above 0 for a line, an arc and a shape that is not filled, and may be `mm(0)` for
  a filled one. The three points of an arc are not on one line.
- **`dimension(key, start, end, *, offset, layer="Dwgs.User", direction=None, units="mm", precision=4,
  size=None, thickness=None, width=None)`**: a linear dimension. Without `direction` it is aligned with the
  two points; with `horizontal` or `vertical` it measures that coordinate difference only. `offset` is the
  signed distance of the dimension line from the measured points, KiCad's `height`: for a dimension from
  left to right a negative offset puts the line above the points (towards smaller y), and for one from top
  to bottom a negative offset puts it to their right. `units` is `mm` or `in`, `precision` 0 to 4
  decimals. KiCad computes the text, its place and its angle from the points when it loads the board.
- **In the model** a text is a `Text` (`txt`), a graphic a `Graphic` (`gfx`) and a dimension a `Dimension`
  (`dim`), each in key order; `design.drawings` holds the records by key.
- **Errors at the call** (`DslError`, nothing recorded): no `board()` yet, a key used twice, a layer that
  takes no drawing, an empty or multi-line text, a bare number for a length, corners of a rectangle that
  share a coordinate, a `direction` whose difference is 0, a `precision` outside 0 to 4.
- **Rebuilds.** As for rule areas: script drawings are written again on every build, and what was drawn
  in KiCad stays.
- **Altium.** Centred texts and graphics are written; a justified text and a dimension are reported and
  not written (`docs/altium.md`).

## Copper guard

`fenolite build` refuses to write a board whose copper shorts two nets or breaks the clearance in force
(`docs/cli-contract.md`, "Copper guard"; `--copper-check warn` reports and writes). `build_design` itself
is not guarded: it returns the files as bytes. A Python caller gets the same verdict from the files it
is about to write:

```python
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copperrules import design_rules_from_texts
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks import check_copper

output = build_design(model, placements, name="blink", copper=2, resolver=resolver, target=10)
board = read_board(output.files["blink.kicad_pcb"].decode("utf-8"), file="blink.kicad_pcb")
rules = design_rules_from_texts(
    board,
    project_text=output.files["blink.kicad_pro"].decode("utf-8"),
    rules_text=output.files["blink.kicad_dru"].decode("utf-8"),
    major=10,
    file_stem="blink",
)
report = check_copper(
    rules.design,
    pads=KicadBackend().board_pads(rules.design),
    min_clearance=rules.min_clearance,
    rules_over_classes=rules.rules_over_classes,
    floor_over_rules=rules.floor_over_rules,
)
errors = [issue for issue in report.issues if issue.severity == "error"]
```

`report.findings` holds each short and clearance violation with its layer, a point and both items;
write the files only when `errors` is empty.

## Drawing sheet and title block

```python
design.sheet("A3", drawing_sheet="frames/mine.kicad_wks")
design.title_block(title="Blink", revision="B", variables={"PROJECT_CODE": "X1"})
```

- **`design.sheet(paper="A4", *, portrait=False, width=None, height=None, drawing_sheet=None)`** sets the
  board's paper: `A0` to `A5`, `Letter`, `Legal`, `Tabloid`, or `custom` with `width` and `height`
  (lengths, given together). It is called at most once.
- **`drawing_sheet`** names your frame: a `.kicad_wks` file, or a `*.sheet.toml` specification
  (`docs/sheet-templates.md`), by a path relative to the folder of the design script. Any other ending,
  an absolute path or a path that leaves that folder raises `DslError`. Fenolite ships no frame of any
  organisation: the file is yours.
- **The build writes `<name>.kicad_wks`** beside the project from that source and names it in the
  project file, so `pcbnew` shows it; when a build writes a schematic, the schematic's key is set too. A
  `.kicad_wks` is written again, not copied: the root becomes `kicad_wks` and a token that the target
  KiCad does not know is refused. Your source file is never changed. A missing source stops the build
  (`FEN-3001`), because KiCad would fall back to its default frame without a word.
- The model holds the written name, never your path: `dsl.drawing_sheet_source(design)` gives the path.
- **`design.title_block(*, title, date, revision, organization, doc_id, responsible, approver,
  variables)`** sets the title block, at most once. `variables` maps names (`[A-Za-z_][A-Za-z0-9_]*`) to
  texts: they become the project's text variables, which a drawing sheet shows as `${NAME}`. A name that
  KiCad reserves is refused by the project writer.
- **On a rebuild** the paper and the title block that the script declares are written again from the
  script. Without these calls the board keeps the ones it has (`docs/lens.md`).
- `result.drawing_sheet` of `build` holds `source`, `file` and `items`, or `null`.

## Path aliases (`moved()`)

`design.moved(old, new)` records that the part or the module at path `new` was at `old` in an earlier
build, so a rebuild keeps its layout (`docs/lens.md`, "moved()" and "Module aliases").

- **Part alias.** When `new` is a component path of the design (`R1`, `power/R1`), the part keeps the
  footprint that was at `old`.
- **Module alias.** When `new` is a module path of the design, every part `<new>/<rest>` gets the alias
  `<old>/<rest>`, and the module's nets follow ("Net aliases" below). A part alias wins over a module
  alias for its part, and a longer module path over a shorter one, so `moved("power", "supply")` and
  `moved("power/R1", "supply/R9")` can be written together.
- `dsl.moves(design)` returns the part aliases, new path to old path, with every module alias expanded;
  `dsl.module_moves(design)` returns the module aliases.
- **Errors.** `old == new`, a malformed path and a second alias with the same `old` or the same `new`
  raise `DslError` at the call. `moves` and `module_moves` raise it when `new` is neither a part nor a
  module of the design, or when `old` still is one, so chains are refused; `fenolite build` reports this
  as `FEN-3004`.
- Aliases are not model data: `to_model` and every id ignore them. One build is enough: the footprint is
  kept under its new path, and the alias can then be removed.

### Net aliases (`moved_net()`)

`design.moved_net(old, new)` records that the net named `new` was named `old`, so the rebuild keeps its
tracks, vias and zones under the new name (`docs/lens.md`, "Net aliases"). `dsl.net_moves(design)` returns
the aliases, new name to old name. `new` must be a net of the design and `old` must not be; the same
errors as for `moved()` apply. A net alias is not model data and is needed for one build only. A net
under a renamed module needs no call: the module alias covers it.

## Determinism

A build is a pure function of the script and the Fenolite version: ids come from keys, files hold no
date, and sets are never iterated in hash order, so builds with different `--seed`, `--timestamp` and
`PYTHONHASHSEED` values (S-0072) are byte-identical. `--seed` and `--timestamp` are accepted and unused.

## Output layout

Under `--out DIR` (never the script folder):

- `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`;
- `<name>.kicad_sch`, `sym-lib-table` and `lib/<nickname>.kicad_sym`: the schematic and the symbols
  it uses (`docs/schematic.md`); not written with `--schematic skip`, except the libraries of
  symbols that the script authors;
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
merged, not replaced (`docs/lens.md`). The schematic is generated again by every build: an edited one
is replaced with the warning `build.schematic-replaced` and a `.bak` copy (`docs/schematic.md`,
"Rebuilding"). The other outputs have no merge: before the plan is returned (so `--dry-run` refuses
too), `fp-lib-table`, `sym-lib-table` and each vendored footprint or symbol library under `lib/` that
already exists must either have the planned bytes or the SHA-256 recorded in `.fenolite/build.json`. Anything else is
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

## Net ties

A net tie joins pads of different nets on purpose: a star ground, a Kelvin lead. In an authored footprint
the join is copper you draw (pads that overlap, or a `line`, `rect`, `circle` or `polygon` on a copper
layer), and `net_tie()` says that it is meant:

```python
tie = Footprint("Local", "StarPoint", kind="smd")
tie.pad("1", at=(mm(-0.5), mm(0)), size=(mm(0.5), mm(0.5)))
tie.pad("2", at=(mm(0.5), mm(0)), size=(mm(0.5), mm(0.5)))
tie.line((mm(-0.5), mm(0)), (mm(0.5), mm(0)), layer="F.Cu", width=mm(0.3))  # the copper bridge
tie.net_tie("1", "2")
design.add_footprint(tie)
```

- `net_tie(*numbers)` declares one group of at least two pad numbers. A number must name a pad of the
  footprint and may be in one group only; both are checked when the definition is read.
- The KiCad build writes `(net_tie_pad_groups "1, 2")` into the library footprint and the board
  footprint, as KiCad's own net-tie footprints have it, and KiCad's DRC then judges no pair of pads of
  the footprint.
- Fenolite's copper check, and so the copper guard of the build, do not judge two pads of one group.
  A pad outside the group, and a track near a tied pad, are judged as on any footprint. The bridge
  itself is a graphic, which the copper check does not see.
- A footprint from a KiCad library keeps the groups its file has; they cannot be edited from a script.
- `--target altium` writes the pads and no mark that ties them, and says so (`docs/altium.md`).

## Waivers

`design.waive()` accepts one finding of `fenolite check`, or of the copper guard of the build, with a
reason. The finding stays listed, as `info`, with the waiver's name and reason, so the exit code no
longer counts it and nothing is hidden.

```python
design.waive("copper.clearance", "J1-3", "J1-4", reason="fixed by the mating connector", name="pitch")
design.waive("copper.clearance", "J1-*", "*", min_gap=mm(0.15), reason="shield can keep-out")
design.waive("kicad.drc.via-dangling", "*", reason="test points")
design.waive("kicad.drc.courtyards-overlap", tp1, "U1", reason="stacked by design")
```

- **Code.** `copper.short`, `copper.clearance`, `copper.zone-overlap`, or a finding of KiCad's DRC as
  `check` prints it, `kicad.drc.<type>`. The three verdicts of the DRC stage (`rules-not-loaded`,
  `rules-unchecked`, `parity-unchecked`) are not findings. ERC and parity findings are not waived: an
  ERC finding has its own means in the script (`no_connect`, a power flag), and a parity finding is a
  defect of the build.
- **Items.** One name per item of the finding, as its `where` prints it: `REF-PIN` for a pad, `REF` for a
  footprint, a locator for a track, a via or a zone, `@x,y` for an item without a name. The order does not
  matter, a `Part` stands for its reference, and `*`, `?` and `[…]` are patterns. A copper finding has two
  items.
- **Reason.** One non-empty line. It is printed with every finding the waiver accepts.
- **Shorts** (`copper.short`, `kicad.drc.shorting-items`) take exact names only: an intended short is one
  net tie, and a pattern could cover a second one. Prefer `Footprint.net_tie` for a short inside a
  footprint you author.
- **`min_gap`** belongs to `copper.clearance`: the finding is accepted only while its gap is at least that
  length, so a closer gap stays an error. A clearance waiver with a pattern needs it. A DRC finding has
  no distance in KiCad's report, so `min_gap` is refused there.
- **`name`** defaults to `<code>:<items joined by ",">`. Two waivers of one name are refused, so the same
  waiver cannot be declared twice.
- **Prefer a rule for a clearance that a selector can name.** A waiver accepts one finding by the names
  of its items; a rule (`design.rules.rule()`) changes the clearance in force for every item it selects,
  in both checks. A waiver is applied by Fenolite only: KiCad's own entry for the same copper stays an
  error until it is waived too, by its `kicad.drc.*` code.

The build stores the waivers in `.fenolite/findings.json`. `fenolite check` reports a waiver that
matched nothing as `check.waiver-unmatched` (`docs/cli-contract.md`, "Waivers"); the names of tracks are
locators, which shift when items are added, so name pads and footprints where you can.

## Check severities

`design.rules.severity()` gives one check of KiCad's DRC a severity in the project file:

```python
design.rules.severity("kicad.drc.silk-overlap", "ignore")
design.rules.severity("kicad.drc.via-dangling", "error")
```

- The code is the finding code that `check` prints (`kicad.drc.<type>`); the level is `error`, `warning`
  or `ignore`. A code may be given one severity.
- The build writes the check's key of `rule_severities`. A code whose key the target KiCad does not have
  is refused when the project is written (`kicad.project.unknown-check`): KiCad would ignore it without
  a message, so a misspelt code would do nothing.
- A `copper.*` finding takes no severity: accept one finding with `design.waive()`.
- `kicad.drc.clearance` cannot be ignored, because `check` needs clearance entries to prove that the
  rules were loaded.
- `--target altium` writes no severity and says so (`docs/altium.md`).
