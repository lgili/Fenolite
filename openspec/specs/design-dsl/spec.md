# design-dsl Specification

## Purpose
Specify the stdlib-only Python DSL that describes a design (parts, nets, net classes, interfaces, outline and placements, with unit-carrying lengths and ids keyed by names and paths) and the `fenolite build` command that turns a design script into a self-contained, reproducible KiCad project.
## Requirements
### Requirement: DSL package
The package `fenolite.dsl` SHALL provide a thin, stdlib-only API to describe a design in Python, and MUST import only `core` and `model` (`package-layering`).
- Modules: `design.py` (`Design`, `Rules`), `module.py` (`Module`), `part.py` (`Part`, `PinHandle`, `Net`, `connect`, `Placement`), `interfaces.py` (`Interface`, `Power`, `DiffPair`), `units.py` (`Length`, `mm`, `mil`, `inch`, `nm`), `convert.py` (`to_model`, `placements`, `KEYS`, `BOARD_ORIGIN`), `errors.py` (`DslError(ValueError)`) and `_minimal.py`, a packaged hermetic example.
- `fenolite.dsl` MUST re-export `Design`, `Module`, `Part`, `Net`, `connect`, `Interface`, `Power`, `DiffPair`, `Length`, `mm`, `mil`, `inch`, `nm`, `Placement`, `BOARD_ORIGIN`, `to_model`, `placements`, `KEYS`, `DSL_BACKEND` (`"dsl"`) and `DslError`.
- The root package `fenolite` MUST re-export neither the DSL `Design` nor the model `Design`. Inside `dsl`, the model class MUST be imported as `ModelDesign`.
- Objects MUST join a design only through `add()`. There is no hidden global or "current design" state.
- The DSL MUST store lib ids as strings only. It MUST NOT read a library, a file or the environment, and MUST NOT import a backend.
- There are no part classes, no part picker, no solver, no `moved()` (c0019) and no custom-rule constructor.

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change, and every import inside `src/fenolite/dsl/` is of the standard library, `fenolite.core` or `fenolite.model`

#### Scenario: Root package exports no Design
- **WHEN** `python -c "import fenolite; print(hasattr(fenolite, 'Design'))"` runs
- **THEN** it prints `False`

#### Scenario: No hidden membership
- **GIVEN** a `Design` and a `Part("R9", "Mini:Mini_R")` that is created but never added
- **WHEN** `to_model(design)` runs
- **THEN** the model holds no component `R9`

### Requirement: DSL lengths and angles
Every length argument of the DSL SHALL be a `Length` or a string with a unit, and every angle argument SHALL be in degrees; no float MUST reach the model.
- A `Length` holds an exact integer number of nanometres. It is made by `mm()`, `mil()`, `inch()` or `nm()`, or from a string with a unit (`"2.54mm"`) through `core.units.parse_length` with no default unit.
- A bare `int`, `float` or `bool`, or a string without a unit, given as a length MUST raise `DslError` naming the argument, so `place(10, 5)` is refused instead of meaning 10 nm.
- The helpers MUST accept `int`, `str` and `float`. A float MUST be converted exactly from `repr(x)`, its shortest round-trip form (S-0073), and a value that is not a whole number of nanometres MUST raise `DslError`. `bool` MUST be refused.
- `Length` MUST support `==`, `hash`, `+`, `-`, unary `-`, and `*` and `//` by an `int`.
- Angles MUST be given as an `int`, a string (`"30.5"` or `"30.5deg"`) or a float converted through `repr`, MUST be whole microdegrees, and MUST be normalised to [0°, 360°).

#### Scenario: Bare numbers are refused
- **WHEN** `part.place(10, 5)` is called
- **THEN** `DslError` is raised naming the argument `x`

#### Scenario: Exact float conversion
- **WHEN** `mm(0.1)`, `mil(10)` and `inch("0.5")` are evaluated
- **THEN** they equal `nm(100_000)`, `nm(254_000)` and `nm(12_700_000)`

#### Scenario: Inexact float refused
- **WHEN** `mm(1/3)` is evaluated
- **THEN** `DslError` is raised

#### Scenario: Strings with units
- **WHEN** `part.place("2.54mm", "-1.27mm")` is called
- **THEN** the stored offsets are 2 540 000 nm and −1 270 000 nm

#### Scenario: Angles are normalised
- **WHEN** parts are placed with `rot=-90`, `rot="30.5deg"` and `rot=450`
- **THEN** their rotations are 270 000 000, 30 500 000 and 90 000 000 microdegrees

### Requirement: Design structure and names
`Design(name)`, `Module(name)` and `Part(ref, lib_id, footprint=None, value="")` SHALL build a tree whose paths name every component, and SHALL raise `DslError` at the offending call for every structural error of this list.
- A design name MUST match `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, because it becomes the stem of the KiCad files. Module names and refs MUST match `[A-Za-z0-9_.+-]+`.
- `Design.add(*objs)` and `Module.add(*objs)` attach parts, modules, nets and interfaces. `Module.path` is the module name at the top and `<parent path>/<name>` below. A component path is `<module path>/<ref>` (`power/ldo/C1`), or `<ref>` at the top.
- Net names are global and literal. A module-local net is named by the script, for example `Net(f"{m.path}/FB")`.
- `DslError` MUST be raised for: a duplicate component or module path; a duplicate net, net-class or interface name; two distinct `Net` objects with one name; a net in two classes; a second `place()` or `board()`; a `copper` other than 2 or 4; one designator connected to two nets; a `side` other than `top` and `bottom`; an invalid name or ref.
- Equal refs in different modules are not a DSL error. They are left to `Design.validate()` (`model.duplicate-ref`, exit 5 from `build`).

#### Scenario: Paths from modules
- **GIVEN** `Module("power")` holding `Module("ldo")` holding `Part("C1", "Mini:Mini_R")`, added to a design
- **WHEN** `part.path` is read
- **THEN** it is `"power/ldo/C1"`

#### Scenario: Two nets with one name
- **WHEN** `Net("GND")` and a second `Net("GND")` are both added to one design
- **THEN** `DslError` is raised at the second `add()` naming `GND`

#### Scenario: Placed twice
- **WHEN** `r1.place(mm(1), mm(1))` is called twice
- **THEN** the second call raises `DslError`

#### Scenario: Duplicate refs in two modules
- **GIVEN** a blink variant with modules `a` and `b`, each holding a part `R1` of `Mini:Mini_R`
- **WHEN** the design is built with `fenolite build ... --dry-run`
- **THEN** the exit code is 5 and `issues` holds `model.duplicate-ref`

#### Scenario: Invalid design name
- **WHEN** `Design("my board")` is called
- **THEN** `DslError` is raised naming the pattern

### Requirement: Connections and pin designators
`part[designator]` SHALL return a pin handle and `connect(net, *pins) -> Net` SHALL record that each pin joins `net`; designators MUST be stored as written and resolved only by the build ("Pins and pads in a build").
- A designator MUST be a non-empty `str` or an `int`; `part[1]` and `part["1"]` MUST name the same pin. A pin name such as `part["GND"]` is accepted as written.
- `net` MUST be a `Net`; any other value MUST raise `DslError`. There are no implicit nets and no net merges.
- A net joins the design when it is added, or when it is connected to a pin of an added part.
- Connecting the same designator of one part to two different nets MUST raise `DslError` at the second `connect`. Connecting it twice to the same net MUST keep one membership.

#### Scenario: Integer and string designators
- **GIVEN** `connect(vin, u1[1])` and `connect(vin, u1["1"])`
- **WHEN** `to_model(design)` runs
- **THEN** the net `VIN` holds one member for `U1` with `pin == "1"`

#### Scenario: Designator on two nets
- **WHEN** `connect(a, r1["1"])` is followed by `connect(b, r1["1"])`
- **THEN** `DslError` is raised naming `R1` and `1`

#### Scenario: Net given as a string
- **WHEN** `connect("GND", r1["2"])` is called
- **THEN** `DslError` is raised

### Requirement: Board and placements in the DSL
`Design.board(width, height, copper=2)` SHALL declare a rectangular board and `Part.place(x, y, rot=0, side="top", locked=False)` SHALL request a placement, both in a board-relative frame.
- The frame has its origin at the top-left corner of the outline, with Y down. `BOARD_ORIGIN` MUST be `Point(100_000_000, 100_000_000)`, a Fenolite choice: the outline is written from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)`, and a part placed at `(x, y)` is written at `BOARD_ORIGIN + (x, y)`.
- `width` and `height` MUST be positive lengths. `copper` MUST be 2 or 4.
- `rot` is the model rotation, the stored footprint angle on both sides (c0017).
- `placements(design) -> Mapping[str, Placement]` MUST map each placed component path, in path order, to `Placement(at, rotation, side, locked)`. Unplaced parts MUST be absent.

#### Scenario: Placement in board coordinates
- **GIVEN** `r1.place(mm(10), mm(5), rot=90, side="bottom", locked=True)`
- **WHEN** `placements(design)["R1"]` is read
- **THEN** it equals `Placement(Point(110_000_000, 105_000_000), 90_000_000, "bottom", True)`

#### Scenario: Unsupported copper count
- **WHEN** `design.board(mm(50), mm(30), copper=3)` is called
- **THEN** `DslError` is raised

#### Scenario: Unplaced parts are absent
- **GIVEN** a design with `R1` placed and `R2` not placed
- **WHEN** `placements(design)` is called
- **THEN** its keys are exactly `("R1",)`

### Requirement: Net classes in the DSL
`design.rules.netclass(name, *, clearance=None, track_width=None, via_diameter=None, via_drill=None, nets=())` SHALL declare one net class whose values are lengths and whose members are the given `Net` objects.
- Each given net joins the design and gets `Net.netclass_id` of that class in the model.
- A class name used twice, or a net given to two classes, MUST raise `DslError`.
- No other rule constructor exists. The model `RuleSet` of a DSL design is empty, and the build lowers it through c0018 to `(version 1)`.

#### Scenario: Class with members
- **GIVEN** `d.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))`
- **WHEN** `to_model(d)` runs
- **THEN** the model holds a `NetClass` named `PWR` with `clearance == 200_000` and `track_width == 500_000`, and the nets `VIN` and `GND` carry its id in `netclass_id`

#### Scenario: Net in two classes
- **WHEN** a net already in `PWR` is given to a second class `SIG`
- **THEN** `DslError` is raised naming the net and both classes

### Requirement: Interfaces in the DSL
`Interface(name, kind, members)`, `Power(hv, lv, *, name=None)` and `DiffPair(p, n, *, name=None)` SHALL record groups of nets as model `Interface` entities, without any model delta.
- `Power(hv, lv)` MUST become `Interface(kind="power", members={"hv": <net id>, "lv": <net id>})`, and `DiffPair(p, n)` MUST become `Interface(kind="diff_pair", members={"p": <net id>, "n": <net id>})`.
- The default name MUST be `"<first net name>/<second net name>"`.
- Member nets join the design.
- Interfaces are not lowered to KiCad. A build MUST give one `build.interface-not-lowered` info per `diff_pair` interface.

#### Scenario: Power interface
- **GIVEN** `Power(vin, gnd)` added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `VIN/GND` with kind `power` and members `hv` and `lv` equal to the ids of `VIN` and `GND`

#### Scenario: Diff pair reported
- **GIVEN** a blink variant holding `DiffPair(usb_p, usb_n)` on nets `USB_P` and `USB_N`
- **WHEN** it is built with `--dry-run`
- **THEN** `issues` holds one info `build.interface-not-lowered` naming `USB_P/USB_N`

### Requirement: DSL to model
`dsl.to_model(design) -> fenolite.model.Design` SHALL convert a DSL design into model types only, with the ids of `design-model` "Identifier derivation" (fourth case).
- **Circuit.** One `Component` per added part, with `ref`, `value`, `lib_symbol_ref`, `lib_footprint_ref` (empty when `Part.footprint` is `None`), empty `pins`, empty `path` and `properties` holding `"fenolite.path"` mapped to the component path and every entry of `Part.properties` ("User properties in the DSL"), keys in code-point order. Nets whose `PinRef.pin` holds the designator as written. Net classes with `Net.netclass_id`. Interfaces. One `Module` per DSL module, with `path`, `parent` and `component_ids`.
- **Board.** A keyed `Board` without layers and footprints, whose `Outline` is the rectangle from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)` in the order of c0017's "Outline lowering", or no outline when `board()` was not called.
- **Other layers.** An empty keyed `RuleSet`, a keyed `Manifest` and a keyed header named after the design.
- Every object MUST have `provenance = None`, so no absolute user path reaches `.fenolite/`.
- `to_model` MUST NOT call `Design.validate()`, MUST NOT resolve libraries, and MUST NOT change the DSL design.

#### Scenario: Blink in the model
- **GIVEN** the DSL design of `examples/blink_2layer/design.py`
- **WHEN** `to_model` runs
- **THEN** `R1` has `lib_symbol_ref == "Mini:Mini_R"`, `lib_footprint_ref == "Mini:Mini_R_0603"`, `pins == ()`, `path == ""` and `properties == {"fenolite.path": "R1"}`, and the outline points are (100 mm, 100 mm), (150 mm, 100 mm), (150 mm, 130 mm) and (100 mm, 130 mm)

#### Scenario: Designators as written
- **GIVEN** `connect(gnd, u1["GND"])`
- **WHEN** `to_model` runs
- **THEN** the net `GND` holds `PinRef(<U1 id>, "GND")`

#### Scenario: No provenance and no absolute path
- **WHEN** the texts of `canonical.dump_texts(to_model(design))` are searched for the absolute path of the script folder
- **THEN** no text contains it, and no entity has a provenance

#### Scenario: User properties in the model
- **GIVEN** `Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330", properties={"Supplier code": "S-1", "Part number": "PN-330"})` added to a design
- **WHEN** `to_model` runs
- **THEN** the component `R1` has `properties == {"Part number": "PN-330", "Supplier code": "S-1", "fenolite.path": "R1"}`, with its keys in this order

### Requirement: Design scripts
`fenolite.cli._script.run_design_script(path) -> ScriptRun(design, output)` SHALL run a `design.py` in-process and return its module-level `design` and its captured output.
- It MUST call `runpy.run_path(path, run_name="__fenolite_build__")` (S-0070) with `sys.dont_write_bytecode = True`, `sys.argv = [path]` and the script folder first on `sys.path` (S-0071). Afterwards it MUST restore `sys.dont_write_bytecode`, `sys.argv` and `sys.path`, and remove every `sys.modules` entry that the run added and whose file lies in the script folder, so no `__pycache__` appears and a second in-process build runs sibling modules again. Entries present before the run MUST stay.
- It MUST capture the script's stdout and stderr with `contextlib.redirect_stdout` and `redirect_stderr` (S-0074) and return them as `output`, at most `SCRIPT_OUTPUT_LIMIT = 4000` characters, truncated with a marker. The command's stdout stays exactly one JSON document.
- The script MUST bind a module-level `design` that is a `fenolite.dsl.Design`.
- Any exception raised by the script (`SystemExit` and `DslError` included) and a missing or wrong `design` MUST become `DesignScriptError(FormatError)` with `file` = the script path and `locator` = `line:<n>` of the deepest frame inside the script, or no locator when there is none. `KeyboardInterrupt` MUST propagate.
- `docs/dsl.md` and `fenolite build --help` MUST state that `build` executes `design.py` as the user's own code and must never be run on an untrusted script. No sandbox is provided.

#### Scenario: Error located by line
- **GIVEN** a `design.py` that raises `ValueError` at line 12
- **WHEN** `fenolite build design.py --out out --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and `where` ends with `:line:12`

#### Scenario: Printing scripts keep one JSON document
- **GIVEN** a `design.py` that prints `hello` before binding `design`
- **WHEN** it is built with `--dry-run --json`
- **THEN** stdout parses as one JSON document whose `result.script_output` contains `hello`

#### Scenario: Missing design
- **GIVEN** a script that binds no `design`
- **WHEN** it is built
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the message names `design`

#### Scenario: No bytecode and fresh siblings
- **GIVEN** a `design.py` that imports a sibling `parts.py`
- **WHEN** it is built twice in one process, with `parts.py` edited between the two builds
- **THEN** the second build uses the edited `parts.py`, and the script folder holds no `__pycache__`

#### Scenario: Interrupt propagates
- **GIVEN** a script that raises `KeyboardInterrupt`
- **WHEN** `run_design_script` runs it
- **THEN** `KeyboardInterrupt` propagates and `sys.path` is restored

#### Scenario: Packaged example keeps the DSL modules
- **GIVEN** `fenolite.dsl` already imported
- **WHEN** `run_design_script` runs `src/fenolite/dsl/_minimal.py` twice
- **THEN** both returned designs are instances of the `fenolite.dsl.Design` class imported before the runs, and `sys.modules["fenolite.dsl"]` is the same module object as before

### Requirement: Build command
`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project]` (`src/fenolite/cli/cmd_build.py`, schema `fenolite.build.v0`) SHALL be a mutating command that runs the script, converts it with `to_model` and `placements`, builds it with `lens.build.build_design` for `Context.kicad_target` and the `--vendor` policy, and returns every output file as a planned write under `DIR`.
- It MUST accept the global flags `--dry-run`, `--confirm`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version 9|10` and `--allow-lossy`. `--out` is required. `--discard-layout` and `--vendor` (choices `all` and `project`, default `all`, passed to `build_design` as `vendor`) are `build` options. The help text of `--vendor` MUST say that `all` copies the placed footprints of every library into `DIR/lib/` and that the copies keep their library's licence.
- An `--out` folder that resolves to the script folder MUST be a usage error (exit 2, `FEN-2001`), so the design's own tables are never overwritten.
- `input` MUST hold the script path and its SHA-256, with kind `fenolite-dsl`.
- The triad stem MUST be the design name, and plan entries MUST be sorted by path.
- `result` MUST hold `design` (the name), `target`, `out`, `files` (the planned paths), `components` and `nets` (counts), `placed` and `staged` (component paths), `vendored` (vendored footprint files), `libraries` (lib id to row origin `project`, `global` or `template`) and `script_output`, plus the dispatcher's `plan`.
- `cmd_build` MUST turn a `DslError` raised by `to_model` or `placements`, which run after `run_design_script` has returned, into `DesignScriptError` with `file` = the script path and no locator (`FEN-3004`, exit 3).
- `cmd_build` MUST read the last build record once with `lens.build.read_record(DIR)`, pass it to `build_design` and to `lens.build.check_existing` as `record`, and call `check_existing` before it returns the plan ("Edited outputs are not overwritten").
- A build with an issue of severity `error` MUST return no planned write, so it exits 5 and writes nothing.
- `example_args` (with `--dry-run`) and `mutation_example_args` MUST use the packaged `src/fenolite/dsl/_minimal.py` (Apache-2.0 header; a board with one net class and no parts), located through `fenolite.dsl.__file__`, so the consistency suite is hermetic from any working directory.

#### Scenario: Confirmation required
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --json` runs without `--confirm`
- **THEN** the exit code is 4, `result.plan` lists every planned file, and `B` is still empty

#### Scenario: Confirmed build
- **WHEN** the same command runs with `--confirm`
- **THEN** the exit code is 0, and `receipt.written` lists `B/blink.kicad_pcb`, `B/blink.kicad_pro`, `B/blink.kicad_dru`, `B/fp-lib-table`, the three footprints under `B/lib/Mini.pretty/` and the seven files under `B/.fenolite/`

#### Scenario: Rebuild is identical
- **WHEN** the confirmed build runs a second time
- **THEN** the exit code is 0, every file that the first build wrote has the same bytes as after the first build, and the only new files are the `.bak` copies that the mutation protocol keeps

#### Scenario: Output folder is the script folder
- **WHEN** `fenolite build examples/blink_2layer/design.py --out examples/blink_2layer --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Vendoring policy on the command line
- **GIVEN** a blink variant whose `R1` footprint `G:Mini_R_0603` resolves through a global row of a `KICAD_CONFIG_HOME` authored in the test and set in the environment of the run
- **WHEN** `fenolite build design.py --out B --dry-run --json` runs, and then the same command with `--vendor project`
- **THEN** the first `result.vendored` lists `lib/G.pretty/Mini_R_0603.kicad_mod`, and the second lists no file under `lib/G.pretty/` and its `issues` hold `build.global-library` naming `G:Mini_R_0603`

#### Scenario: Consistency suite
- **WHEN** `uv run pytest tests/consistency` runs from a temporary working directory
- **THEN** it passes, with `build` covered by the mutation protocol

### Requirement: Library resolution during build
The build SHALL resolve every `lib_symbol_ref` and `lib_footprint_ref` through one c0008 `LibraryResolver(LibraryConfig(target_major=ctx.kicad_target, project_dir=<script folder>))`, built with the process environment and the user's configuration folder.
- Project tables next to `design.py` are the recommended source. Global and template tables follow c0008. Official library variables come only from an `env` or `install` source of the target major, so a 10.0 install is never used for target 9 (`kicad-library-resolution`, "Library sources").
- Every `LibraryError` MUST be collected. If there is at least one, `lens.build.UnresolvedLibrariesError(LibraryError)` (`FEN-3001`) MUST be raised with the first error's hint and one `kicad.lib.*` issue per failure in `issues`.
- `Part.footprint=None` MUST fall back to the symbol's `Footprint` property. When both are empty, the build MUST give `build.no-footprint` (error).
- `value=""` MUST fall back to the symbol's `Value` property.
- `result.libraries` MUST map each lib id to the origin of its row.

#### Scenario: Two unknown lib ids
- **GIVEN** a blink variant whose parts `R1` and `D1` name `Nope:A` and `Nope:B`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and `issues` holds one `kicad.lib.*` issue for each lib id

#### Scenario: A 10.0 install is not used for target 9
- **GIVEN** only a 10.0 install made by `tests/_libs.make_install`, and a design whose footprint row uses `${KICAD9_FOOTPRINT_DIR}`
- **WHEN** `fenolite --kicad-version 9 build design.py --out out --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and its hint names `KICAD9_FOOTPRINT_DIR`

#### Scenario: Footprint and value from the symbol
- **GIVEN** `Part("U1", "Mini:Mini_QFP32_IC")` with no footprint and no value, resolved from `Mini_v9.kicad_sym`
- **WHEN** it is built
- **THEN** the component has `lib_footprint_ref == "Mini:Mini_QFP-32_7x7mm_P0.8mm"` and `value == "Mini_QFP32_IC"`

#### Scenario: No footprint anywhere
- **GIVEN** `Part("X1", "Mini:Mini_GND")`, whose symbol has an empty `Footprint` property, with no footprint
- **WHEN** it is built
- **THEN** the exit code is 5, `issues` holds `build.no-footprint` naming `X1`, and nothing is written

#### Scenario: Row origins reported
- **WHEN** the blink is built with the example's own tables and an empty `KICAD_CONFIG_HOME`
- **THEN** `result.libraries["Mini:Mini_R_0603"]` is `project`

### Requirement: Pins and pads in a build
The build SHALL fill `Component.pins` from the resolved symbol, resolve every net member to pin numbers, and give each pad the net of the pin with its number.
- `Component.pins` is the flattened symbol: `SymbolDef.pins_of(unit, body_style=1)` for every unit, keeping the first occurrence of each pin number.
- A designator MUST be read as a pin number first, and otherwise as a pin name that names every pin with that name (`U1["GND"]` joins all `GND` pins). A designator that is neither MUST give `build.unknown-pin` (error). A number that is also another pin's name MUST give `build.pin-ambiguous` (warning), and the number wins.
- After resolution, one pin on two nets MUST give `build.pin-on-two-nets` (error).
- Every pad whose number equals a pin number MUST get that pin's net, every pad of a repeated number included. A connected pin without a pad MUST give `build.pin-without-pad` (error), an unconnected pin without a pad `build.unused-pin-without-pad` (warning), and a numbered pad without a pin `build.pad-without-pin` (info). Pads with an empty number are ignored.
- Net names, or class names, that differ only in letter case MUST give `build.name-case-collision` (error), whatever c0018's `H-K-DRU-COND` measures.
- Hidden or power pins MUST NOT create implicit nets (a Fenolite choice).
- After the build, `Net.members` MUST hold `PinRef(<component id>, <pin number>)`.

#### Scenario: A name joins every pin
- **GIVEN** a symbol authored in the test whose pins `4` and `12` are both named `GND`, and `connect(gnd, u1["GND"])`
- **WHEN** the design is built
- **THEN** the net `GND` holds `PinRef(<U1 id>, "4")` and `PinRef(<U1 id>, "12")`, and the pads `4` and `12` carry the id of `GND`

#### Scenario: Unknown pin
- **GIVEN** `connect(led, r1["X"])` on `Mini:Mini_R`
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.unknown-pin` naming `R1` and `X`, and nothing is written

#### Scenario: One pin on two nets
- **GIVEN** `connect(gnd, u1["GND"])` and `connect(sense, u1["10"])` on `Mini:Mini_QFP32_IC`, whose pin `10` is named `GND`
- **WHEN** the design is built
- **THEN** `issues` holds `build.pin-on-two-nets` naming `U1` pin `10`, and the exit code is 5

#### Scenario: Pin without pad
- **GIVEN** a symbol with pins `1`, `2` and `3` placed with a two-pad footprint, and pin `3` connected
- **WHEN** the design is built
- **THEN** `issues` holds `build.pin-without-pad` (error) for pin `3`; with pin `3` unconnected it holds `build.unused-pin-without-pad` (warning) instead

#### Scenario: A number wins over a name
- **GIVEN** a symbol authored in the test whose pin `1` is named `2` and whose pin `2` is named `A`, and `connect(sig, u1["2"])`
- **WHEN** the design is built
- **THEN** the net `SIG` holds `PinRef(<U1 id>, "2")` only, and `issues` holds one `build.pin-ambiguous` warning naming `U1` and `2`

#### Scenario: Pad without pin
- **GIVEN** a symbol with pins `1` and `2` placed with a footprint authored in the test whose pads are numbered `1`, `2` and `3`, plus one pad with an empty number
- **WHEN** the design is built
- **THEN** `issues` holds one `build.pad-without-pin` info naming pad `3`, none for the pad with an empty number, and the exit code is 0

#### Scenario: Names that differ only in case
- **GIVEN** a blink variant with nets `gnd` and `GND`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.name-case-collision`, and nothing is written

### Requirement: Placement of built parts
The build SHALL place every placed part with c0017's `embed.place_footprint` and SHALL stage every unplaced part in one row beside the outline.
- A placed part MUST be `embed.place_footprint(<extended>, component=…, at=…, rotation=…, side=…, locked=…, key=<component path>, copper=<copper names>)`, with `at`, `rotation`, `side` and `locked` from its `Placement`. `<extended>` is `embed.with_property(defn, name=PATH_PROPERTY, value=<component path>)` followed by one `embed.with_property` call per user property of the component, in code-point order of names ("User properties on built footprints"). The path property is written while `H-K-BUILD-PATHPROP` holds (`kicad-file-backend`, "Path property on placed footprints"); without it, `<extended>` starts from `defn`.
- Every `place_footprint` call, staged parts included, MUST pass the part's `<extended>` definition and, as `copper`, the names of the copper layers of `layers.created_layers(copper)`, in table order (`kicad-file-backend`, MODIFIED "Footprint embedding"), so wildcard pad layers cover every copper layer of a four-layer board.
- Unplaced parts MUST be staged in component-path order in one row that starts `STAGING_OFFSET = 5_000_000` nm right of the outline's bounding box and is top-aligned with it. Each part's `footprint_extent` box MUST be left-aligned on the cursor, which then advances by the box width plus `STAGING_GAP = 2_000_000` nm. Staged parts are on the top side at 0° and unlocked, and each gives one `layout.unplaced` warning. Staging is a fixed row, not a placer (c0022).
- `Board.layers` MUST be `layers.created_layers(copper)`, re-keyed by layer name.
- A design without `board()` MUST give `build.no-board` (error).
- `Component.properties` MUST be set to exactly what `read_board` projects from the written footprint (the definition's properties, `fenolite.path`, the user properties, `Reference` and `Value`), so c0017's "Projected fields on write" passes unchanged. `Component.path` MUST stay empty: no footprint `path`, `sheetname` or `sheetfile` is written before schematics (v0.2a).
- `lens` MUST read the `footprint_extent` box by attribute and MUST NOT import `geometry`.

#### Scenario: Placed parts
- **WHEN** the blink is built
- **THEN** each footprint instance has `position` equal to `BOARD_ORIGIN` plus its DSL offset, `D1` has `side == "bottom"`, `U1` has `locked == True`, and the footprint instances carry the ids of c0017's placed copies with keys `U1`, `R1` and `D1`

#### Scenario: Staging row
- **GIVEN** a blink variant in which `D1` and `R1` are not placed
- **WHEN** it is built
- **THEN** the extent box of `D1`, moved to its position, has its left edge at 155 mm and its top edge at 100 mm, the box of `R1` has its left edge 2 mm right of the right edge of `D1`'s box and its top edge at 100 mm, `issues` holds two `layout.unplaced` warnings, and the exit code is 0

#### Scenario: No board
- **GIVEN** a blink variant without `board()`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.no-board`, and nothing is written

#### Scenario: Write accepts the built properties
- **WHEN** the blink is built for targets 9 and 10
- **THEN** `write_triad` raises no `kicad.board.projection-read-only`, and every component has `path == ""` and `properties["fenolite.path"]` equal to its component path

#### Scenario: Staged parts carry their properties
- **GIVEN** a blink variant in which `R1` is not placed and has `properties={"Part number": "PN-330"}`
- **WHEN** it is built and the written board is read with `read_board`
- **THEN** the staged `R1` footprint holds the hidden `Part number` property after `fenolite.path`, and the read-back `R1` has `properties["Part number"] == "PN-330"`

#### Scenario: Four-layer build
- **GIVEN** a blink variant whose board is declared with `copper=4`
- **WHEN** it is built for target 10 with `--confirm` and the written board is read with `read_board`
- **THEN** the exit code is 0, and pad `"1"` of `D1` (`Mini_LED_THT_3mm`) has the copper layers `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` in the built model and in the read-back board

### Requirement: Built project files
`lens.build.build_design(design, placements, *, name, copper, resolver, target=DEFAULT_TARGET, allow_lossy=False, vendor="all", record=None) -> BuildOutput` SHALL return every file of a self-contained KiCad project as bytes, and SHALL return no file when any issue has severity `error`.
- The steps MUST run in this order: resolve libraries; fill pins and resolve net members; place, stage, set layers and assign pad nets; run the build checks (those of "Pins and pads in a build", "Placement of built parts", "User properties on built footprints" and "Footprints of every row origin are vendored") and `Design.validate()`; call c0010's `triad.write_triad(design, name=name, target=target, existing_project=None, allow_lossy=allow_lossy, issues=…)`, which lowers rules through c0018 and net classes through c0010; add the vendored footprints, `fp-lib-table`, the `.fenolite/` texts and `.fenolite/build.json`; combine evidence.
- An issue of severity `error` before the writer MUST return a `BuildOutput` with its issues and empty `files`. Writer refusals (`LossyWriteError`, `RulesLossError`, `FEN-7001`) MUST propagate with their issues.
- `BuildOutput` is a frozen dataclass with `design`, `files: Mapping[str, bytes]` (paths relative to `--out`), `issues`, `evidence` and `summary`.
- The layout MUST be `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, `fp-lib-table`, `lib/<nickname>.pretty/<entry>.kicad_mod`, the six layer files under `.fenolite/` and `.fenolite/build.json`.
- Every vendored footprint MUST be copied byte for byte from `Location.item_path` to `lib/<nickname>.pretty/<entry>.kicad_mod`, and `fp-lib-table` MUST hold one row per vendored nickname with `uri "${KIPRJMOD}/lib/<nickname>.pretty"`, written by `libs.write_lib_table` for the target. With `vendor="all"`, every footprint that the build places is vendored, whatever the origin of its row; with `vendor="project"`, only footprints resolved through a project-table row are ("Footprints of every row origin are vendored"). Any other `vendor` MUST raise `ValueError`.
- With `vendor="project"`, footprints from rows of another origin MUST NOT be vendored and get no row (`build.global-library`, info). A vendored file whose header version is newer than the target's newest format MUST give `build.library-too-new` (warning). With `record`, a vendored file whose bytes differ from the hash recorded for its path MUST give `build.library-changed` (warning).
- The build MUST NOT write a `sym-lib-table`, a symbol file, a `.kicad_prl`, a `native/` folder or a date.
- The `.fenolite/` layer texts MUST come from `canonical.dump_texts`, with an empty `findings.json` and no `FootprintDef`. `.fenolite/build.json` MUST have `schema` `fenolite.build-record.v0`, sorted keys and no date, and MUST record the SHA-256 of every file outside `.fenolite/` that the build writes. It is regenerable and marks a built project.

#### Scenario: Files of a target-9 build
- **WHEN** the blink is built for target 9
- **THEN** `files` holds exactly the triad `blink.*`, `fp-lib-table` without a `version` child, three files under `lib/Mini.pretty/` byte-equal to their sources in `tests/data/libs/Mini_v9.pretty/`, the six layer files under `.fenolite/` and `.fenolite/build.json`

#### Scenario: Build record
- **WHEN** `.fenolite/build.json` of a blink build is read
- **THEN** its `schema` is `fenolite.build-record.v0`, it holds no date, and it maps each of the seven files outside `.fenolite/` to its SHA-256

#### Scenario: Errors produce no files
- **GIVEN** a blink variant with `connect(led, r1["X"])`
- **WHEN** `build_design` runs
- **THEN** the returned `files` is empty and `issues` holds `build.unknown-pin`

#### Scenario: Unsafe class pattern refused
- **GIVEN** a blink variant with a net `D[0]` in class `PWR` and a net `D0` beside it
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, `issues` holds `kicad.project.pattern-unsafe`, and nothing is written

#### Scenario: Global footprint vendored
- **GIVEN** a blink variant whose `R1` footprint `G:Mini_R_0603` resolves through a global `fp-lib-table` row of a `KICAD_CONFIG_HOME` authored in the test, the other footprints resolving through the project table
- **WHEN** `build_design` runs with the default `vendor`
- **THEN** `files` holds `lib/G.pretty/Mini_R_0603.kicad_mod`, byte-equal to its source, `fp-lib-table` holds the rows `G` and `Mini` in this order, and `issues` holds no `build.global-library`

#### Scenario: Global footprint kept out on request
- **GIVEN** the same variant
- **WHEN** `build_design` runs with `vendor="project"`
- **THEN** `issues` holds one `build.global-library` info naming `G:Mini_R_0603`, `files` holds no file under `lib/G.pretty/`, and `fp-lib-table` holds no row named `G`

#### Scenario: Unknown vendoring policy
- **WHEN** `build_design` runs with `vendor="none"`
- **THEN** `ValueError` is raised naming `all` and `project`

#### Scenario: Vendored file newer than the target
- **GIVEN** a blink variant whose project table names a folder holding a copy of `Mini_v9.pretty/Mini_R_0603.kicad_mod` authored in the test with header version `20260206` and no 10-only token
- **WHEN** `build_design` runs for target 9
- **THEN** `issues` holds one `build.library-too-new` warning naming the vendored file, and `files` holds the vendored copy byte-equal to its source

#### Scenario: The built folder moves whole
- **GIVEN** a confirmed blink build copied to another folder
- **WHEN** a resolver with `project_dir` set to the copy locates `Mini:Mini_R_0603`
- **THEN** the item path is `lib/Mini.pretty/Mini_R_0603.kicad_mod` inside the copy

### Requirement: Edited outputs are not overwritten
`lens.build.check_existing(out_dir, files, *, record, discard_layout) -> None` SHALL refuse to replace a file outside `.fenolite/` that changed since Fenolite last wrote it, until c0019 preserves layouts. For each planned file outside `.fenolite/` that already exists:
- bytes equal to the planned bytes: an identical rewrite, allowed;
- SHA-256 equal to the one recorded in `.fenolite/build.json`: untouched since the last build, allowed, so a DSL edit never needs `--discard-layout`;
- otherwise (edited, for example in KiCad, or found without a record): `LayoutExistsError` MUST be raised, with `cli_code = "FEN-7001"` (exit 7), one `build.layout-exists` issue per file, and the hint "re-run with --discard-layout to replace them (backups are kept), or build into another --out folder".

Further rules:
- The check MUST run before the plan is returned, so `--dry-run` refuses too, and nothing is written.
- `--discard-layout` MUST skip the check; the mutation protocol then keeps a `.bak` of each replaced file unless `--no-backup` is given. `--allow-lossy` MUST NOT skip the check.
- Without a record (for example after `.fenolite/` was deleted), only identical bytes are allowed.

#### Scenario: DSL edit needs no flag
- **GIVEN** a confirmed blink build in `B`
- **WHEN** `R1` is moved in `design.py` and the build runs again with `--confirm`
- **THEN** the exit code is 0 and `B/blink.kicad_pcb` holds the new position

#### Scenario: Edited board refused
- **GIVEN** a confirmed blink build in `B` and one byte of `B/blink.kicad_pcb` changed afterwards
- **WHEN** the build runs again with `--confirm`, and then with `--dry-run`
- **THEN** both exit 7 with `FEN-7001`, the envelope's `issues` holds `build.layout-exists` naming `B/blink.kicad_pcb`, and no file under `B` changes

#### Scenario: Discarding the layout
- **GIVEN** the same edited board
- **WHEN** the build runs with `--discard-layout --confirm`
- **THEN** the exit code is 0, and `B/blink.kicad_pcb.bak` holds the edited bytes

#### Scenario: Lost record
- **GIVEN** two copies of a confirmed blink build, each with its `.fenolite/` folder deleted
- **WHEN** the build runs again with `--confirm` into the first copy with the script unchanged, and into the second copy after `R1` is moved
- **THEN** the first run exits 0 with identical bytes, and the second exits 7 with `build.layout-exists` naming `blink.kicad_pcb`

#### Scenario: Lossy flag does not skip the check
- **GIVEN** the edited board
- **WHEN** the build runs with `--allow-lossy --confirm`
- **THEN** the exit code is 7 with `build.layout-exists`

### Requirement: Build issue codes
The build SHALL report its own findings only with the codes of the closed table `lens.build.BUILD_ISSUE_CODES`. Codes of the writers (`kicad.board.*`, `kicad.project.*`, `rules.*`), of the resolver (`kicad.lib.*`) and of `Design.validate()` (`model.*`) MUST pass through unchanged.

| code | severity | when |
|---|---|---|
| `build.unknown-pin` | error | a designator is neither a pin number nor a pin name |
| `build.pin-on-two-nets` | error | a resolved pin is on two nets |
| `build.pin-without-pad` | error | a connected pin has no pad of its number |
| `build.no-footprint` | error | neither the part nor the symbol names a footprint |
| `build.no-board` | error | the design has no `board()` |
| `build.name-case-collision` | error | net or class names differ only in letter case |
| `build.layout-exists` | error | an output changed since the last build (carried by `LayoutExistsError`) |
| `build.property-reserved` | error | a user property has a reserved name or prefix |
| `build.property-invalid` | error | a user property name or value is not printable text, a name has surrounding whitespace, or two names differ only in letter case |
| `build.property-conflict` | error | the footprint definition holds a property of the same name with another value |
| `build.vendor-unsafe-name` | error | a vendored nickname holds a path separator or a non-printable character, or two vendored paths differ only in letter case |
| `build.pin-ambiguous` | warning | a pin number is also another pin's name |
| `build.unused-pin-without-pad` | warning | an unconnected pin has no pad of its number |
| `build.library-too-new` | warning | a vendored file is newer than the target's newest format |
| `build.library-changed` | warning | a vendored file differs from the copy that the last build recorded |
| `layout.unplaced` | warning | a part was staged beside the outline |
| `build.pad-without-pin` | info | a numbered pad has no pin of its number |
| `build.global-library` | info | with `vendor="project"`, a footprint came from a row whose origin is not `project` and is not vendored |
| `build.interface-not-lowered` | info | a `diff_pair` interface is kept in the model only |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_build_issues.py -k closed_set` collects every issue code produced by the build tests
- **THEN** each code other than `kicad.*`, `rules.*` and `model.*` is a key of `BUILD_ISSUE_CODES` with the severity of this table, and every key of the table is produced by at least one test

#### Scenario: Warnings do not fail
- **GIVEN** the blink with `R1` not placed
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 0 and `issues` holds one `layout.unplaced` warning naming `R1`

### Requirement: Build evidence
The `build` envelope SHALL carry `Evidence.combine` (lowest wins) of `lens.build.BUILD_EVIDENCE` (`INFERRED`; `H-K-BUILD-TRIAD`, `H-K-BUILD-CLASS`, `H-K-BUILD-LIBTABLE`, `H-K-BUILD-PATHPROP`), `sym.EVIDENCE` and `mod.EVIDENCE` (`H-K-LIB-READ`), `pcb.WRITE_EVIDENCE` (`H-K-PCB-WRITE`), `pro.EVIDENCE` (`H-K-PRO-PATTERNS`), `lowering.EVIDENCE`, when a part is on the bottom side `embed.EVIDENCE`, when a user property is written `lens.build.PROPERTY_EVIDENCE` (`INFERRED`; `H-K-VENDOR-PROPS`, `H-K-VENDOR-DUPNAME`), and when a footprint of a row whose origin is not `project` is vendored `lens.build.VENDOR_EVIDENCE` (`INFERRED`; `H-K-VENDOR-GLOBAL`, `H-K-VENDOR-SHADOW`).
- The level MUST stay `INFERRED` while any of these is below `KICAD-VERIFIED`.
- `PROPERTY_EVIDENCE` and `VENDOR_EVIDENCE` MUST stay `INFERRED` after their rows are settled, because the oracle covers the blink and its variants, not every design.
- `KICAD-VERIFIED` applies to the blink example only, through the oracle suite (`kicad-oracle`, "Built projects pass the build oracle"), and MUST NOT be reported for an arbitrary build.

#### Scenario: Blink envelope
- **WHEN** the blink is built with `--dry-run --json`
- **THEN** `evidence.level` is `INFERRED`, and `evidence.hypotheses` contains `H-K-BUILD-TRIAD`, `H-K-LIB-READ` and `H-K-PCB-WRITE`

#### Scenario: Bottom parts add the flip rows
- **GIVEN** the blink, whose `D1` is on the bottom, and a variant with `D1` on the top
- **WHEN** both are built with `--dry-run --json`
- **THEN** only the first envelope's `evidence.hypotheses` contains the hypotheses of `embed.EVIDENCE`

#### Scenario: Properties and vendoring add their rows
- **GIVEN** the blink, a variant with `properties={"Part number": "PN-330"}` on `R1`, and a variant whose footprints come from a global table authored in the test
- **WHEN** the three are built with `--dry-run --json`
- **THEN** only the second envelope's `evidence.hypotheses` contains `H-K-VENDOR-PROPS`, only the third contains `H-K-VENDOR-GLOBAL`, and every `evidence.level` is `INFERRED`

### Requirement: Reproducible builds
Two builds of the same script for the same target SHALL give byte-identical files under `--out`, `.fenolite/` included and `.bak` files excluded, whatever the values of `--seed`, `--timestamp` and `PYTHONHASHSEED` (S-0072).
- Every output collection MUST be sorted by name or path. Library table uris MUST be `${KIPRJMOD}`-relative. Outputs MUST hold no date and no absolute path.
- `--seed` changes nothing, because DSL ids are keyed (`design-model`, "Identifier derivation"). `--timestamp` is accepted and unused, because a build writes no date (no command generates a title-block date; `TitleBlock.date` is set by the user, c0012). Both follow the MODIFIED `cli-contract` "Determinism flags".
- A build MUST leave the script folder unchanged: the same file list, the same SHA-256 values and no `__pycache__`.
- Deleting `.fenolite/` and building again MUST restore identical bytes.

#### Scenario: Twice in-process and twice by subprocess
- **WHEN** `uv run pytest tests/unit/lens/test_build_determinism.py` builds the blink for targets 9 and 10 twice in-process, and twice by subprocess with `PYTHONHASHSEED=1` and `--seed 1`, then `PYTHONHASHSEED=2` and `--seed 2`
- **THEN** for each target every file under `--out` is byte-identical across the four builds

#### Scenario: Script folder unchanged
- **WHEN** the blink is built with `--confirm`
- **THEN** `examples/blink_2layer/` holds the same files with the same SHA-256 values as before, and no `__pycache__`

#### Scenario: Cache regenerated
- **GIVEN** a confirmed blink build whose `.fenolite/` folder is deleted
- **WHEN** the build runs again with `--confirm`
- **THEN** `.fenolite/` holds the same seven files with the same bytes as before

### Requirement: Built boards read back with the same connectivity
`tests/unit/lens/test_build_readback.py` SHALL read the board written by a build with c0009's `read_board`, without KiCad, and compare it with the built model.
- The nets that `read_board` synthesises MUST have the same sets of (reference, pad number) pairs as the built model's nets, pad by pad.
- Components MUST have the same `ref`, `value`, `lib_footprint_ref` and `properties`, and `Component.path` MUST be empty in both.
- Footprint positions, rotations, sides and locks MUST equal the built ones.
- Ids differ by design (`kicad` and `dsl` keys), so the comparison is by keys. RT1 of the built board is c0013's roundtrip stage; the model-to-board comparison by keys belongs to c0019 (components, positions, properties) and c0020 (pad nets).

#### Scenario: Blink reads back
- **WHEN** `uv run pytest tests/unit/lens/test_build_readback.py` runs for targets 9 and 10
- **THEN** the net `LED_A` read back holds the pairs (`R1`, `2`) and (`D1`, `2`) exactly as the built model does, every component has equal `properties`, and every `Component.path` is empty

#### Scenario: Staged parts read back
- **GIVEN** the blink with `R1` not placed
- **WHEN** the written board is read back
- **THEN** `R1` is at the staged position, on the top side, at 0° and unlocked

### Requirement: Blink examples
The repository SHALL ship a CC0 blink example built from the authored mini library for both targets, and an official-library variant that is never committed in built form.
- `tests/data/libs/Mini_v9.kicad_sym` MUST gain 9-format `Mini_R` and `Mini_LED`: copies of the 10.0 symbols with header `20241209` and every 10-only token removed, so `versions.check_emittable` for target 9 is clean. They MUST pass c0008's `tests/kicad/libs/test_mini_oracle.py` on 9.0.9 and 10.0.6, and their pins MUST equal those of the 10.0 copies.
- `examples/blink_2layer/design.py` (CC0) MUST describe `U1` `Mini:Mini_QFP32_IC`, locked on the top; `R1` `Mini:Mini_R` with `Mini:Mini_R_0603`; `D1` `Mini:Mini_LED` with `Mini:Mini_LED_THT_3mm` on the bottom; the nets `VIN`, `GND`, `LED_DRV` (a `U1` pin to `R1`) and `LED_A` (`R1` to `D1`); `Power(VIN, GND)` with `VIN` and `GND` on adjacent `U1` pins; the class `PWR` (0.2 mm clearance, 0.5 mm track) on `VIN` and `GND`; a 50 mm × 30 mm two-layer board; every part placed.
- `examples/blink_2layer/fp-lib-table` and `sym-lib-table` MUST hold rows to `${KIPRJMOD}/../../tests/data/libs/Mini_v9.*`, used for both targets.
- `examples/blink_official/design.py` MUST describe the same circuit with an MCU symbol from the official libraries, `Device:R` and `Device:LED`. It is DSL source only, built only by `tests/libs/test_build_official.py` (marker `needs_libs`) into `tmp_path`, and nothing generated from it is committed.
- Every new example and data file MUST be declared in `tests/data/MANIFEST.toml`, with rows in `PROVENANCE.md` and `LEGAL-ANNEX.md`.

#### Scenario: Mini symbols load on both majors
- **WHEN** `uv run pytest tests/kicad/libs/test_mini_oracle.py -rA` runs on 9.0.9 and on 10.0.6
- **THEN** it passes with `Mini_R` and `Mini_LED` in `Mini_v9.kicad_sym`

#### Scenario: Equal pins in both formats
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_mini_v9_pins.py` runs
- **THEN** `Mini_R` and `Mini_LED` have equal pins in `Mini.kicad_sym` and `Mini_v9.kicad_sym`

#### Scenario: Official variant where libraries exist
- **GIVEN** the official libraries found by the `needs_libs` census
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_build_official.py` runs
- **THEN** it builds `examples/blink_official/design.py` into `tmp_path` with exit 0, and `uv run pytest tests/residue/test_official_libs.py` passes

### Requirement: DSL facts are documented
The DSL, the build and the facts they rely on SHALL be documented in Fenolite's own words, with sources and evidence labels.
- `docs/dsl.md` (new) MUST cover the API, units, the key table, the frame and `BOARD_ORIGIN`, the script rules and the security note, determinism, the output layout, the edited-output rule, and stale vendored files left in `lib/` after a part is removed.
- `docs/design-model.md` MUST describe keyed DSL ids; `docs/cli-contract.md` MUST describe `build`, `FEN-3005` and refusals with issues; `docs/formats/kicad/board.md` MUST hold the path-property form and `docs/formats/kicad/libraries.md` the written tables and vendoring, as fact rows with source, label and hypothesis; `examples/README.md` MUST list both examples.
- `docs/evidence/sources.md` MUST register S-0070 (`runpy`), S-0071 (`sys`), S-0072 (`PYTHONHASHSEED`), S-0073 (floating-point `repr`) and S-0074 (`contextlib.redirect_stdout`), and `docs/hypotheses.md` MUST register `H-K-BUILD-TRIAD`, `H-K-BUILD-CLASS`, `H-K-BUILD-LIBTABLE` and `H-K-BUILD-PATHPROP`.

#### Scenario: Registers hold the new rows
- **WHEN** `grep -c '^| H-K-BUILD-' docs/hypotheses.md` and `grep -c '^| S-007[0-4] ' docs/evidence/sources.md` run
- **THEN** they print `4` and `5`

#### Scenario: Fact tables are labelled
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes, and every new row of `board.md` and `libraries.md` has a source id and a valid label, with a hypothesis when below `KICAD-VERIFIED`

#### Scenario: Help warns about untrusted scripts
- **WHEN** `fenolite build --help` runs
- **THEN** the text says that `build` executes `design.py` and must not be run on an untrusted script

### Requirement: User properties in the DSL
`Part(ref, lib_id, footprint=None, value="", *, properties=None)` SHALL record user properties of a part, such as a part number or a supplier code, as text, and SHALL raise `DslError` at the call for every property it cannot record unambiguously.
- `properties` MUST be `None` (no property) or a mapping whose keys and values are `str`. Any other type, or a key or value that is not a `str`, MUST raise `DslError` naming the part.
- A name MUST be non-empty, MUST have no leading or trailing whitespace, and MUST satisfy `str.isprintable()` (S-0105). A value MUST satisfy `str.isprintable()` and MAY be empty. A tab, a newline or another control character is therefore refused.
- A name MUST NOT equal a reserved name (`Reference`, `Value`, `Footprint`, `Datasheet`, `Description`) and MUST NOT start with a reserved prefix (`fenolite.`, `ki_`). Both are compared after `str.casefold()` (S-0105). `Reference` and `Value` come from `ref` and `value`, the other three names are fields of the footprint library, `fenolite.path` is the component path, and `ki_` names are KiCad's own. The sets are `fenolite.dsl.part.RESERVED_PROPERTIES` and `RESERVED_PREFIXES`, are not re-exported, and MUST equal those of `lens.build`.
- Two names of one part that are equal after `str.casefold()` MUST raise `DslError` naming both.
- `Part.properties` MUST be a read-only mapping whose keys are in code-point order, whatever the order of the script.
- The DSL MUST NOT compare names with the properties of a footprint library; the build does ("User properties on built footprints").

#### Scenario: Properties recorded in name order
- **GIVEN** `r1 = Part("R1", "Mini:Mini_R", properties={"Supplier code": "S-1", "Part number": "PN-330"})`
- **WHEN** `r1.properties` is read, and then `r1.properties["X"] = "y"` is attempted
- **THEN** the mapping equals `{"Part number": "PN-330", "Supplier code": "S-1"}` with its keys in this order, and the assignment raises `TypeError`

#### Scenario: Reserved names in any letter case
- **WHEN** `Part("R1", "Mini:Mini_R", properties={"datasheet": "x"})` and `Part("R2", "Mini:Mini_R", properties={"KI_keywords": "x"})` are called
- **THEN** each call raises `DslError`, the first naming `datasheet` and `Datasheet`, the second naming the prefix `ki_`

#### Scenario: The path property is not the script's
- **WHEN** `Part("R1", "Mini:Mini_R", properties={"fenolite.path": "R9"})` is called
- **THEN** `DslError` is raised naming the prefix `fenolite.`

#### Scenario: Values are printable text
- **WHEN** `Part("R1", "Mini:Mini_R", properties={"Qty": 2})` and `Part("R2", "Mini:Mini_R", properties={"Part number": "A\nB"})` are called
- **THEN** each call raises `DslError` naming the property

#### Scenario: Names that differ only in case
- **WHEN** `Part("R1", "Mini:Mini_R", properties={"MPN": "a", "mpn": "b"})` is called
- **THEN** `DslError` is raised naming `MPN` and `mpn`

#### Scenario: Reserved sets agree
- **WHEN** `uv run pytest tests/unit/dsl/test_properties.py -k reserved_sets` runs
- **THEN** `fenolite.dsl.part.RESERVED_PROPERTIES` and `RESERVED_PREFIXES` equal `fenolite.lens.build.RESERVED_PROPERTIES` and `RESERVED_PREFIXES`

### Requirement: User properties on built footprints
The build SHALL write every user property of a component onto its placed footprint through `embed.with_property`, and SHALL refuse, with an issue and no file, a user property that it cannot write unambiguously.
- The user properties of a component are the entries of `Component.properties` other than `fenolite.path`, which carries the component path ("DSL to model").
- **Checks.** They run with the build checks of "Built project files", and each issue names the component path in `where`:
  - a name equal to a reserved name, or starting with a reserved prefix, after `str.casefold()` (`lens.build.RESERVED_PROPERTIES` and `RESERVED_PREFIXES`, the sets of "User properties in the DSL"): `build.property-reserved` (error);
  - an empty name, a name with leading or trailing whitespace, a name or value that fails `str.isprintable()`, or two names equal after `str.casefold()`: `build.property-invalid` (error);
  - a name equal, after `str.casefold()`, to the name of a property of the resolved footprint definition: when both the name and the value are identical, nothing is appended and the definition's property stands; otherwise `build.property-conflict` (error) naming the property and the library's value.
- **Form and order.** Each user property MUST be appended by one call `embed.with_property(<definition>, name=<name>, value=<value>)`, in code-point order of names, after the path property; when `H-K-BUILD-PATHPROP` is refuted and no path property is written, after the definition's last property. Each is therefore hidden, on `F.Fab` at `(at 0 0 0)` with c0011's font, and `place_footprint` puts it on `B.Fab` with a mirrored text for a bottom part. Values are written with the string escapes of the s-expression writer (`H-K-SEXPR-ESCAPES`).
- Adding or removing a user property MUST NOT change the uuid of any node other than the user properties that come after it, because new nodes are appended after the existing ones and locator indices count earlier siblings with the same head (`kicad-sexpr`).
- **Model.** `Component.properties` MUST equal what `read_board` projects from the written footprint: the definition's properties, `fenolite.path`, the user properties, `Reference` and `Value`. c0017's "Projected fields on write" stays unchanged and passes, because every property of the model is a fragment of the footprint.
- **Readback.** `read_board` of the written board MUST give every user property with its value, for targets 9 and 10.
- Visibility, position, layer and size of these properties cannot be set by this change (field placement, c0030).

#### Scenario: Written after the path property
- **GIVEN** a blink variant whose `R1` has `properties={"Supplier code": "S-1 \"q\" \\ µ", "Part number": "PN-330"}`
- **WHEN** it is built for target 10 and the board text is parsed
- **THEN** the last three `property` nodes of `R1`'s footprint are `fenolite.path`, `Part number` and `Supplier code`, in this order, each on layer `F.Fab` with `(hide yes)`, and `read_board` gives `properties["Supplier code"] == "S-1 \"q\" \\ µ"` and `properties["Part number"] == "PN-330"`

#### Scenario: Bottom part
- **GIVEN** the blink, whose `D1` is on the bottom side, with `properties={"Part number": "PN-LED"}` on `D1`
- **WHEN** it is built for target 9
- **THEN** the `Part number` node of `D1` has layer `B.Fab`, `(hide yes)` and `mirror` in its `justify`

#### Scenario: Writer accepts the properties and reads them back
- **WHEN** the variant with properties on `R1` and `D1` is built for targets 9 and 10, and each written board is read with `read_board`
- **THEN** `write_triad` raises no `kicad.board.projection-read-only`, and each built component's `properties` equals the read-back component's `properties`

#### Scenario: No other uuid moves
- **GIVEN** the blink built once as it is and once with `properties={"Part number": "PN-330"}` on `R1`
- **WHEN** the uuids of the two boards are compared
- **THEN** they are equal, except the uuid of the new `Part number` node, which only the second board has

#### Scenario: Reserved name through the model
- **GIVEN** `to_model` of the blink, with `"Datasheet": "x"` added to the `properties` of `R1` in the test
- **WHEN** `build_design` runs
- **THEN** `files` is empty, and `issues` holds `build.property-reserved` whose `where` is `R1`

#### Scenario: Library property with the same name
- **GIVEN** a footprint authored in the test whose properties include `Part number` with value `LIB`, used by `R1`
- **WHEN** it is built with `R1` given `properties={"Part number": "PN-330"}`, and again with `properties={"Part number": "LIB"}`
- **THEN** the first build gives `build.property-conflict` naming `Part number` and `LIB` with no file, and the second build writes the footprint with exactly one `Part number` node

#### Scenario: Control character through the model
- **GIVEN** `to_model` of the blink, with `"Part number": "A\tB"` added to the `properties` of `R1` in the test
- **WHEN** `build_design` runs
- **THEN** `files` is empty, and `issues` holds `build.property-invalid` naming `R1`

### Requirement: Footprints of every row origin are vendored
With `vendor="all"`, the default of `build_design` and of `fenolite build`, the build SHALL copy every footprint it places into the project's library folder, whatever the origin of the row that resolved it, so that a built project needs no global or template table.
- Row origins are those of `LibraryResolver`: `project`, `global` and `template`, and any origin that a later change adds, such as c0021's `scan`. A footprint of any origin MUST be copied byte for byte from `Location.item_path` to `lib/<nickname>.pretty/<entry>.kicad_mod`, `nickname` being the nickname of the row that resolved it, with one `fp-lib-table` row per vendored nickname ("Built project files").
- Lib ids MUST stay unchanged: the board's footprint names, `Component.lib_footprint_ref` and the `.fenolite/` texts keep the nicknames of the design. In KiCad's library check, the vendored row hides a global row with the same nickname, and with it the items that were not vendored (`H-K-VENDOR-SHADOW`).
- Only placed footprints MUST be copied: no whole library, no 3D model, no symbol and no `sym-lib-table`. Symbol libraries get the same rule when built projects get schematics (v0.2a).
- With `vendor="project"` (`fenolite build --vendor project`), a footprint of a row whose origin is not `project` MUST NOT be copied and gets no row. Each such footprint gives `build.global-library` (info), as c0011 did.
- **Unsafe names.** A vendored nickname that holds `/` or `\`, or a character that fails `str.isprintable()`, MUST give `build.vendor-unsafe-name` (error) with the build checks, and two vendored paths that differ but are equal after `str.casefold()` MUST give it too. Then no file is written outside `lib/`, and the folder survives a file system that ignores letter case.
- **Library changes.** When `record` (the hashes that `read_record` returns) holds a hash for the path of a vendored file, and the planned bytes have another SHA-256, the build MUST give `build.library-changed` (warning) naming the file, because its library changed since the last build. The planned copy still replaces an old copy that is untouched since the last build ("Edited outputs are not overwritten").
- Vendored bytes are the source bytes, so two builds with the same libraries give identical files ("Reproducible builds").
- Copies are written only into the `--out` folder. The official libraries are CC-BY-SA 4.0 with an exception for designs, and redistributing the collection is not covered by it (S-0048). `docs/dsl.md` MUST say so without legal advice, and MUST name `--vendor project`.

#### Scenario: Global footprints vendored
- **GIVEN** the blink built from a folder without project tables, every symbol and footprint served by the global tables of a `KICAD_CONFIG_HOME` authored in the test, whose rows `Mini` name a temporary copy of `tests/data/libs/Mini_v9.pretty` and `Mini_v9.kicad_sym`
- **WHEN** `build_design` runs for target 9, and again for target 10
- **THEN** each `files` holds the three footprints under `lib/Mini.pretty/`, byte-equal to the copy, and an `fp-lib-table` with the one row `Mini` naming `${KIPRJMOD}/lib/Mini.pretty`; `issues` holds no `build.global-library`; `summary["libraries"]["Mini:Mini_R_0603"]` is `global`; and the board names the footprint `Mini:Mini_R_0603`

#### Scenario: Template footprints vendored
- **GIVEN** a fake install made with `tests/_libs.make_install`, whose template tables name the same copies through `${KICAD10_FOOTPRINT_DIR}` and `${KICAD10_SYMBOL_DIR}`, and an empty configuration folder
- **WHEN** the blink is built for target 10 from a folder without project tables
- **THEN** `summary["libraries"]["Mini:Mini_R_0603"]` is `template`, and the files under `lib/Mini.pretty/` and the table are those of the previous scenario

#### Scenario: Vendoring kept to project rows on request
- **GIVEN** the global setup of the first scenario
- **WHEN** `build_design` runs with `vendor="project"`
- **THEN** `files` holds nothing under `lib/`, `fp-lib-table` holds no row, and `issues` holds three `build.global-library` infos, one for each footprint

#### Scenario: Unsafe nickname
- **GIVEN** a global row named `a/b`, made in the test, that serves `R1`'s footprint
- **WHEN** `build_design` runs
- **THEN** `files` is empty, and `issues` holds `build.vendor-unsafe-name` naming `a/b`

#### Scenario: Library changed since the last build
- **GIVEN** a first build of the global setup and the hashes of its `.fenolite/build.json`, and then pad `1` of the global copy of `Mini_R_0603.kicad_mod` moved 0.05 mm in the test
- **WHEN** `build_design` runs again with `record` set to those hashes
- **THEN** `issues` holds one `build.library-changed` warning naming `lib/Mini.pretty/Mini_R_0603.kicad_mod`, and the planned copy is byte-equal to the changed source; without the change, no such warning is given

#### Scenario: Built folder resolves alone
- **GIVEN** a build of the global setup, written to a folder and copied to another folder
- **WHEN** a resolver with `project_dir` set to the copy, an empty configuration folder and no install locates `Mini:Mini_R_0603`
- **THEN** the origin is `project`, and the item path is `lib/Mini.pretty/Mini_R_0603.kicad_mod` inside the copy

