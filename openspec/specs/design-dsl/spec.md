# design-dsl Specification

## Purpose
Specify the stdlib-only Python DSL that describes a design (parts, nets, net classes, interfaces, outline and placements, with unit-carrying lengths and ids keyed by names and paths) and the `fenolite build` command that turns a design script into a self-contained, reproducible KiCad project.
## Requirements
### Requirement: DSL package
The package `fenolite.dsl` SHALL provide a thin, stdlib-only API to describe a design in Python, and MUST import only `core` and `model` (`package-layering`).
- Modules: `design.py` (`Design`, `Rules`), `module.py` (`Module`), `part.py` (`Part`, `PinHandle`, `Net`, `connect`, `Placement`), `interfaces.py` (`Interface`, `Power`, `DiffPair`), `units.py` (`Length`, `mm`, `mil`, `inch`, `nm`), `convert.py` (`to_model`, `placements`, `moves`, `KEYS`, `BOARD_ORIGIN`), `errors.py` (`DslError(ValueError)`) and `_minimal.py`, a packaged hermetic example.
- `fenolite.dsl` MUST re-export `Design`, `Module`, `Part`, `Net`, `connect`, `Interface`, `Power`, `DiffPair`, `Length`, `mm`, `mil`, `inch`, `nm`, `Placement`, `BOARD_ORIGIN`, `to_model`, `placements`, `moves`, `KEYS`, `DSL_BACKEND` (`"dsl"`) and `DslError`.
- Later requirements MAY add modules and re-exported names, which keep the import rule above; each such requirement names this one.
- The root package `fenolite` MUST re-export neither the DSL `Design` nor the model `Design`. Inside `dsl`, the model class MUST be imported as `ModelDesign`.
- Objects MUST join a design only through `add()`. There is no hidden global or "current design" state.
- The DSL MUST store lib ids as strings only. It MUST NOT read a library, a file or the environment, and MUST NOT import a backend.
- There are no part classes, no part picker, no solver and no custom-rule constructor. `Design.moved(old, new)` records a path alias for layout preservation ("Path aliases in the DSL").

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

#### Scenario: Aliases exported
- **WHEN** `python -c "from fenolite.dsl import moves; print(moves.__module__)"` runs
- **THEN** it prints `fenolite.dsl.convert`

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
`Design.board(width, height, copper=2, planes=None)` SHALL declare a rectangular board, its copper layer count and its internal planes, and `Part.place(x, y, rot=0, side="top", locked=False)` SHALL request a placement, both in a board-relative frame.
- The frame has its origin at the top-left corner of the outline, with Y down. `BOARD_ORIGIN` MUST be `Point(100_000_000, 100_000_000)`, a Fenolite choice: the outline is written from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)`, and a part placed at `(x, y)` is written at `BOARD_ORIGIN + (x, y)`.
- `width` and `height` MUST be positive lengths. `copper` MUST be 2 or 4.
- An inner copper layer is a signal layer unless `planes` names it. `planes` MUST be `None` or a mapping from an inner layer name (`"In1.Cu"`, `"In2.Cu"`) to a `Net` or a net name: that layer is an internal plane on that net. `DslError` MUST be raised at the call for `planes` with `copper=2`, a key that is not an inner layer name, and a value that is neither a `Net` nor a valid net name. A plane holds one net; split planes cannot be declared.
- `Design.planes` MUST hold the mapping from layer name to net name, in layer order, empty by default. `planes(design) -> Mapping[str, str]` (`dsl/convert.py`, re-exported by `fenolite.dsl` as "DSL package" allows) MUST return it and MUST raise `DslError` naming a net that the design does not hold.
- A plane is a build parameter, as `copper` is: `to_model` MUST NOT change, the model gets no plane entity, and a plane layer stays a layer of kind `copper`. What a target does with a plane is its build's rule ("Planes in a build").
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

#### Scenario: Ground plane declared
- **GIVEN** `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})`, where `gnd` is the net `GND` of the design
- **WHEN** `planes(design)` is read
- **THEN** it equals `{"In1.Cu": "GND"}`, and `to_model(design)` equals the model of the same script without `planes`

#### Scenario: Malformed planes fail at the call
- **WHEN** `design.board(mm(50), mm(30), planes={"In1.Cu": gnd})`, `design.board(mm(50), mm(30), copper=4, planes={"F.Cu": gnd})` and `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": 3})` are called on fresh designs
- **THEN** each raises `DslError`, the second naming `F.Cu`

#### Scenario: Plane on a net that is not in the design
- **GIVEN** `design.board(mm(50), mm(30), copper=4, planes={"In2.Cu": "NOPE"})` and no net `NOPE`
- **WHEN** `planes(design)` is called
- **THEN** `DslError` is raised naming `NOPE`

### Requirement: Net classes in the DSL
`design.rules.netclass(name, *, clearance=None, track_width=None, via_diameter=None, via_drill=None, nets=())` SHALL declare one net class whose values are lengths and whose members are the given `Net` objects.
- Each given net joins the design and gets `Net.netclass_id` of that class in the model.
- A class name used twice, or a net given to two classes, MUST raise `DslError`.
- A net class adds no rule to the model `RuleSet`. The only rule constructor is `design.rules.minimum` ("Rule minimums in the DSL"); without a call to it the `RuleSet` of a DSL design is empty, and the build lowers it through c0018 to `(version 1)`.

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
- Interfaces are not lowered to KiCad. A build MUST give one `build.interface-not-lowered` info per `diff_pair` and per `usb2` interface ("Typed interfaces in the DSL"), and the nets of each such pair MUST pass the name check of "Interface checks in a build".

#### Scenario: Power interface
- **GIVEN** `Power(vin, gnd)` added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `VIN/GND` with kind `power` and members `hv` and `lv` equal to the ids of `VIN` and `GND`

#### Scenario: Diff pair reported
- **GIVEN** a blink variant holding `DiffPair(usb_p, usb_n)` on nets `USB_P` and `USB_N`
- **WHEN** it is built with `--dry-run`
- **THEN** `issues` holds one info `build.interface-not-lowered` naming `USB_P/USB_N`

#### Scenario: Diff pair names checked
- **GIVEN** a blink variant holding `DiffPair(clk_p, clk_n)` on nets `CLK_P` and `CLKN`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one info `build.interface-not-lowered` naming `CLK_P/CLKN` and one warning `build.diff-pair-name` naming both nets

### Requirement: DSL to model
`dsl.to_model(design) -> fenolite.model.Design` SHALL convert a DSL design into model types only, with the ids of `design-model` "Identifier derivation" (fourth case).
- **Circuit.** One `Component` per added part, with `ref`, `value`, `lib_symbol_ref`, `lib_footprint_ref` (empty when `Part.footprint` is `None`), empty `pins`, empty `path` and `properties` holding `"fenolite.path"` mapped to the component path and every entry of `Part.properties` ("User properties in the DSL"), keys in code-point order. Nets whose `PinRef.pin` holds the designator as written. Net classes with `Net.netclass_id`. Interfaces. One `Module` per DSL module, with `path`, `parent` and `component_ids`.
- **Board.** A keyed `Board` without layers and footprints, whose `Outline` is the rectangle from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)` in the order of c0017's "Outline lowering", or no outline when `board()` was not called.
- **Other layers.** A keyed `RuleSet` holding the rules of "Rule minimums in the DSL" (empty without a `minimum()` call), a keyed `Manifest` and a keyed header named after the design.
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
`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project]` (`src/fenolite/cli/cmd_build.py`, schema `fenolite.build.v0`) SHALL be a mutating command that runs the script, converts it with `to_model`, `placements` and `moves`, prepares layout preservation with `lens.preserve.read_existing` and `lens.preserve.prepare` unless `--discard-layout` is given, builds it with `lens.build.build_design` for `Context.kicad_target` and the `--vendor` policy, and returns every output file as a planned write under `DIR`.
- It MUST accept the global flags `--dry-run`, `--confirm`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version 9|10` and `--allow-lossy`. `--out` is required. `--discard-layout` and `--vendor` (choices `all` and `project`, default `all`, passed to `build_design` as `vendor`) are `build` options. The help text of `--vendor` MUST say that `all` copies the placed footprints of every library into `DIR/lib/` and that the copies keep their library's licence.
- An `--out` folder that resolves to the script folder MUST be a usage error (exit 2, `FEN-2001`), so the design's own tables are never overwritten.
- `input` MUST hold the script path and its SHA-256, with kind `fenolite-dsl`.
- The triad stem MUST be the design name, and plan entries MUST be sorted by path.
- `result` MUST hold `design` (the name), `target`, `out`, `files` (the planned paths), `components` and `nets` (counts), `placed` and `staged` (component paths), `vendored` (vendored footprint files), `libraries` (lib id to row origin `project`, `global`, `template` or `scan`), `script_output` and `preserved` (`layout-lens`, "Layout preservation evidence"), plus the dispatcher's `plan`.
- Later requirements MAY add `build` options, steps of `cmd_build` and keys of `result`; each such requirement names this one.
- `cmd_build` MUST turn a `DslError` raised by `to_model`, `placements` or `moves`, which run after `run_design_script` has returned, into `DesignScriptError` with `file` = the script path and no locator (`FEN-3004`, exit 3).
- Unless `--discard-layout` is given, `cmd_build` MUST read the existing triad with `read_existing(DIR, <design name>)`, call `prepare(model, placements(design), existing, name=<design name>, moves=moves(design))`, and pass `prepared.placements` as `placements` and `prepared` as `prepared` to `build_design`. With `--discard-layout`, it MUST pass `placements(design)` and no `prepared`.
- `cmd_build` MUST read the last build record once with `lens.build.read_record(DIR)`, pass it to `build_design` and to `lens.build.check_existing` as `record`, and call `check_existing` before it returns the plan, with every planned file except the board, project and rules files, which preservation merges ("Edited outputs are not overwritten").
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

#### Scenario: Rebuild over an edited board
- **GIVEN** a confirmed target-10 blink build in `B` whose board was replaced by `tests/_layout_edit.py::edit_blink` of its text
- **WHEN** the build runs again with `--confirm --json`
- **THEN** the exit code is 0, `result.preserved.board` is `true`, and `result.preserved.kept` lists `D1`, `R1` and `U1`

### Requirement: Library resolution during build
The build SHALL resolve every `lib_symbol_ref` and `lib_footprint_ref` through one c0008 `LibraryResolver(LibraryConfig(target_major=ctx.kicad_target, project_dir=<script folder>))`, built with the process environment and the user's configuration folder. A `cache` source is used only when `FENOLITE_LIBS_CACHE` names one: the build passes no `cache_dir`, and no default cache location is searched (`kicad-library-resolution`, "Library sources").
- Project tables next to `design.py` are the recommended source. Global and template tables follow c0008. Official library variables come only from an `env`, `cache` or `install` source of the target major, in that order, so a 10.0 install is never used for target 9 (`kicad-library-resolution`, "Library sources").
- Every `LibraryError` MUST be collected. If there is at least one, `lens.build.UnresolvedLibrariesError(LibraryError)` (`FEN-3001`) MUST be raised with the first error's hint and one `kicad.lib.*` issue per failure in `issues`.
- `Part.footprint=None` MUST fall back to the symbol's `Footprint` property. When both are empty, the build MUST give `build.no-footprint` (error).
- `value=""` MUST fall back to the symbol's `Value` property.
- A row of origin `scan` (`kicad-library-resolution`, "Table discovery and precedence") MUST be handled by every build rule like any row whose origin is not `project`: its footprints are vendored ("Footprints of every row origin are vendored"), or give `build.global-library` with `vendor="project"`.
- `result.libraries` MUST map each lib id to the origin of its row: `project`, `global`, `template` or `scan`.

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

#### Scenario: Footprint from a scanned cache
- **GIVEN** a blink variant whose `R1` footprint is `Cached:Mini_R_0603`, a folder `C` whose `10.0.6/kicad-footprints/` holds `Cached.pretty`, a copy of `tests/data/libs/Mini.pretty`, and a stamp equal to the 10.0.6 footprint pin, an empty configuration folder and an install path that does not exist
- **WHEN** it is built for target 10 through `tests/_buildhelp.py` with `cache_dir=C`, a keyword that this change adds and that also turns on `use_global_table`
- **THEN** `summary["libraries"]["Cached:Mini_R_0603"]` is `scan`, `files` holds `lib/Cached.pretty/Mini_R_0603.kicad_mod` byte-equal to its source, and `fp-lib-table` holds a row `Cached`

#### Scenario: Official variant from the cache
- **GIVEN** a verified 10.0.6 cache at `tests/_resources.libs_cache_dir()` and no other library source
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_build_official.py` runs
- **THEN** the test sets `FENOLITE_LIBS_CACHE` to that folder for the build, the build exits 0, and `result.libraries["Device:R"]` is `scan`

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
`lens.build.build_design(design, placements, *, name, copper, resolver, target=DEFAULT_TARGET, allow_lossy=False, vendor="all", record=None, prepared=None) -> BuildOutput` SHALL return every file of a self-contained KiCad project as bytes, and SHALL return no file when any issue has severity `error`.
- The steps MUST run in this order: resolve libraries; fill pins and resolve net members; place, stage, set layers and assign pad nets; run the build checks (those of "Pins and pads in a build", "Placement of built parts", "User properties on built footprints" and "Footprints of every row origin are vendored") and `Design.validate()`; when `prepared` holds an existing board, merge it with `lens.preserve.merge_layout` and run `Design.validate()` on the merged layout; call c0010's `triad.write_triad(<model>, name=name, target=target, existing_project=<the existing project text of prepared, or None>, allow_lossy=allow_lossy, issues=…)`, which lowers rules through c0018 and net classes through c0010, `<model>` being the merged layout when there is an existing board and the built design otherwise; merge the rules text with `lens.preserve.merge_rules` when `prepared` holds an existing rules text; with an existing board, drop the fills whose digests changed with `lens.preserve.drop_stale_fills` and, when one was dropped, write the board again with `write_board`; derive `BuildOutput.layout` from the written board text (`layout-lens`, "Preservation is the build's normal form"); add the vendored footprints, `fp-lib-table`, the `.fenolite/` texts and `.fenolite/build.json`; combine evidence.
- Later requirements MAY add keyword-only arguments with defaults to `build_design`, and steps between or within the steps above; each such requirement names this one.
- An issue of severity `error` before the writer MUST return a `BuildOutput` with its issues and empty `files`. Writer refusals (`LossyWriteError`, `RulesLossError`, `FEN-7001`) MUST propagate with their issues.
- `BuildOutput` is a frozen dataclass with `design`, `files: Mapping[str, bytes]` (paths relative to `--out`), `issues`, `evidence`, `summary` and `layout: Design | None`. `design` is the model built from the script at the given placements; `layout` is the model of the written board, and `None` when no file is returned.
- The layout MUST be `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, `fp-lib-table`, `lib/<nickname>.pretty/<entry>.kicad_mod`, the six layer files under `.fenolite/` and `.fenolite/build.json`.
- Every vendored footprint MUST be copied byte for byte from `Location.item_path` to `lib/<nickname>.pretty/<entry>.kicad_mod`, and `fp-lib-table` MUST hold one row per vendored nickname with `uri "${KIPRJMOD}/lib/<nickname>.pretty"`, written by `libs.write_lib_table` for the target. With `vendor="all"`, every footprint that the build places is vendored, whatever the origin of its row; with `vendor="project"`, only footprints resolved through a project-table row are ("Footprints of every row origin are vendored"). Any other `vendor` MUST raise `ValueError`.
- With `vendor="project"`, footprints from rows of another origin MUST NOT be vendored and get no row (`build.global-library`, info). A vendored file whose header version is newer than the target's newest format MUST give `build.library-too-new` (warning). With `record`, a vendored file whose bytes differ from the hash recorded for its path MUST give `build.library-changed` (warning).
- The build MUST NOT write a `sym-lib-table`, a symbol file, a `.kicad_prl`, a `native/` folder or a date.
- The `.fenolite/` layer texts MUST come from `canonical.dump_texts` of `BuildOutput.layout`, with an empty `findings.json` and no `FootprintDef`. `.fenolite/build.json` MUST have `schema` `fenolite.build-record.v0`, sorted keys and no date, and MUST record the SHA-256 of every file outside `.fenolite/` that the build writes. It is regenerable and marks a built project.

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

#### Scenario: Cache texts come from the layout
- **WHEN** `build_design` runs for the blink without `prepared`
- **THEN** `output.layout` is not `None`, and the six `.fenolite/` texts in `files` equal `canonical.dump_texts(output.layout)`

#### Scenario: Existing project text is merged
- **GIVEN** a `prepared` whose existing project text holds a net class `USER` that the design lacks
- **WHEN** `build_design` runs
- **THEN** the planned `blink.kicad_pro` holds the classes `PWR` and `USER`

### Requirement: Edited outputs are not overwritten
`lens.build.check_existing(out_dir, files, *, record, discard_layout) -> None` SHALL refuse to replace a file outside `.fenolite/` that changed since Fenolite last wrote it, except the board, project and rules files of the triad, which layout preservation merges instead (`layout-lens`). For each other planned file outside `.fenolite/` that already exists, that is `fp-lib-table` and the vendored footprints under `lib/`:
- bytes equal to the planned bytes: an identical rewrite, allowed;
- SHA-256 equal to the one recorded in `.fenolite/build.json`: untouched since the last build, allowed, so a DSL edit never needs `--discard-layout`;
- otherwise (edited, or found without a record): `LayoutExistsError` MUST be raised, with `cli_code = "FEN-7001"` (exit 7), one `build.layout-exists` issue per file, and the hint "re-run with --discard-layout to replace them (backups are kept), or build into another --out folder".

Further rules:
- `cmd_build` MUST NOT pass the board, project and rules files to the check.
- The check MUST run before the plan is returned, so `--dry-run` refuses too, and nothing is written.
- `--discard-layout` MUST skip the check, and the build then preserves nothing (`layout-lens`, "Existing project files"); the mutation protocol keeps a `.bak` of each replaced file unless `--no-backup` is given. `--allow-lossy` MUST NOT skip the check.
- Without a record (for example after `.fenolite/` was deleted), only identical bytes are allowed.

#### Scenario: DSL edit needs no flag
- **GIVEN** a confirmed blink build in `B`
- **WHEN** the value of `R1` is changed in `design.py` and the build runs again with `--confirm`
- **THEN** the exit code is 0, and `B/blink.kicad_pcb` holds the new value

#### Scenario: Edited board is merged, not refused
- **GIVEN** a confirmed blink build in `B` whose board gets one segment by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the segment is kept, and `issues` holds no `build.layout-exists`

#### Scenario: Edited vendored footprint refused
- **GIVEN** a confirmed blink build in `B` and one byte of `B/lib/Mini.pretty/Mini_R_0603.kicad_mod` changed afterwards
- **WHEN** the build runs again with `--confirm`, and then with `--dry-run`
- **THEN** both exit 7 with `FEN-7001`, the envelope's `issues` holds `build.layout-exists` naming `B/lib/Mini.pretty/Mini_R_0603.kicad_mod`, and no file under `B` changes

#### Scenario: Discarding the layout
- **GIVEN** the same edited footprint file
- **WHEN** the build runs with `--discard-layout --confirm`
- **THEN** the exit code is 0, and `B/lib/Mini.pretty/Mini_R_0603.kicad_mod.bak` holds the edited bytes

#### Scenario: Lost record
- **GIVEN** two copies of a confirmed blink build, each with its `.fenolite/` folder deleted
- **WHEN** the build runs again with `--confirm` into the first copy unchanged, and into the second copy after one byte of its `fp-lib-table` is changed
- **THEN** the first run exits 0 with identical bytes, and the second exits 7 with `build.layout-exists` naming `fp-lib-table`

#### Scenario: Lossy flag does not skip the check
- **GIVEN** the edited footprint file
- **WHEN** the build runs with `--allow-lossy --confirm`
- **THEN** the exit code is 7 with `build.layout-exists`

### Requirement: Build issue codes
The build SHALL report its own findings only with the codes of the closed table `lens.build.BUILD_ISSUE_CODES`, which MUST also hold every row of `lens.preserve.PRESERVE_ISSUE_CODES` (`layout-lens`, "Layout issue codes"). Every `kicad.*` code, such as those of the writers (`kicad.board.*`, `kicad.project.*`) and of the readers and the resolver (`kicad.board.*`, `kicad.version.*`, `kicad.lib.*`), the writers' `rules.*` codes and the codes of `Design.validate()` (`model.*`) MUST pass through unchanged. Later requirements MAY add codes that join the `build` envelope unchanged, from steps they add to the build or to `cmd_build`; each such requirement names this one.

| code | severity | when |
|---|---|---|
| `build.unknown-pin` | error | a designator is neither a pin number nor a pin name |
| `build.pin-on-two-nets` | error | a resolved pin is on two nets |
| `build.pin-without-pad` | error | a connected pin has no pad of its number |
| `build.no-footprint` | error | neither the part nor the symbol names a footprint |
| `build.no-board` | error | the design has no `board()` |
| `build.name-case-collision` | error | net or class names differ only in letter case |
| `build.layout-exists` | error | `fp-lib-table` or a vendored footprint changed since the last build (carried by `LayoutExistsError`) |
| `build.property-reserved` | error | a user property has a reserved name or prefix |
| `build.property-invalid` | error | a user property name or value is not printable text, a name has surrounding whitespace, or two names differ only in letter case |
| `build.property-conflict` | error | the footprint definition holds a property of the same name with another value |
| `build.vendor-unsafe-name` | error | a vendored nickname holds a path separator or a non-printable character, or two vendored paths differ only in letter case |
| `build.pin-ambiguous` | warning | a pin number is also another pin's name |
| `build.unused-pin-without-pad` | warning | an unconnected pin has no pad of its number |
| `build.library-too-new` | warning | a vendored file is newer than the target's newest format |
| `build.library-changed` | warning | a vendored file differs from the copy that the last build recorded |
| `layout.unplaced` | warning | a part was staged beside the outline, its footprint being new or off the board |
| `build.pad-without-pin` | info | a numbered pad has no pin of its number |
| `build.global-library` | info | with `vendor="project"`, a footprint came from a row whose origin is not `project` and is not vendored |
| `build.interface-not-lowered` | info | a `diff_pair` interface is kept in the model only |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_build_issues.py -k closed_set` collects every issue code produced by the build tests
- **THEN** each code other than `kicad.*`, `rules.*`, `model.*` and the codes that later requirements add under this requirement is a key of `BUILD_ISSUE_CODES` with the severity of this table or of `PRESERVE_ISSUE_CODES`, and every key of this table is produced by at least one test

#### Scenario: Warnings do not fail
- **GIVEN** the blink with `R1` not placed
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 0 and `issues` holds one `layout.unplaced` warning naming `R1`

#### Scenario: Preservation codes are build codes
- **WHEN** `PRESERVE_ISSUE_CODES` is compared with `BUILD_ISSUE_CODES`
- **THEN** every key of the first is a key of the second with the same severity

### Requirement: Build evidence
The `build` envelope SHALL carry `Evidence.combine` (lowest wins) of `lens.build.BUILD_EVIDENCE` (`INFERRED`; `H-K-BUILD-TRIAD`, `H-K-BUILD-CLASS`, `H-K-BUILD-LIBTABLE`, `H-K-BUILD-PATHPROP`), `sym.EVIDENCE` and `mod.EVIDENCE` (`H-K-LIB-READ`), `pcb.WRITE_EVIDENCE` (`H-K-PCB-WRITE`), `pro.EVIDENCE` (`H-K-PRO-PATTERNS`), `lowering.EVIDENCE`, when a part is on the bottom side `embed.EVIDENCE`, when a user property is written `lens.build.PROPERTY_EVIDENCE` (`INFERRED`; `H-K-VENDOR-PROPS`, `H-K-VENDOR-DUPNAME`), when a footprint of a row whose origin is not `project` is vendored `lens.build.VENDOR_EVIDENCE` (`INFERRED`; `H-K-VENDOR-GLOBAL`, `H-K-VENDOR-SHADOW`), when an existing board was read `lens.preserve.EVIDENCE` and `pcb.EVIDENCE` (`H-K-PCB-READ`), and when an existing rules text was merged `dru.EVIDENCE`.
- The level MUST stay `INFERRED` while any of these is below `KICAD-VERIFIED`.
- `PROPERTY_EVIDENCE` and `VENDOR_EVIDENCE` MUST stay `INFERRED` after their rows are settled, because the oracle covers the blink and its variants, not every design.
- Later requirements MAY add evidence that joins the envelope only when their feature is used; each such requirement names this one.
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

#### Scenario: An existing board adds the preservation rows
- **GIVEN** a confirmed blink build in `B`
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** `evidence.hypotheses` contains `H-K-LENS-KEEP` and `H-K-PCB-READ`, and `evidence.level` is `INFERRED`

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

### Requirement: Path aliases in the DSL
`Design.moved(old, new)` SHALL record that the part or module at path `new` was at path `old` in an earlier build. `dsl.moves(design) -> Mapping[str, str]` SHALL return the part aliases, new component path to old component path, in path order, with every module alias expanded, and `dsl.module_moves(design) -> Mapping[str, str]` SHALL return the module aliases, new module path to old module path, in path order; `fenolite.dsl` SHALL re-export `module_moves` (an addition under "DSL package").
- `old` and `new` MUST be paths: segments matching `[A-Za-z0-9_.+-]+` joined by `/` ("Design structure and names"). A malformed path, `old == new`, or a second alias with the same `old` or the same `new` MUST raise `DslError` at the call.
- An alias whose `new` is the path of a part added to the design is a part alias. One whose `new` is the path of a module added to the design is a module alias: it gives every part path `<new>/<rest>` of the design the alias `<old>/<rest>`. A part alias MUST win over a module alias for its part, and a longer module path over a shorter one.
- `moves(design)` and `module_moves(design)` MUST raise `DslError` when `new` is neither a part path nor a module path of the design, or when `old` is the path of a part or a module added to the design, because the old part would lose its layout to the new one. Chains (`moved("A", "B")` with `moved("B", "C")`) are therefore refused.
- `cmd_build` MUST turn such a `DslError` into `DesignScriptError` (`FEN-3004`, exit 3), as for `to_model` and `placements`.
- Aliases are not model data: `to_model` MUST give the same model with and without them, and no id changes.
- An alias is needed for one build only: the build writes the footprint under its new path, keeping its board node when it can (`layout-lens`, "Kept and re-placed footprints"), and later builds match it by uuid ("Footprint matching"). An expanded alias that matches nothing gives `layout.alias-unused` (warning).

#### Scenario: Alias recorded
- **GIVEN** a design holding `Module("power")` with `Part("R1", "Mini:Mini_R")`, and `d.moved("R1", "power/R1")`
- **WHEN** `moves(d)` is called
- **THEN** it returns `{"power/R1": "R1"}`

#### Scenario: Old part still present
- **GIVEN** a design holding parts `R1` and `R2`, and `d.moved("R1", "R2")`
- **WHEN** `moves(d)` is called
- **THEN** `DslError` is raised naming `R1`

#### Scenario: Unknown new path at build time
- **GIVEN** a `design.py` that calls `d.moved("R0", "R9")` and adds neither a part `R0` nor a part `R9`
- **WHEN** `fenolite build design.py --out out --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the message names `R9`

#### Scenario: Same new path twice
- **WHEN** `d.moved("R1", "R7")` is followed by `d.moved("R2", "R7")`
- **THEN** the second call raises `DslError` naming `R7`

#### Scenario: Model unchanged by aliases
- **GIVEN** the blink design with and without `d.moved("R0", "R1")`
- **WHEN** `canonical.dump_texts(to_model(d))` is computed for both
- **THEN** the texts are equal

#### Scenario: Module alias expanded
- **GIVEN** a design holding `Module("supply")` with parts `R1` and `C1`, and `d.moved("power", "supply")`
- **WHEN** `moves(d)` and `module_moves(d)` are called
- **THEN** they return `{"supply/C1": "power/C1", "supply/R1": "power/R1"}` and `{"supply": "power"}`

#### Scenario: Part renamed inside a renamed module
- **GIVEN** the same design with `R1` renamed `R9`, and `d.moved("power/R1", "supply/R9")` besides the module alias
- **WHEN** `moves(d)` is called
- **THEN** it returns `{"supply/C1": "power/C1", "supply/R9": "power/R1"}`

#### Scenario: Old module still present
- **GIVEN** a design holding modules `power` and `supply`, and `d.moved("power", "supply")`
- **WHEN** `module_moves(d)` is called
- **THEN** `DslError` is raised naming `power`

### Requirement: No-connect marks in the DSL
`fenolite.dsl.part.no_connect(*pins) -> None` SHALL mark each pin handle as intentionally unconnected, and `fenolite.dsl` SHALL re-export `no_connect` (an addition under "DSL package": `part.py` imports nothing new).
- Each argument MUST be a pin handle such as `u1[11]` or `u1["TP"]`; any other value MUST raise `DslError`. A call without arguments does nothing. Pins of several parts MAY be marked in one call.
- The designator MUST be stored as written in `Part.no_connects`, a set of `str`, and resolved only by the build ("No-connect marks in a build"). `u1[11]` and `u1["11"]` name the same mark, and marking a designator twice keeps one mark.
- `no_connect` on a designator that `connect` joined to a net MUST raise `DslError` naming the ref, the designator and the net. `connect` on a marked designator MUST raise `DslError` naming the ref and the designator. In both cases the earlier call stays in force.
- A mark belongs to its part: it joins the design when the part is added, before or after the call, and a part that is never added carries no mark into the model.
- `to_model` MUST set `Circuit.no_connects` to one `PinRef(<component id>, <designator as written>)` per mark, in `PinRef` order (`design-model`, "No-connect marks in the circuit model"), and MUST change nothing else: `Component.pins` stays empty and no net is created.
- There is no `Part` method for marks, no automatic marking of unused pins and no way to remove a mark.
- `docs/dsl.md` MUST gain a section "No-connect marks" with the call, the errors, the stored form and what each target does with a mark.

#### Scenario: Marks in the model
- **GIVEN** `u1 = Part("U1", "Mini:Mini_QFP32_IC")` added to a design, and `no_connect(u1[12], u1[11], u1["11"])`
- **WHEN** `to_model(design)` runs
- **THEN** `circuit.no_connects` is `(PinRef(<U1 id>, "11"), PinRef(<U1 id>, "12"))`, `U1` has `pins == ()`, and the circuit holds no net

#### Scenario: Marking a connected designator
- **WHEN** `connect(en, u1[11])` is followed by `no_connect(u1[11])`
- **THEN** `DslError` is raised naming `U1`, `11` and `EN`, and `to_model` gives no mark

#### Scenario: Connecting a marked designator
- **WHEN** `no_connect(u1[11])` is followed by `connect(en, u1[11])`
- **THEN** `DslError` is raised naming `U1` and `11`, and the net `EN` gets no member

#### Scenario: Not a pin handle
- **WHEN** `no_connect("U1.11")` or `no_connect(u1)` is called
- **THEN** `DslError` is raised

#### Scenario: Re-export and import rule
- **WHEN** `python -c "from fenolite.dsl import no_connect; print(no_connect.__module__)"` and `uv run pytest tests/unit/test_import_graph.py` run
- **THEN** the first prints `fenolite.dsl.part`, and the second passes with no `ALLOWED` change

### Requirement: No-connect marks in a build
The KiCad build (`lens.build.build_design`) SHALL resolve every mark of `Circuit.no_connects` to pin numbers by the rules of "Pins and pads in a build", refuse a pin that is marked and connected, and keep the marks in the `.fenolite/` model. It writes no schematic, so no written KiCad file changes.
- A designator MUST be read as a pin number first, and otherwise as a pin name that marks every pin with that name. A designator that is neither MUST give `build.unknown-pin` (error) naming the ref and the designator. A number that is also another pin's name MUST give `build.pin-ambiguous` (warning), and the number wins.
- After resolution, a pin that is marked and that a net lists MUST give `build.no-connect-on-net` (error) naming the ref, the pin number and the net; the build MUST exit 5 and write nothing. This code joins the `build` envelope under "Build issue codes": it MUST be a key of `lens.build.BUILD_ISSUE_CODES` with severity `error`, and `docs/cli-contract.md` MUST list it.
- After the build, `Circuit.no_connects` MUST hold `PinRef(<component id>, <pin number>)` in `PinRef` order without duplicates, and `.fenolite/circuit.json` MUST store them.
- `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, the library tables and the vendored files MUST be byte for byte those of the same design without marks: the pad of a marked pin gets no net, as the pad of any unconnected pin, and `build.unused-pin-without-pad` applies to a marked pin as to any unconnected pin.
- A rebuild takes the marks from the script; the layout lens neither reads nor keeps a mark from the board.
- The KiCad schematic writer of v0.2a lowers these marks to KiCad's no-connect flags; until then the marks serve `fenolite check` ("ERC lite stage" of `verification-loop`).

#### Scenario: Marks resolved in the built model
- **GIVEN** a blink variant with `u1 = Part("U1", "Mini:Mini_QFP32_IC", ...)`, its `GND` pins connected, and `no_connect(u1[11], u1[12])`
- **WHEN** it is built with `--confirm` into `B` and `B/.fenolite` is loaded with `canonical.load_dir`
- **THEN** the exit code is 0 and `circuit.no_connects` is `(PinRef(<U1 id>, "11"), PinRef(<U1 id>, "12"))`

#### Scenario: Written KiCad files do not change
- **GIVEN** the variant above and the same variant without the `no_connect` call
- **WHEN** both are built with the same `--seed` and `--timestamp`
- **THEN** every planned file outside `.fenolite/` has the same SHA-256 in both receipts

#### Scenario: A name and a number of one pin
- **GIVEN** `connect(gnd, u1["GND"])` and `no_connect(u1[10])` on `Mini:Mini_QFP32_IC`, whose pin `10` is named `GND`
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.no-connect-on-net` naming `U1`, `10` and `GND`, and nothing is written

#### Scenario: Unknown marked designator
- **GIVEN** `no_connect(r1["X"])` on `Mini:Mini_R`
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5 and `issues` holds `build.unknown-pin` naming `R1` and `X`

#### Scenario: New code in the closed set
- **WHEN** `uv run pytest tests/unit/lens/test_build_issues.py -k closed_set` and `uv run pytest tests/consistency` run
- **THEN** both pass, `BUILD_ISSUE_CODES["build.no-connect-on-net"]` is `error`, and a build test produces the code

### Requirement: Harness interfaces in the DSL
`fenolite.dsl.Harness(name, members)` SHALL record a named group of nets with different names as a model `Interface` of kind `harness`, without any model delta. This requirement extends "Interfaces in the DSL", whose rules hold for it.
- `Harness` MUST be a subclass of `Interface` defined in `fenolite.dsl.interfaces` and re-exported by `fenolite.dsl`. `name` is the harness type name and has no default. `members` maps an entry name to a `Net`, for example `Harness("SPI", {"MOSI": mosi, "MISO": miso, "SCK": sck})`.
- An empty `members`, an entry name that is not a non-empty string, or a member that is not a `Net` MUST raise `DslError`.
- `to_model` MUST give `Interface(kind="harness", name=<name>, members={<entry>: <net id>, …})` with the id `derived_id("itf", "dsl", "interface:harness:<name>")`. Member nets join the design.
- The order of the entries carries no meaning: a backend that needs one MUST sort the entry names.
- A KiCad build MUST keep a harness interface in `.fenolite/` and MUST give no issue for it; the written KiCad files MUST NOT depend on it. The Altium build lowers it (`altium-build`, "Module sheets in an Altium build").

#### Scenario: Harness becomes an interface
- **GIVEN** `Harness("SPI", {"MOSI": mosi, "MISO": miso, "SCK": sck})` on the nets `SPI_MOSI`, `SPI_MISO` and `SPI_SCK`, added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `SPI` with kind `harness` and the members `MOSI`, `MISO` and `SCK` equal to the ids of the three nets, and the three nets are in the circuit

#### Scenario: Empty harness refused
- **WHEN** `Harness("SPI", {})` is called
- **THEN** it raises `DslError` naming `SPI`

#### Scenario: KiCad build ignores the harness
- **GIVEN** `examples/blink_2layer/design.py` and a variant that adds `Harness("LED", {"DRV": led_drv, "A": led_a})`
- **WHEN** both are built for KiCad with `--dry-run --json`
- **THEN** the variant's `issues` equal the example's, and the planned KiCad files outside `.fenolite/` are equal byte for byte

#### Scenario: Export
- **WHEN** `uv run python -c "from fenolite.dsl import Harness; print(Harness.__module__)"` runs
- **THEN** it prints `fenolite.dsl.interfaces`

### Requirement: Planes in a build
`fenolite build` SHALL hand the script's planes to the build of its target. This requirement extends "Build command" (a step of `cmd_build`) and "Build issue codes" (one code).
- `cmd_build` MUST call `planes(design)` with `to_model`, and a `DslError` it raises MUST become `DesignScriptError` (`FEN-3004`, exit 3) as "Build command" rules for `placements`.
- With `--target altium`, `cmd_build` MUST pass the mapping to `lens.altium.build_altium(…, planes=…)` (`altium-build`, "Internal planes in an Altium build").
- With the KiCad target the board is unchanged: the plane layer is written as the signal layer it was before this change, and the build MUST give one `build.plane-not-lowered` info per plane that names the layer and the net and hints at a zone on that layer. `lens.build.BUILD_ISSUE_CODES` MUST gain `build.plane-not-lowered` with severity `info`, and `lens.build.plane_issues(planes)` MUST return those issues.
- A script without planes MUST build every file with the bytes it had before this change, for both targets.

#### Scenario: Plane in a KiCad build
- **GIVEN** a blink variant with `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `build.plane-not-lowered` info naming `In1.Cu` and `GND`, and the planned board equals the board of the variant without `planes`

#### Scenario: Plane in an Altium build
- **WHEN** the same variant is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.copper.planes` is `{"In1.Cu": "GND"}`, and no `build.plane-not-lowered` is given

#### Scenario: Unknown plane net stops the build
- **GIVEN** a blink variant with `planes={"In1.Cu": "NOPE"}`
- **WHEN** it is built
- **THEN** the exit code is 3 and stderr carries `FEN-3004` naming `NOPE`

### Requirement: Copper intents in the DSL
The DSL SHALL record copper as intents, plain data that the build resolves after placement, through `Part.pad`, `via_step`, `arc_to`, `Design.track`, `Design.via`, `Design.stitch` and `dsl.copper(design)`, and MUST still import only `core` and `model`.
- `part.pad(number, *, index=None) -> PadRef` names the pads of the part with that number. `number` MUST be a non-empty `str` or an `int` (`part.pad(9)` names the same pads as `part.pad("9")`), and `index` a non-negative `int` or `None`.
- `via_step(x, y, *, to, diameter=None, drill=None, kind="through") -> ViaStep` is a via of `kind` (`through`, `blind`, `buried` or `micro`) at `BOARD_ORIGIN + (x, y)` after which the track continues on the copper layer `to`.
- `arc_to(mid, end) -> ArcStep` is an arc from the point of the path element before it through `mid` to `end`, both `(x, y)` pairs of lengths in the frame of `place()`; the path continues from `end`.
- `Design.track(key, *path, layer="F.Cu", width=None, net=None)` takes `PadRef`s, via steps, arc steps and points written as `(x, y)` pairs of lengths in the frame of `place()`. `Design.via(key, x, y, *, net, diameter=None, drill=None, kind="through", layers=None)`, whose `layers` are the two copper layer names of a via that is not a through via, and `Design.stitch(key, *, net, pitch, along=(), region=(), origin=None, diameter=None, drill=None, clearance=None, margin=None)` take the same pairs; `origin` defaults to the corner of the board, (0, 0) in that frame. Lengths follow "DSL lengths and angles", and nets MUST be `Net` objects.
- `DslError` MUST be raised at the call for: a key that does not match `^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$` or that the design already uses for copper; a track path with fewer than two elements, starting with a via step or an arc step, holding an element of another type, or holding two consecutive elements at the same point, the point of an arc step being its `end`; an arc step whose `mid` equals its `end`; a `kind` outside the four; `layers` given for a `through` via, or anything but two different non-empty layer names for another kind; an empty `layer` or `to`; a width, diameter, drill or pitch that is not positive, or a negative margin; a stitch with both or neither of `along` and `region`, fewer than two `along` points or fewer than three `region` points.
- `dsl.copper(design)` MUST return the intents as frozen dataclasses of `dsl/intents.py`, in key order: `PadEnd(component, number, index)` with the part's component path, `ViaStep(at, layer, diameter, drill, kind="through")`, `ArcStep(mid, end)`, `TrackIntent(key, path, layer, width, net)`, `ViaIntent(key, at, net, diameter, drill, kind="through", layers=None)` and `StitchIntent(key, net, pitch, along, region, origin, diameter, drill, clearance, margin)`. Points MUST be `BOARD_ORIGIN` plus their offsets, lengths `int` nanometres and nets their names. A `PadRef` of a part that is not in the design, or a net that is not in it, MUST raise `DslError` naming it.
- `fenolite.dsl` MUST re-export `PadRef`, `via_step`, `arc_to`, `copper`, `PadEnd`, `ViaStep`, `ArcStep`, `TrackIntent`, `ViaIntent`, `StitchIntent` and `CopperIntent`, and `dsl/intents.py` is a module of the package; "DSL package" lets later requirements add both. `to_model` MUST NOT change: intents are not model objects.

#### Scenario: A track in board coordinates
- **GIVEN** the blink with `design.track("led_a", r1.pad(2), (mm(36), mm(9)), via_step(mm(36), mm(14), to="B.Cu"), d1.pad(2), width=mm(0.3))`
- **WHEN** `copper(design)` is called
- **THEN** it returns one `TrackIntent` with key `led_a`, the path `PadEnd("R1", "2", None)`, `Point(136_000_000, 109_000_000)`, `ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None)`, `PadEnd("D1", "2", None)`, layer `F.Cu`, width `300_000` and net `None`

#### Scenario: Malformed intents fail at the call
- **WHEN** `design.track("led a", r1.pad(1), d1.pad(1))`, `design.track("k", via_step(mm(1), mm(1), to="B.Cu"), r1.pad(1))`, `design.track("k2", r1.pad(1), (1, 2))` and `design.stitch("s", net=gnd, pitch=mm(2))` are called
- **THEN** each raises `DslError`, the third naming the point argument

#### Scenario: Key order and repeated keys
- **GIVEN** a via intent `b` added before a via intent `a`
- **WHEN** `copper(design)` is called, and then `design.via("a", mm(1), mm(1), net=gnd)` is called again
- **THEN** the intents come in the order `a`, `b`, and the second call raises `DslError` naming `a`

#### Scenario: Part not in the design
- **GIVEN** a track intent from `r9.pad(1)` of a part `R9` that was never added
- **WHEN** `copper(design)` is called
- **THEN** `DslError` is raised naming `R9`

#### Scenario: Arc step recorded
- **GIVEN** the blink with `design.track("bend", (mm(10), mm(10)), arc_to((mm(11), mm(11)), (mm(10), mm(12))), (mm(10), mm(15)), net=gnd, width=mm(0.25))`
- **WHEN** `copper(design)` is called
- **THEN** the path of the `TrackIntent` holds `Point(110_000_000, 110_000_000)`, `ArcStep(Point(111_000_000, 111_000_000), Point(110_000_000, 112_000_000))` and `Point(110_000_000, 115_000_000)`

#### Scenario: Via kinds recorded, earlier calls unchanged
- **GIVEN** a track whose path holds `via_step(mm(5), mm(5), to="In1.Cu", kind="blind")`, the via `design.via("core", mm(8), mm(8), net=gnd, kind="buried", layers=("In1.Cu", "In2.Cu"))`, and the track `led_a` of "A track in board coordinates"
- **WHEN** `copper(design)` is called
- **THEN** the first step has `kind == "blind"`, the via intent has `kind == "buried"` and `layers == ("In1.Cu", "In2.Cu")`, and the via step of `led_a` still equals `ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None)`

#### Scenario: Refused arc and via calls
- **WHEN** `design.track("k", arc_to((mm(1), mm(1)), (mm(2), mm(0))), r1.pad(1))`, `arc_to((mm(1), mm(1)), (mm(1), mm(1)))`, `via_step(mm(1), mm(1), to="B.Cu", kind="laser")`, `design.via("v", mm(1), mm(1), net=gnd, layers=("F.Cu", "B.Cu"))` and `design.via("w", mm(1), mm(1), net=gnd, kind="blind")` are called
- **THEN** each raises `DslError`, the last naming `layers`

### Requirement: Copper intents in a build
`lens.build.build_design` SHALL accept the keyword-only argument `copper_intents: Sequence[CopperIntentLike] = ()` and SHALL resolve it with `copper.resolve_copper` (`manual-copper`) after placing, staging, setting layers and assigning pad nets, and before the build checks and `Design.validate()`; `cli/cmd_build.py` SHALL pass `dsl.copper(design)`.
- `unplaced` MUST be the component paths that the build staged, so an intent that ends at a staged part gives `kicad.copper.end-unplaced` and creates nothing.
- The result MUST be the built model: `BuildOutput.design` holds the script copper, the written board holds it, and with an existing board `lens.preserve.merge_layout` merges it (`layout-lens`, "Script copper in a merge").
- An error of `resolve_copper` MUST make `build_design` return no files, so `build` exits 5 and writes nothing.
- When intents are given, the envelope MUST also combine `copper.EVIDENCE` and `frame.EVIDENCE`. `result.copper` MUST report `intents`, `tracks` and `vias` (created), and `regenerated`, `stale` and `duplicates` (from the merge, 0 without an existing board).
- The extension is additive, as "Built project files" (the keyword and its step), "Build command" (`result.copper`), "Build evidence" (the two evidence rows) and "Build issue codes" (the `kicad.copper.*` and `kicad.frame.*` codes, which pass through unchanged) allow: a call without `copper_intents` MUST behave as those requirements define, and `--seed`, `--timestamp` and `PYTHONHASHSEED` MUST NOT change any file of a build with intents.

#### Scenario: Routed blink
- **WHEN** `fenolite build examples/blink_routed/design.py --out B --dry-run --json` runs for target 10
- **THEN** the exit code is 0, `result.copper` reports 4 intents, 11 tracks and 7 vias, and `read_board` of the planned board holds those tracks and vias, each with a copper uuid

#### Scenario: A copper error stops the build
- **GIVEN** a variant of `examples/blink_routed/design.py` whose track `led_drv` ends at `D1` pad `2` instead of `R1` pad `1`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` hold `kicad.copper.net-conflict`, and nothing is written

#### Scenario: Intent to a staged part
- **GIVEN** a variant of the routed blink without `d1.place(…)`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0, `issues` hold `layout.unplaced` and `kicad.copper.end-unplaced` naming `D1`, and the planned board holds no script copper ending at `D1`

#### Scenario: Reproducible routed builds
- **WHEN** `uv run pytest tests/unit/lens/test_build_copper.py -k reproducible` builds the routed blink twice for target 9 and target 10, by subprocess with `PYTHONHASHSEED=1`/`--seed 1` and `PYTHONHASHSEED=2`/`--seed 2`
- **THEN** both builds write every file with the same bytes

### Requirement: Field placements in the DSL
`Part.field(name, *, dx=None, dy=None, rot=None, layer=None, visible=None, size=None, thickness=None, justify=None, outside=None, gap=None, locked=False)` SHALL record one placement request for the field `name` of the part's footprint, and `dsl.fields(design) -> Mapping[str, tuple[FieldRequest, ...]]` SHALL return the requests of every added part that has one, keyed by component path in path order, each tuple in name order; a part without a request has no key.
- `name` MUST be `"Reference"` or `"Value"`.
- `dx` and `dy` are lengths ("DSL lengths and angles") in the board frame of "Board and placements in the DSL", measured from the part's placement point, and MUST be given together. `rot` is the field's angle on the board, in degrees, normalised to [0°, 360°).
- `layer` is `"silk"` or `"fab"`, on the part's side. `size` and `thickness` are positive lengths; `size` gives both the glyph width and height. `justify` is one string of one or two words: `left` or `right` first, then `top` or `bottom`; it is recorded with single spaces. `visible` and `locked` are bools.
- `outside` is `"top"`, `"bottom"`, `"left"` or `"right"`. With it, `dx`, `dy`, `rot` and `justify` MUST be `None`. `gap` is a length of at least 0 and is allowed only with `outside`.
- `DslError` MUST be raised at the call for another name, for a second `field()` call for the same name of one part, for a request that sets nothing, and for any value outside these rules.
- `FieldRequest` is a frozen dataclass with `name`, `dx`, `dy`, `rotation`, `layer`, `visible`, `size`, `thickness`, `justify`, `outside`, `gap` and `locked`, with lengths in nm, angles in µdeg and `None` for every value not given.
- `fenolite.dsl` MUST also re-export `FieldRequest` and `fields`, as "DSL package" allows, and the package keeps importing only the standard library, `core` and `model`.

#### Scenario: Requests recorded
- **GIVEN** `r1.field("Reference", outside="top", gap=mm(0.3))` and `r1.field("Value", visible=False)`
- **WHEN** `fields(design)["R1"]` is read
- **THEN** it holds the `Reference` request with `outside == "top"` and `gap == 300_000`, then the `Value` request with `visible == False`, each with `locked == False` and `None` for every other value

#### Scenario: Offset in the board frame
- **GIVEN** `u1.field("Reference", dx=mm(0), dy="-2.5mm", rot=-90, justify="left bottom", locked=True)`
- **WHEN** `fields(design)["U1"]` is read
- **THEN** its request has `dx == 0`, `dy == -2_500_000`, `rotation == 270_000_000`, `justify == "left bottom"` and `locked == True`

#### Scenario: Refused calls
- **WHEN** `r1.field("MPN", visible=True)`, `r1.field("Reference", dx=mm(1))`, `r1.field("Reference", outside="top", dx=mm(1), dy=mm(0))`, `r1.field("Reference", justify="middle")`, `r1.field("Reference")` and `r1.field("Reference", dx=1, dy=2)` are called
- **THEN** each call raises `DslError`

#### Scenario: Second request for one field
- **WHEN** `r1.field("Value", visible=False)` is called twice
- **THEN** the second call raises `DslError` naming `R1` and `Value`

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change, and every import inside `src/fenolite/dsl/` is of the standard library, `fenolite.core` or `fenolite.model`

### Requirement: Field placements in a build
`lens.build.build_design` SHALL accept the keyword argument `fields: Mapping[str, Sequence[FieldRequestLike]]`, empty by default, and `cmd_build` SHALL pass `dsl.fields(design)`. `FieldRequestLike` is the structural protocol of `FieldRequest`, defined in `lens.fields`.
- After each part is placed or staged, and before its pad nets are assigned, the requests of its component path MUST be applied with `lens.fields.apply_requests(instance, requests)`, in name order, through the helpers of `kicad-file-backend` "Footprint field helpers". For each request:
  - `dx` and `dy` set the anchor `instance.position + (dx, dy)`, and `rotation` sets the board angle, through `set_field`;
  - `layer` sets `F.SilkS` or `B.SilkS` for `silk` and `F.Fab` or `B.Fab` for `fab`, by the part's side, and sets `mirrored` to whether the part is on the bottom side;
  - `visible`, `size` (as `Size(size, size)`), `thickness` and `justify` are set as given;
  - `outside` then calls `place_outside(…, side=outside, gap=gap)`, with `DEFAULT_GAP` when `gap` is `None`;
  - a value that is not given keeps the library's.
- A request for a field that the placed footprint does not hold MUST raise `FormatError` (`FEN-3004`) naming the footprint's lib id and the field.
- Every request MUST apply to the built copy, locked or not; on an existing board, `layout-lens` "Footprint fields across rebuilds" decides which survive.
- Applied requests add no issue.
- The keyword and its step are additions that "Built project files" allows, and the call of `cmd_build` one that "Build command" allows; without requests the build is the one they define.

#### Scenario: Reference above a part
- **GIVEN** a blink variant whose `design.py` calls `r1.field("Reference", outside="top")`
- **WHEN** it is built for target 10 into an empty folder and the board is read with `read_board`
- **THEN** `R1`'s `Reference` field has board angle 0, `v_justify == "bottom"` and `h_justify == "center"`, and equals the field that `place_outside(r1, "Reference", side="top")` gives for `R1`'s footprint in that board

#### Scenario: Hidden value of a bottom part
- **GIVEN** the blink, whose `D1` is on the bottom side, with `d1.field("Value", visible=False, layer="silk")`
- **WHEN** it is built for target 9 and the board is read back
- **THEN** `D1`'s `Value` field has `visible == False`, layer `B.SilkS` and `mirrored == True`

#### Scenario: Offset of a rotated part
- **GIVEN** a blink variant whose `U1` is placed with `rot=90` and calls `u1.field("Reference", dx=mm(0), dy=mm(-5), rot=0)`
- **WHEN** it is built and the board is read back
- **THEN** `field_anchor` of `U1`'s `Reference` equals `U1`'s position plus (0, −5 mm), and `field_angle` is 0

#### Scenario: Library without the field
- **GIVEN** a blink variant written in the test to `V/design.py`, whose `R1` uses a footprint authored in the test without a `Value` property and calls `r1.field("Value", visible=False)`
- **WHEN** `fenolite build V/design.py --out B --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004` naming the lib id and `Value`, and nothing is written

#### Scenario: Reproducible field placement
- **GIVEN** the variant of "Reference above a part"
- **WHEN** it is built twice into two empty folders
- **THEN** every file of the two folders has the same bytes

### Requirement: Zones in the DSL
`Design.zone(net, *, layers, name=None, outline=None, priority=0, clearance=None, min_thickness=None, connection=None, thermal_gap=None, thermal_spoke_width=None, islands=None, min_island_area=None, locked=False)` SHALL declare one copper zone, and `dsl.to_model` SHALL put one model `Zone` per declared zone into `Board.zones`, in name order. This adds zones to the `Board` of "DSL to model".
- `board()` MUST have been called first. `layers` MUST be a non-empty sequence of distinct copper layer names of the board: `F.Cu` and `B.Cu`, and also `In1.Cu` and `In2.Cu` for `copper=4`.
- `net` MUST be a `Net`, which joins the design, or `None` for a zone without a net. `name` defaults to the net's name, and is required when `net` is `None`. Zone names MUST be unique, non-empty and without surrounding spaces.
- `outline` is `None`, which means the board rectangle, or at least three `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL". Points are written with `BOARD_ORIGIN` added.
- A setting given as `None` MUST take the `ZoneSettings` default. Lengths follow "DSL lengths and angles". `clearance` MUST be at least 0, and `min_thickness`, `thermal_gap` and `thermal_spoke_width` above 0.
- `connection` MUST be one of `solid`, `thermal`, `none` and `thru_hole_only`, and `islands` one of `always`, `never` and `below_area`.
- `min_island_area` MUST be a string with the unit `mm2`, such as `"2.5mm2"`, converted exactly to square nanometres, and is accepted only together with `islands="below_area"`.
- `priority` MUST be an `int` of at least 0, and `locked` a `bool`.
- Each violation MUST raise `DslError` at the call, naming the argument.
- The model zone MUST have the id `derived_id("zon", "dsl", "zone:<name>")` (`design-model`, "Identifier derivation"), `name`, the layers, the net's id, `priority`, `locked`, the settings, `filled == False` and no fills. Hatching and smoothing are not DSL arguments and keep their defaults.

#### Scenario: Pour with a 0.3 mm clearance
- **GIVEN** a design with `board(mm(50), mm(30))` and `d.zone(gnd, layers=("F.Cu", "B.Cu"), clearance=mm(0.3))`
- **WHEN** `to_model(d)` runs
- **THEN** `board.zones` holds one zone named `GND`, with layers `("F.Cu", "B.Cu")`, the id of net `GND`, `settings == ZoneSettings(clearance=300_000)`, and the outline points (100 mm, 100 mm), (150 mm, 100 mm), (150 mm, 130 mm) and (100 mm, 130 mm)

#### Scenario: Zone before the board
- **WHEN** `d.zone(gnd, layers=("F.Cu",))` is called before `board()`
- **THEN** `DslError` is raised

#### Scenario: Inner layer on a two-layer board
- **GIVEN** a design with `board(mm(50), mm(30))`
- **WHEN** `d.zone(gnd, layers=("In1.Cu",))` is called
- **THEN** `DslError` is raised naming `In1.Cu`

#### Scenario: Bare number refused
- **WHEN** `d.zone(gnd, layers=("F.Cu",), clearance=0.3)` is called
- **THEN** `DslError` is raised naming `clearance`

#### Scenario: Island area needs below_area
- **WHEN** `d.zone(gnd, layers=("F.Cu",), islands="never", min_island_area="2mm2")` is called, and then `d.zone(vin, layers=("B.Cu",), islands="below_area", min_island_area="2mm2")`
- **THEN** the first raises `DslError` naming `min_island_area`, and the second gives a zone with `min_island_area == 2_000_000_000_000`

#### Scenario: Names are unique
- **GIVEN** `d.zone(gnd, layers=("F.Cu",))`
- **WHEN** `d.zone(gnd, layers=("B.Cu",))` is called, and then `d.zone(gnd, layers=("B.Cu",), name="GND_BOTTOM")`
- **THEN** the first raises `DslError` naming the name `GND`, and the second is accepted

### Requirement: Zones in a build
`fenolite build` SHALL write every zone that the script declares, with its settings, for targets 9 and 10, and the written board SHALL read back with those zones.
- `lens.build.build_design` MUST keep the `Board.zones` of the model it is given, an addition to "Built project files" that needs no keyword. The writer follows `kicad-file-backend` "Zone settings are written" for these created zones.
- Read back with `read_board`, each zone MUST have the script's name, outline, layers, net, priority and `locked`, `settings.effective()` equal to the script's, and `filled == False`.
- A build over an existing board MUST merge zones as `layout-lens` "Zones declared in the script" describes.
- `fenolite build --target altium` MUST keep one copper source (`altium-build`, "Copper in an Altium build"). Without `--copper-from` and without copper intents, the script's zones are the zones of the model source. With copper intents and without `--copper-from`, `cmd_build` MUST give the build the model without the script's zones: the script source holds them, as the in-memory KiCad build keeps them (`altium-build`, "Script copper in an Altium build"). With `--copper-from`, `cmd_build` MUST give the build the model without the script's zones: the routed board is the copper source, and its zones stand for the `zone()` calls that the KiCad build wrote into it.

#### Scenario: Blink with a pour on both targets
- **GIVEN** a blink variant with `d.zone(gnd, layers=("B.Cu",), clearance=mm(0.3), connection="solid")`
- **WHEN** it is built for targets 9 and 10 with `--confirm`, and each written board is read with `read_board`
- **THEN** the exit code is 0, each board holds a zone `GND` on `B.Cu` with `clearance == 300_000` and `connection == "solid"`, and only the target-9 text holds `(filled_areas_thickness no)`

#### Scenario: Altium build of a script with a zone
- **GIVEN** a confirmed target-10 build of the pour variant in `B`
- **WHEN** the script is built with `--target altium --confirm`, and again into another folder with `--copper-from B/blink.kicad_pcb`
- **THEN** both exit codes are 0, `result.copper.source` is `model` and then `board`, and `result.copper.zones` is 1 in both

#### Scenario: Zone uuid from the name
- **GIVEN** the same variant built twice into empty folders
- **WHEN** the two board texts are compared
- **THEN** they are byte-identical, and the zone's uuid is `pcb.kicad_uuid` of a zone with id `derived_id("zon", "dsl", "zone:GND")`

#### Scenario: Altium build of a script with a zone and copper intents
- **GIVEN** a variant of `examples/blink_routed/design.py` with `design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.copper.source` is `script` and `result.copper.zones` is 1

### Requirement: Copper guard before writing
`fenolite build` with the KiCad target (`--target kicad`, the default) SHALL judge the copper of the triad it is about to write with `fenolite.checks.copper.check_copper` (`copper-check`) after `lens.build.build_design` returns its files and before `cmd_build` calls `check_existing` and returns its plan, on `--dry-run` and `--confirm` alike. When `build_design` refused (no files), the guard MUST NOT run. With `--target altium` the guard MUST NOT run and `result` holds no `copper_check`: that branch writes no KiCad triad (`altium-build`).
- **What is judged.** `cmd_build` MUST read the planned `<name>.kicad_pcb` text back with `read_board`, apply the planned `<name>.kicad_pro` and `<name>.kicad_dru` texts with `copperrules.design_rules_from_texts` and `major` = the build's target (`Context.kicad_target`), take the pads from c0028's `BoardFrame.board_pads` of `KicadBackend`, and call `check_copper` with the design, `min_clearance`, `rules_over_classes` and `floor_over_rules` it gets. The guard therefore judges the bytes that will be written, preserved copper (`layout-lens`) included. It MUST read and write no file.
- **Modes.** The option `--copper-check refuse|warn` MUST default to `refuse`. With `refuse`, every copper issue MUST join the envelope's `issues` with its severity, so a `copper.short` or a `copper.clearance` error makes the build return no planned write and exit 5 ("Build command"). With `warn`, every copper issue of severity `error` MUST be reported with severity `warning` and ` (copper guard in warn mode)` appended to its message, and the build MUST plan its writes as usual. Any other value MUST exit 2 with `FEN-2001`. `--copper-check` given with `--target altium` MUST exit 2 with `FEN-2001`, as `--altium-format` does with the KiCad target.
- **Codes.** The guard's codes are those of `checks.codes.ISSUE_CODES` (`verification-loop`, "Copper stage issue codes"). They are not build findings: they join the envelope's `issues` unchanged, as "Build issue codes" allows for codes that later requirements add, and `lens.build.BUILD_ISSUE_CODES` and `build_design` stay unchanged.
- **Result.** `result.copper_check` MUST hold `mode`, `ran`, `shorts`, `clearance` (counts of findings), `rules` (`{min_clearance, opaque_clearance_rules, unread}`) and `evidence` (`{level, oracle, hypotheses}` of `Evidence.combine(CopperReport.evidence, pcb.EVIDENCE, DesignRules.evidence)`). The `build` envelope's own evidence stays as "Build evidence" defines it.
- The option, the guard step of `cmd_build` and the `result` key are additions that "Build command" allows.
- Python callers of `build_design` are not guarded; `docs/dsl.md` MUST show the call of `check_copper` that gives them the same verdict.

#### Scenario: Blink passes the guard
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --confirm --json` runs
- **THEN** the exit code is 0, `result.copper_check.ran` is true, and `result.copper_check.shorts` and `result.copper_check.clearance` are 0

#### Scenario: Short refused before writing
- **GIVEN** a confirmed blink build in `B` whose board got, by `tests/_coppercheck.py::bridge_pads(text, "R1", "2", "1")`, a segment on the net of `R1` pad 2 laid across `R1` pad 1
- **WHEN** the build runs again with `--confirm --json`
- **THEN** the exit code is 5, the issues hold one `copper.short` error whose `where` contains `R1-1`, and every file in `B` keeps its bytes

#### Scenario: Warn mode writes
- **GIVEN** the same edited build
- **WHEN** the build runs again with `--copper-check warn --confirm --json`
- **THEN** the exit code is 0, the files are written, and the issues hold the `copper.short` with severity `warning` and a message ending with `(copper guard in warn mode)`

#### Scenario: Unknown mode
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --copper-check off --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

### Requirement: Placement legality in a build
`fenolite build` with the KiCad target (`--target kicad`, the default) SHALL judge the placement of the board it is about to write with `fenolite.placement.legality.check` (`placement`, "Placement legality"), in `cmd_build.placement_guard`, after `lens.build.build_design` returns its files and before `cmd_build` returns its plan, on `--dry-run` and `--confirm` alike. When `build_design` refused (no files), the check MUST NOT run and `result.placement.ran` MUST be false. With `--target altium` the check MUST NOT run and `result` holds no `placement`.
- **What is judged.** `cmd_build` MUST read the planned `<name>.kicad_pcb` text back with `read_board`, take the extents from c0028's `BoardFrame.placed_extents` of `KicadBackend`, the rings from `backends.kicad.outline.board_outline` of that board, and `edge_clearance` from `placement.legality.edge_clearance` of the built model design (0 without a board-wide `edge_clearance` rule). The check therefore judges the bytes that will be written, preserved placements (`layout-lens`) included. It MUST read and write no file.
- Each `place.*` issue MUST be reported with a severity no higher than `warning`, so a build never refuses and never exits 5 for placement.
- Parts that the build stages (`result.staged`, reported as `layout.unplaced`) MUST NOT be judged.
- **Codes.** The codes are those of `placement.ISSUE_CODES` (`placement`, "Placement issue codes"). They are not build findings: they join the envelope's `issues` as "Build issue codes" allows for codes that later requirements add, and `lens.build.BUILD_ISSUE_CODES` and `build_design` stay unchanged, because `lens` may not import `placement` (`package-layering`).
- `result.placement` MUST hold `ran` and `counts`, the number of issues by code.
- The step of `cmd_build` and the `result` key are additions that "Build command" allows.

#### Scenario: Overlap reported, build written
- **GIVEN** a blink variant whose `R1` and `D1` are placed on the same side with courtyards that overlap by 0.1 mm and copper that stays clear
- **WHEN** `fenolite build … --confirm` runs
- **THEN** the exit code is 0, the board is written, and `issues` holds one `place.courtyard-overlap` warning naming `D1,R1`

#### Scenario: Part over the edge
- **GIVEN** a blink variant whose `R1` is placed across the outline's right edge
- **WHEN** the build runs with `--dry-run`
- **THEN** `issues` holds `place.outside-outline` naming `R1` as a warning, and nothing is written

#### Scenario: Staged parts are not judged
- **GIVEN** a blink variant in which `R1` has no `place()`
- **WHEN** the build runs
- **THEN** `issues` holds `layout.unplaced` for `R1` and no `place.outside-outline` for it

#### Scenario: Clean blink stays clean
- **WHEN** the blink is built for targets 9 and 10
- **THEN** `issues` holds no `place.*` issue, `result.placement.counts` is empty, and every file has the bytes it had before this change

### Requirement: Rule minimums in the DSL
`design.rules.minimum(*, clearance=None, track_width=None, via_diameter=None, via_drill=None, hole_size=None, edge_clearance=None, netclass=None)` SHALL declare one design-rule minimum per given length. The keywords are the first six rule kinds of the model (`fenolite.model.rules.RuleKind`), listed in this order by `dsl.design.MINIMUM_KINDS`; the other kinds are declared with `rule()` ("Rule constructor in the DSL").
- A value MUST be a `Length` or a string with a unit, as "DSL lengths and angles" rules, and MUST be above 0.
- `netclass=None` declares board minimums. `netclass="<name>"` declares minimums for the nets of that class, which MUST already be declared with `design.rules.netclass`.
- `minimum()` MAY be called several times. `DslError` MUST be raised at the call for: no length given; a bare number, a value without a unit or a value of 0 or less; a `netclass` that is not a declared class; and a kind declared twice for the same scope (the board, or one class). A refused call MUST record nothing.
- `Rules.minimums` MUST hold one `dsl.design.MinimumSpec(kind, netclass, min)` per declared minimum, keyed by `(kind, netclass)`, with `min` in integer nanometres.
- `dsl.to_model` MUST write one model `Rule` per minimum into `Design.rules.rules`:

  | field | board minimum | class minimum |
  |---|---|---|
  | `id` | `derived_id("rul", "dsl", "rule:<kind>")` | `derived_id("rul", "dsl", "rule:<kind>:<class>")` |
  | `name` | `min_<kind>` | `min_<kind>_<class>` |
  | `selector_a` | `Selector("all")` | `Selector("netclass", "<class>")` |
  | `priority` | `0` | `1` |

  with `kind` the keyword, `min` the value, severity `error`, and no `selector_b`, `layers`, `opt` or `max`. The rules MUST be in this order: board minimums, then class minimums by class name, each group in the order of `MINIMUM_KINDS`. The order of the `minimum()` calls MUST NOT change the model.
- The priorities make a class minimum govern the items of its class over the board minimum of the same kind (`rules-model`, "Lowered rules follow priority").
- The KiCad build needs no step of its own: `write_triad` lowers `Design.rules` to `<name>.kicad_dru` (`rules-model`, "Fenolite lowers only the design's rules") and to the board-setup minimums of `<name>.kicad_pro` ("Board-wide rules lower to board-setup minimums"), with the issues of those requirements. A design without `minimum()` calls MUST build the same bytes as before this requirement.
- `docs/dsl.md` MUST describe `minimum()` in a section "Design rules", list it in the API section, and hold the `rule` row in the key table.

#### Scenario: Board and class minimums in the model
- **GIVEN** a design with the class `PWR`, `d.rules.minimum(track_width=mm(0.6), netclass="PWR")` and then `d.rules.minimum(clearance=mm(0.15), track_width="0.25mm")`
- **WHEN** `to_model(d)` runs
- **THEN** `rules.rules` holds, in this order, `min_clearance` (`clearance`, `all`, `min == 150_000`, priority 0), `min_track_width` (`track_width`, `all`, `min == 250_000`, priority 0) and `min_track_width_PWR` (`track_width`, `netclass PWR`, `min == 600_000`, priority 1), and the id of the last is `derived_id("rul", "dsl", "rule:track_width:PWR")`

#### Scenario: Call order does not matter
- **GIVEN** two designs that make the same `minimum()` calls in opposite orders
- **WHEN** `canonical.dump_texts(to_model(d))["rules.json"]` is taken for both
- **THEN** the two texts are byte-identical

#### Scenario: Refused calls
- **WHEN** `d.rules.minimum()`, `d.rules.minimum(clearance=0.2)`, `d.rules.minimum(clearance=mm(0))`, `d.rules.minimum(clearance=mm(0.2), netclass="HV")` without a class `HV`, and a second `d.rules.minimum(clearance=mm(0.3))` after `d.rules.minimum(clearance=mm(0.2))` are called
- **THEN** each raises `DslError` naming `minimum()`, and `d.rules.minimums` holds only the minimum of the accepted call

#### Scenario: Built rules and minimums
- **GIVEN** the blink design with `d.rules.minimum(clearance=mm(0.15), track_width=mm(0.25))` and `d.rules.minimum(clearance=mm(0.2), track_width=mm(0.5), netclass="PWR")`
- **WHEN** it is built for target 10
- **THEN** `blink.kicad_dru` holds the rules `fenolite_0_min_clearance`, `fenolite_0_min_track_width`, `fenolite_1_min_clearance_pwr` and `fenolite_1_min_track_width_pwr` in this order, the last two with the condition `"A.NetClass == 'PWR'"`; `board.design_settings.rules` of `blink.kicad_pro` has `min_clearance == 0.15` and `min_track_width == 0.25`; and `.fenolite/rules.json` holds the four rules

#### Scenario: Unchanged without minimums
- **GIVEN** the blink design without a `minimum()` call
- **WHEN** it is built for target 10
- **THEN** `blink.kicad_dru` is `(version 1)\n` and `.fenolite/rules.json` holds no rule

#### Scenario: Rebuild replaces the minimums
- **GIVEN** a built project whose script declares `minimum(track_width=mm(0.25))`, and a rule named `mine` added to its `.kicad_dru` by hand
- **WHEN** the script changes the value to `mm(0.3)` and the project is built again
- **THEN** the rules file holds `fenolite_0_min_track_width` once, with `(min 0.3mm)`, followed by the rule `mine`

### Requirement: Per-component pin-to-pad mapping
The DSL build SHALL assign each symbol pin's net to the physical footprint pad named by `Component.pin_pad_map`, using identity mapping for pins not listed. Circuit net members and no-connects SHALL remain keyed by symbol pin number. A mapping with a missing source pin, missing pad target, or duplicate physical target MUST report `build.pin-pad-map-invalid` as an error and write no output. This issue SHALL join the closed build issue set of `design-dsl`, "Build issue codes".

#### Scenario: Remap a connected symbol pin
- **GIVEN** component `U1` maps symbol pin `1` to physical pad `2` and pin `1` is connected to net `N`
- **WHEN** the build resolves its footprint pads
- **THEN** pad `2` carries net `N`, while `Net.members` keeps pin number `1`

#### Scenario: Refuse an invalid pin-to-pad map
- **GIVEN** a map names a missing source pin or target pad
- **WHEN** the component is built
- **THEN** `build.pin-pad-map-invalid` is an error and the build writes no files

### Requirement: Project-authored symbols

`fenolite.dsl.Symbol(library, name, *, reference, value="", footprint="", description="")` SHALL author a one-unit symbol. `Symbol.pin(number, name, *, etype="passive", at, length, rotation=0, shape="line")` SHALL record a uniquely numbered pin with exact DSL lengths and one of the supported electrical types, shapes and cardinal rotations. `Design.add(symbol)` SHALL register symbols explicitly by `library:name`, and duplicate IDs or symbols without pins MUST be refused. The DSL SHALL expose the completed definition as a model `SymbolDef`, without adding library definitions to canonical design JSON.

`fenolite build --target kicad` SHALL resolve component symbol IDs against the design's authored definitions before external library sources. It SHALL write one `lib/<nickname>.kicad_sym` per authored library and a `sym-lib-table` whose `${KIPRJMOD}` rows point at those files. These are planned writes on dry-run and appear in the receipt on confirmation. The serializer MUST be deterministic, and the build MUST NOT invoke KiCad tools. The Altium target is outside this requirement.

#### Scenario: Build using only an authored symbol
- **GIVEN** a component whose symbol ID is present only in a `Symbol` attached to the design, and a separately resolvable footprint
- **WHEN** `fenolite build ... --target kicad --dry-run --json` runs
- **THEN** it succeeds without a symbol library table row as input, resolves the symbol pins, and plans its symbol library plus `sym-lib-table`

#### Scenario: Authored symbol library artifact
- **GIVEN** a design with two authored symbols under nickname `Local`
- **WHEN** its KiCad build is confirmed
- **THEN** it writes one `lib/Local.kicad_sym` containing both symbols and one matching `${KIPRJMOD}` table row

### Requirement: Rule constructor in the DSL
`design.rules.rule(name, kind, *, where=select.ALL, between=None, layers=(), min=None, opt=None, max=None, severity="error", priority=0)` SHALL declare one design rule of any model kind (`fenolite.model.rules.RuleKind`), with selectors from `fenolite.dsl.select` ("Selectors in the DSL").
- `DslError` MUST be raised at the call, and nothing recorded, for: a `name` that is not a non-empty string or is already used by `rule()`; a `kind` outside `RuleKind`; no limit; a limit that is not a `Length` or a string with a unit; a negative `min`, or an `opt` or `max` of 0 or less; `min` above `opt` or `max`, or `opt` above `max`; a `where` or `between` that is not a selector; a `between` for a kind other than `clearance` and `creepage`; a `layers` value that is not a tuple of strings; a `severity` outside `error`, `warning` and `ignore`; a `priority` that is not an integer of 0 or more.
- What depends on the target is not checked here: limits per kind, kind support, globs, selector support and layer names are refused by the lowering with its codes, and `build` reports them (exit 7, `FEN-7001`).
- `Rules.named` MUST hold one `dsl.design.RuleSpec` per call, in call order.
- `dsl.to_model` MUST add one model `Rule` per call to `Design.rules.rules`, after the rules of `minimum()`, in call order: id `derived_id("rul", "dsl", "rule:named:<name>")`, the given name, kind, limits, severity and priority, `selector_a` from `where`, `selector_b` from `between` (`None` when not given) and `layers` as given.
- `docs/dsl.md` MUST describe `rule()` in its section "Design rules", with an example per kind group, and say that priority 0 is written first and governs least.

#### Scenario: Creepage rule in the model
- **GIVEN** a design with the classes `HV` and `LV` and `d.rules.rule("mains", "creepage", where=select.netclass("HV"), between=select.netclass("LV"), min=mm(6.4))`
- **WHEN** `to_model(d)` runs
- **THEN** `rules.rules` holds one `creepage` rule named `mains`, with `selector_a == Selector("netclass", "HV")`, `selector_b == Selector("netclass", "LV")`, `min == 6_400_000` and the id `derived_id("rul", "dsl", "rule:named:mains")`

#### Scenario: Board-wide hole pitch
- **WHEN** `d.rules.rule("pitch", "hole_to_hole", min="0.25mm")` is declared and the design is built for target 10
- **THEN** `<name>.kicad_dru` holds a rule `"fenolite_0_pitch"` with `(constraint hole_to_hole (min 0.25mm))` and no condition

#### Scenario: Second side refused for a hole kind
- **WHEN** `d.rules.rule("x", "hole_clearance", where=select.net("A"), between=select.net("B"), min=mm(0.3))` is called
- **THEN** `DslError` is raised naming `between` and `hole_clearance`, and nothing is recorded

#### Scenario: Target refusal reported by the build
- **GIVEN** a design with a `creepage` rule
- **WHEN** it is built with `--kicad-version 9 --dry-run --json`, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001`, a message that names the rule and says that KiCad 9.0 does not check creepage rules, and a hint naming `--allow-lossy`; the second exits 0 with `rules.dropped-for-target` in `issues`

### Requirement: Selectors in the DSL
`fenolite.dsl.select` SHALL build rule selectors: `ALL`, `net(name)`, `netclass(name)`, `ref(name)` and `item(kind)`, each a `select.Select`, combined with `&` (and), `|` (or) and `~` (not); `fenolite.dsl` SHALL re-export `select` (an addition under "DSL package").
- `net` MUST take a net name or a `Net`, `netclass` a class name declared with `design.rules.netclass`, `ref` a reference or a `Part`, and `item` one of `track`, `via`, `pad` and `zone`. A `Net` or `Part` MUST be stored by its name, so a rule follows a rename made where the object is created. An empty name, or an `item` value outside the list, MUST raise `DslError`.
- `a & b` MUST give `Selector("and", items=…)` and `a | b` `Selector("or", items=…)`, flattening nested operations of the same op; `~a` MUST give `Selector("not", items=(a,))`. `ALL` MUST NOT be combined: `ALL & x` raises `DslError`.
- A name MAY hold `*`, which the model keeps as a glob; whether a target writes it is decided by the lowering (`rules-model`, "Closed selector grammar").
- `Select.to_model()` MUST return the model `Selector`, and two equal expressions MUST give equal selectors.

#### Scenario: Compound selector
- **WHEN** `(select.net("A") | select.net("B")) & ~select.item("via")` is turned into a model selector
- **THEN** it is `Selector("and", items=(Selector("or", items=(Selector("net", "A"), Selector("net", "B"))), Selector("not", items=(Selector("item_kind", "via"),))))`

#### Scenario: Net object
- **GIVEN** `vbus = Net("VBUS")` added to the design and a rule with `where=select.net(vbus)`
- **WHEN** `to_model` runs
- **THEN** the rule's `selector_a` is `Selector("net", "VBUS")`

#### Scenario: ALL combined
- **WHEN** `select.ALL & select.net("A")` is evaluated
- **THEN** `DslError` is raised

### Requirement: Quantities in the DSL
`fenolite.dsl.quantity` SHALL provide `Quantity`, an exact value of one unit among `ohm`, `farad`, `henry`, `volt`, `ampere`, `hertz`, `watt` and `second`, and the constructors `ohm(x)`, `farad(x)`, `henry(x)`, `volt(x)`, `amp(x)`, `hertz(x)`, `watt(x)` and `second(x)`; `fenolite.dsl` SHALL re-export `Quantity` and the constructors (an addition under "DSL package").
- **Input.** `x` MUST be an `int`, a `fractions.Fraction`, or a text: a decimal number, an optional SI prefix among `p`, `n`, `u`, `µ`, `m`, `k`, `M` and `G`, and an optional symbol of the constructor's unit (`Ω`, `ohm` or `R`; `F`; `H`; `V`; `A`; `Hz`; `W`; `s`), with optional blanks between number and prefix; or the IEC 60062 letter code, where the prefix letter, or `R` for ohms, stands for the decimal point (`4k7`, `2R2`, `1n5`).
- A `float`, a `bool`, a symbol of another unit, a text that does not parse, or a negative value for a unit other than volts and amperes MUST raise `DslError` naming the input.
- **Value.** The value MUST be held as a `Fraction` of the unit. Equality, ordering and hashing MUST compare the unit and the exact value; ordering between different units MUST raise `TypeError`.
- **Arithmetic.** `+` and `-` MUST take two quantities of one unit; `*` and `/` MUST take an `int` or a `Fraction`; any other operand MUST raise `TypeError`.
- **Text.** `text()` MUST print the value scaled by the largest SI prefix, in steps of 1 000 from `p` to `G`, that keeps its magnitude at least 1 (no prefix between 1 and 1 000), as the shortest exact decimal, followed by the prefix (`u` for micro) and the symbol (`Ω`, `F`, `H`, `V`, `A`, `Hz`, `W`, `s`). A value that is not a terminating decimal at that scale MUST raise `DslError`. `text(code=True)` MUST print the IEC 60062 letter code for ohms, farads and henries, the prefix letter (or `R` without a prefix, for ohms) standing for the decimal point and no symbol, and MUST raise `DslError` for the other units.
- No quantity MUST reach the model or `.fenolite/`: it is a script value.

#### Scenario: Equal forms
- **WHEN** `ohm("4k7")`, `ohm("4.7k")`, `ohm("4.7 kΩ")` and `ohm(4700)` are compared
- **THEN** they are equal, have one hash, and `text()` of each is `4.7kΩ`

#### Scenario: Canonical texts
- **WHEN** `farad("0.1u").text()`, `volt("3.30").text()`, `hertz(16_000_000).text()` and `ohm("2R2").text(code=True)` are computed
- **THEN** they are `100nF`, `3.3V`, `16MHz` and `2R2`

#### Scenario: Float refused
- **WHEN** `ohm(4.7e3)` is called
- **THEN** `DslError` is raised naming the value

#### Scenario: Wrong unit
- **WHEN** `farad("10V")` is called
- **THEN** `DslError` is raised naming `10V`

### Requirement: Part values from quantities
`Part(ref, lib_id, footprint=None, value="")` SHALL accept a `Quantity` as `value` and SHALL store its `text()`; a string value MUST keep working unchanged.
- The model's `Component.value` MUST be that text, so two parts given equal quantities have equal values whatever their spelling in the script.

#### Scenario: One value for two spellings
- **GIVEN** `Part("R1", "Mini:Mini_R", value=ohm("4k7"))` and `Part("R2", "Mini:Mini_R", value=ohm("4700"))` in one design
- **WHEN** `to_model` runs
- **THEN** both components have the value `4.7kΩ`

### Requirement: Typed interfaces in the DSL
`fenolite.dsl.interfaces` SHALL define `I2C(sda, scl, *, name=None)`, `SPI(sck, mosi, miso, *, cs=(), name=None)`, `UART(tx, rx, *, name=None)` and `USB2(dp, dn, *, vbus=None, gnd=None, name=None)`, subclasses of `Interface` re-exported by `fenolite.dsl` (an addition under "DSL package"), which record buses as model `Interface` entities without any model delta. This requirement extends "Interfaces in the DSL", whose rules hold for them.
- Kinds and members: `I2C` gives kind `i2c` with `sda` and `scl`; `SPI` gives `spi` with `sck`, `mosi`, `miso` and `cs0` … `cs<n-1>` for the nets of `cs` in order; `UART` gives `uart` with `tx` and `rx`, named from device A; `USB2` gives `usb2` with `dp` and `dn`, and `vbus` and `gnd` when given.
- Every argument naming a net MUST be a `Net`; two members of one interface MUST be distinct nets; otherwise `DslError` is raised. A net MAY be a member of several interfaces.
- The default name MUST be `"<first net name>/<second net name>"`, and the id MUST be `derived_id("itf", "dsl", "interface:<kind>:<name>")`. Member nets join the design.
- A KiCad build MUST keep the four kinds in `.fenolite/`, and the written KiCad files outside it MUST NOT depend on them.

#### Scenario: I2C in the model
- **GIVEN** `I2C(sda, scl)` on the nets `SDA` and `SCL`, added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `SDA/SCL` with kind `i2c` and members `sda` and `scl` equal to the ids of the two nets

#### Scenario: SPI chip selects
- **GIVEN** `SPI(sck, mosi, miso, cs=(cs_flash, cs_adc))`
- **WHEN** `to_model` runs
- **THEN** the interface has the members `sck`, `mosi`, `miso`, `cs0` (the net of `cs_flash`) and `cs1` (the net of `cs_adc`)

#### Scenario: One net twice
- **WHEN** `USB2(dp, dp)` is called
- **THEN** `DslError` is raised naming the net

### Requirement: Attaching parts to interfaces
Each typed interface SHALL provide `attach(part, **roles)`, which connects pins of one part to the interface's nets by role through `connect`, so that every rule of `connect` applies.
- `I2C.attach(part, *, sda, scl)` and `USB2.attach(part, *, dp, dn, vbus=None, gnd=None)` MUST connect each given pin to the net of its role. A role whose net the interface does not have (`vbus` on a `USB2` without `vbus`) MUST raise `DslError`.
- `UART.attach(part, *, side, tx, rx)`: with `side="a"` the `tx` pin MUST join the `tx` net and the `rx` pin the `rx` net; with `side="b"` the `tx` pin MUST join the `rx` net and the `rx` pin the `tx` net. Any other `side` MUST raise `DslError`.
- `SPI.attach(part, *, role, sck, mosi, miso, cs=None, cs_index=None)`: `sck`, `mosi` and `miso` MUST join the nets of their names. With `role="controller"`, `cs` MUST be a sequence with one pin per chip-select net, joined in order, and `cs_index` MUST be `None`. With `role="peripheral"`, `cs` MUST be one pin and `cs_index` the index of its chip-select net. Any other combination MUST raise `DslError`.
- A pin argument MUST be a pin handle of `part`, or a designator, which MUST be resolved as `part[designator]`. A pin handle of another part MUST raise `DslError`.

#### Scenario: UART crossed for the second device
- **GIVEN** `uart = UART(a_tx, a_rx)`, `uart.attach(u1, side="a", tx=u1["TX"], rx=u1["RX"])` and `uart.attach(u2, side="b", tx=u2["TX"], rx=u2["RX"])`
- **WHEN** `to_model` runs
- **THEN** the net of `a_tx` holds `U1` pin `TX` and `U2` pin `RX`, and the net of `a_rx` holds `U1` pin `RX` and `U2` pin `TX`

#### Scenario: SPI peripheral on its chip select
- **GIVEN** the SPI of "SPI chip selects", a controller `U1` attached with `cs=(u1["CS0"], u1["CS1"])`, and a peripheral `U3` attached with `cs=u3["CS"]` and `cs_index=1`
- **WHEN** `to_model` runs
- **THEN** the net of `cs_adc` holds `U1` pin `CS1` and `U3` pin `CS`, and the net of `cs_flash` holds only `U1` pin `CS0`

#### Scenario: Pin of another part
- **WHEN** `bus.attach(u1, sda=u2["SDA"], scl=u1["SCL"])` is called on an `I2C`
- **THEN** `DslError` is raised naming `U2`, and nothing is connected

### Requirement: Interface checks in a build
A build SHALL check the interfaces of the design after the parts are resolved, as "Built project files" allows for added steps of `build_design`, and SHALL report two warnings, which join the closed build set ("Build issue codes"):

| code | severity | when |
|---|---|---|
| `build.diff-pair-name` | warning | the two nets of a `diff_pair` (`p`, `n`) or `usb2` (`dp`, `dn`) interface do not form a KiCad differential pair by name |
| `build.i2c-pullup-missing` | warning | an I2C line has no two-pin part to the `hv` net of a `power` interface |

- **Pair names** (`H-K-DIFFPAIR-NAMES`). The names, in KiCad's stored form, form a pair when they are equal except for the last character, which is `P` for the first net and `N` for the second, or `+` and `-`; letter case counts. The hint MUST propose a second name: the first name with its last character `P` or `+` replaced by `N` or `-`; when the first name ends in neither, it MUST propose `<first name>_P` and `<first name>_N`.
- **Pull-ups.** For the `sda` and `scl` nets of each `i2c` interface, a pull-up is a component whose resolved symbol has exactly two pins, one on that net and the other on the `hv` net of a `power` interface of the design. The issue MUST name the interface and the line.
- The checks MUST NOT change any file or the model, and a design without interfaces MUST give neither code.

#### Scenario: Pair names that KiCad does not pair
- **GIVEN** a blink variant with `USB2(usb_dp, usb_dm)` on the nets `USB_DP` and `USB_DM`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.diff-pair-name` naming `USB_DP` and `USB_DM`, with a hint naming `USB_DN`, and one `build.interface-not-lowered`

#### Scenario: Pair names that KiCad pairs
- **WHEN** the same variant uses the nets `USB_P` and `USB_N`
- **THEN** `issues` hold no `build.diff-pair-name`

#### Scenario: Missing pull-up
- **GIVEN** a design with `Power(vdd, gnd)`, `I2C(sda, scl)`, a resistor from `SDA` to `VDD` and none on `SCL`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.i2c-pullup-missing` naming the interface and `scl`

### Requirement: Pad zone connections in the DSL
`Part.zone_connection(number, connection, *, index=None, locked=False)` SHALL record one request for how copper zones connect to the pads of the part's footprint that carry `number`, and `dsl.pad_zones(design) -> Mapping[str, tuple[PadZoneRequest, ...]]` SHALL return the requests of every added part that has one, keyed by component path in path order, each tuple sorted by `number` and then `index`, `None` first. A part without a request has no key.
- `number` MUST be a non-empty `str` or an `int`, as in `Part.pad`. `index` MUST be `None` or a non-negative `int`: `None` names every pad that carries the number, an `int` the pad at that position among them, in the footprint's pad order.
- `connection` MUST be `"solid"`, `"thermal"`, `"none"` or `"thru_hole_only"`, the values of `Pad.zone_connection` (`design-model`). `locked` MUST be a `bool`.
- `DslError` MUST be raised at the call for another connection, for a second request for the same number and index of one part, and for a request with an index when the part already holds one for that number without an index, or the reverse: the two would name the same pad.
- `PadZoneRequest` is a frozen dataclass with `number` (a `str`), `index`, `connection` and `locked`.
- `fenolite.dsl` MUST also re-export `PadZoneRequest` and `pad_zones`, as "DSL package" allows, and the package keeps importing only the standard library, `core` and `model`. `to_model` MUST NOT change: a request is not a model object.

#### Scenario: Requests recorded
- **GIVEN** `u1.zone_connection(9, "solid")` and `u1.zone_connection("1", "none", locked=True)`
- **WHEN** `pad_zones(design)["U1"]` is read
- **THEN** it holds `PadZoneRequest("1", None, "none", True)` and then `PadZoneRequest("9", None, "solid", False)`

#### Scenario: One of several pads
- **GIVEN** `j1.zone_connection(1, "thermal", index=0)` and `j1.zone_connection(1, "solid", index=1)`
- **WHEN** `pad_zones(design)["J1"]` is read
- **THEN** it holds the two requests in index order

#### Scenario: Refused calls
- **WHEN** `u1.zone_connection(9, "direct")`, `u1.zone_connection("", "solid")`, a second `u1.zone_connection(9, "thermal")` after `u1.zone_connection(9, "solid")`, and `u1.zone_connection(9, "thermal", index=0)` after it are called
- **THEN** each call raises `DslError`, the last two naming `U1` and `9`

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change

### Requirement: Pad zone connections in a build
`lens.build.build_design` SHALL accept the keyword-only argument `pad_zones: Mapping[str, Sequence[PadZoneRequestLike]]`, empty by default, and SHALL apply the requests of each component to the built copy of its footprint with `fenolite.backends.kicad.zones.apply_pad_connections(instance, requests, *, where="", issues=None) -> FootprintInstance`, `where` being the component path that an issue names, after placing and before the build checks and `Design.validate()`; `cli/cmd_build.py` SHALL pass `dsl.pad_zones(design)`.
- `PadZoneRequestLike` is a structural protocol with the attributes of `PadZoneRequest`, so `zones.py` never imports the DSL.
- A request MUST set `Pad.zone_connection` of every pad it names: all pads of the footprint with that number, or the one at `index` among them. A pad that no request names keeps the value of the library footprint.
- A request whose number no pad carries, or whose index is beyond the pads that carry it, MUST give `kicad.pad.zone-unknown-pad` (error) naming the part, the number and the index; `build_design` then returns no files, so `build` exits 5 and writes nothing.
- The board writer writes the value as `(zone_connect N)` (`kicad-file-backend`, "Pad zone connection"). Nothing else of the build changes: a call without `pad_zones` MUST behave as before, and `--seed`, `--timestamp` and `PYTHONHASHSEED` MUST NOT change any file of a build with requests.
- With an existing board, `layout-lens`, "Pad zone connections across rebuilds", decides the pads of kept footprints.
- `zones.PAD_ZONE_ISSUE_CODES` MUST be the closed table of the codes of this requirement and of that one. They are `kicad.*` codes, so they pass through `BUILD_ISSUE_CODES` and `PRESERVE_ISSUE_CODES` unchanged, as "Build issue codes" allows.

| code | severity | when |
|---|---|---|
| `kicad.pad.zone-unknown-pad` | error | a request names a pad number or index that the footprint does not have |
| `kicad.pad.zone-forced` | warning | a locked request replaced the setting that a pad of a kept footprint carries |
| `kicad.pad.zone-overridden` | info | an unlocked request differs from the setting that a pad of a kept footprint carries, which stays |

- `--target altium` MUST NOT read the requests, as it does not read field requests; `docs/dsl.md` MUST say so, and MUST describe the call, the four values and the rebuild rule under "Zones".
- The evidence of the build does not change: the written child is covered by the board writer's evidence, and its effect on a fill by `H-K-ZONE-CONNECT`. That a pad which differs from its library pad only by this child raises no library mismatch in KiCad's DRC is `H-K-PAD-ZONE-LIB`.

#### Scenario: Solid exposed pad
- **GIVEN** a blink pour variant in which `d1.zone_connection(1, "solid")` is called
- **WHEN** it is built with `--dry-run --json` for target 10 and the planned board is read with `read_board`
- **THEN** the exit code is 0, pad `1` of `D1` has `zone_connection == "solid"`, its other pad has `None`, and the board text holds `(zone_connect 2)` exactly once

#### Scenario: Unknown pad stops the build
- **GIVEN** the same variant with `d1.zone_connection(7, "solid")`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` hold one `kicad.pad.zone-unknown-pad` naming `D1` and `7`, and nothing is written

#### Scenario: Builds with requests are reproducible
- **WHEN** `uv run pytest tests/unit/lens/test_build_pad_zones.py -k reproducible` builds the variant twice for target 9 and target 10 with different seeds and `PYTHONHASHSEED` values
- **THEN** both builds write every file with the same bytes

#### Scenario: KiCad reports no library mismatch
- **WHEN** `uv run pytest tests/kicad/zones/test_pad_zone_requests.py` builds the variant once per connection value, with its vendored library in place, and runs `pcb drc` on 9.0.9 and on 10.0.6
- **THEN** each run writes a report that holds no `lib_footprint_mismatch` and no violation naming pad `1` of `D1`, and the probe `pad-zone-lib` records `absent` on both majors (`H-K-PAD-ZONE-LIB`)

#### Scenario: Closed code table
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pad_zones.py -k closed_set` collects every code that `apply_pad_connections` and `keep_pad_connections` produce in their tests
- **THEN** each is a key of `PAD_ZONE_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

### Requirement: Net aliases in the DSL
`Design.moved_net(old, new)` SHALL record that the net named `new` was named `old` in an earlier build, and `dsl.net_moves(design) -> Mapping[str, str]` SHALL return the recorded net aliases, new name → old name, in name order; `fenolite.dsl` SHALL re-export `net_moves` (an addition under "DSL package").
- `old` and `new` MUST be non-empty strings. `old == new`, or a second alias with the same `old` or the same `new`, MUST raise `DslError` at the call.
- `net_moves(design)` MUST raise `DslError` when `new` is not the name of a net of the design, or when `old` is, because the old net's copper would move to the new one. Chains are therefore refused.
- `cmd_build` MUST turn such a `DslError` into `DesignScriptError` (`FEN-3004`, exit 3).
- Net aliases are not model data: `to_model` MUST give the same model with and without them.
- A net alias is needed for one build only: the build writes the copper under the new name (`layout-lens`, "Copper items follow their nets").

#### Scenario: Net alias recorded
- **GIVEN** a design holding the net `LED_ANODE` and `d.moved_net("LED_A", "LED_ANODE")`
- **WHEN** `net_moves(d)` is called
- **THEN** it returns `{"LED_ANODE": "LED_A"}`

#### Scenario: Old net still present
- **GIVEN** a design holding the nets `VIN` and `VBUS`, and `d.moved_net("VIN", "VBUS")`
- **WHEN** `net_moves(d)` is called
- **THEN** `DslError` is raised naming `VIN`

#### Scenario: Model unchanged by net aliases
- **GIVEN** the blink design with and without `d.moved_net("LED_X", "LED_A")`
- **WHEN** `canonical.dump_texts(to_model(d))` is computed for both
- **THEN** the texts are equal

### Requirement: Placements file in a build
`cmd_build` SHALL read `<script folder>/placements.toml` when it exists and pass its entries to the layout lens as `source`, as "Build command" allows for added steps and `result` keys.
- The file MUST be read with `lens.placements.read_placements(text, origin=dsl.BOARD_ORIGIN, file="placements.toml")`; a `FormatError` MUST exit 3 (`FEN-3004`) before any planned write.
- Its `layout.source-invalid` issues MUST be reported, and an error among them MUST stop the build as any other build error does (exit 5, nothing written).
- Without `--discard-layout`, the entries MUST be passed to `prepare` as `source`. With `--discard-layout`, `cmd_build` MUST call `prepare` with an `ExistingProject` whose three texts are `None` and the same `source`, so no file of the output folder is read and the file still applies ("Placement precedence").
- With `--target altium`, the placements passed on MUST be those that `prepare` gives with an `ExistingProject` whose texts are `None` and the same `source`, so both targets place a part from the file.
- `result.preserved.source` MUST hold `file` (`placements.toml`, or `null` when no file was read), `used` (component paths that took their placement from the file), `stale` and `unknown` (paths of `layout.source-stale` and `layout.source-unknown`); "Layout preservation evidence" allows the key.
- `.fenolite/build.json` MUST record the SHA-256 of the file that was read, so `check` can tell that the layout's source changed.

#### Scenario: File places a part
- **GIVEN** a blink variant whose `R1` has no `place()`, and a `placements.toml` beside its script with `[part."R1"]`, `x = 20`, `y = 10`
- **WHEN** it is built into an empty folder with `--confirm --json`
- **THEN** `R1` is at (120 mm, 110 mm), `issues` hold no `layout.unplaced`, and `result.preserved.source.used` is `["R1"]`

#### Scenario: File survives a discarded layout
- **GIVEN** a confirmed blink build in `B` edited by `edit_blink`, and a `placements.toml` written by `fenolite sync --to-source --confirm`
- **WHEN** the blink is built again with `--discard-layout --confirm`
- **THEN** `D1` is 4 mm right of its `place()` position, the segments and the via of the edit are gone, and `issues` hold one `layout.place-overridden` naming `D1`

#### Scenario: Invalid file stops the build
- **GIVEN** a `placements.toml` whose `R1` table has `side = "left"`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5, `issues` hold `layout.source-invalid` naming `R1` and `side`, and nothing is written

### Requirement: Drawing sheet and title block in the DSL
`Design.sheet(paper="A4", *, portrait=False, width=None, height=None, drawing_sheet=None)` and `Design.title_block(*, title="", date="", revision="", organization="", doc_id="", responsible="", approver="", variables={})` SHALL record the board's sheet and title block, each at most once; a second call MUST raise `DslError`.
- `paper`, `portrait`, `width` and `height` MUST follow the model's `SheetFrameRef` rules; `width` and `height` are lengths, given together for a user paper.
- `drawing_sheet` MUST be a path relative to the folder of the design script, ending in `.kicad_wks` or `.sheet.toml`; any other ending, an absolute path, or a path leaving that folder MUST raise `DslError`.
- `variables` MUST map text-variable names to string values; a name that does not match the model's parameter-name rule MUST raise `DslError`.
- `dsl.to_model` MUST set `Board.sheet` to the `SheetFrameRef` of the call, with `drawing_sheet` equal to `"<design name>.kicad_wks"` when a drawing sheet is given, and `Board.title_block` to the `TitleBlock` of the call with `params` from `variables`. The source path MUST NOT enter the model; `dsl.drawing_sheet_source(design)` MUST return it, or `None`.
- A design without these calls MUST give the model it gave before this requirement.

#### Scenario: Sheet and title block in the model
- **GIVEN** `d.sheet("A3", drawing_sheet="frames/company.kicad_wks")` and `d.title_block(title="Blink", revision="B", variables={"PROJECT_CODE": "X1"})` in the blink script
- **WHEN** `to_model(d)` runs
- **THEN** `Board.sheet` is `SheetFrameRef("A3", drawing_sheet="blink.kicad_wks")`, `Board.title_block.title` is `Blink`, its `revision` is `B`, its `params` hold `PROJECT_CODE`, and `drawing_sheet_source(d)` is `frames/company.kicad_wks`

#### Scenario: Wrong file type
- **WHEN** `d.sheet(drawing_sheet="frame.pdf")` is called
- **THEN** `DslError` is raised naming `frame.pdf`

### Requirement: Drawing sheets in a build
`fenolite build` SHALL write the drawing sheet that the script names as `<name>.kicad_wks` beside the project, as "Built project files" allows for added steps of `build_design` and added files.
- `cmd_build` MUST read the source: a `.kicad_wks` with `wks.read_drawing_sheet(text, file=<name of the source>)`, a `*.sheet.toml` with the reader of `sheet-templates` and `build_sheet`. A missing or unreadable source MUST exit 3 (`FEN-3001` or `FEN-3004`) before any planned write, because KiCad would fall back to its default frame without a word (`H-K-WKS-FALLBACK`). The reader's infos MUST be reported.
- `build_design` MUST add `<name>.kicad_wks` from `wks.write_drawing_sheet(<the sheet>, target=target, allow_lossy=allow_lossy)`; its errors MUST stop the build with its codes, as other writers do.
- The file MUST be recorded in `.fenolite/build.json` and MUST follow "Edited outputs are not overwritten".
- The project MUST name it through `apply_sheet_keys`, for the board and, when the build writes a schematic, for the schematic (`kicad-file-backend`, "Projects carry the drawing sheet and text variables").
- On a rebuild over an existing board, the paper and the title block that the script declares MUST be written from the script; a board whose script declares neither keeps its own (`layout-lens`, "Board content outside the design is kept").
- `result.drawing_sheet` MUST hold `source` (the path given in the script), `file` (`<name>.kicad_wks`) and `items` (the number of drawn items), or be `null` without a drawing sheet.

#### Scenario: User sheet in a built project
- **GIVEN** the blink script with `d.sheet(drawing_sheet="frame.kicad_wks")` and an authored `frame.kicad_wks` beside it whose root is the legacy `page_layout`
- **WHEN** it is built for target 9 with `--confirm --json`
- **THEN** `receipt.written` lists `blink.kicad_wks`, whose root is `kicad_wks` with the header `(version 20231118)`, `blink.kicad_pro` holds `pcbnew.page_layout_descr_file` `blink.kicad_wks`, and `issues` hold the info `kicad.wks.legacy-root`

#### Scenario: Missing source
- **GIVEN** the same script without `frame.kicad_wks`
- **WHEN** it is built with `--dry-run`
- **THEN** the exit code is 3, stderr carries `FEN-3001` naming `frame.kicad_wks`, and nothing is planned

#### Scenario: Schematic gets the frame
- **GIVEN** c0061 archived and the same script with the file present
- **WHEN** it is built with a schematic
- **THEN** `blink.kicad_pro` holds `schematic.page_layout_descr_file` `blink.kicad_wks` too

