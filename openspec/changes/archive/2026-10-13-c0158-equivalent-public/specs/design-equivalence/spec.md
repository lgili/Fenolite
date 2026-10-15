## ADDED Requirements

### Requirement: Public equivalence API
The package `fenolite.api` SHALL provide `equivalent(a, b, *, level=None, tolerances=None, frame=None, ignore_refs=(), profile=None, against=None, kicad_cli=None, timeout=300.0) -> EquivalenceResult`. It MUST read the sides as "Equivalent command" describes, run `compare_designs` at the highest level both sides hold when `level` is `None`, and return an `EquivalenceResult` with `report`, `a`, `b`, `profile`, `issues` and `evidence`, whose `to_json()` MUST return the command's `result`.

#### Scenario: Same reply as the command
- **WHEN** `uv run pytest tests/unit/api/test_equivalence_api.py -k same_as_cli` calls `equivalent` and runs `fenolite equivalent --json` on the two-layer board and its copy with one footprint moved
- **THEN** `to_json()` of the call equals `result` of the reply, and the issues are equal in order

### Requirement: Public equivalence API inputs
`a` and `b` of `fenolite.api.equivalent` MUST each be a path (a `str` or a `Path`) of any side that `fenolite equivalent` reads, or a `fenolite.model.design.Design`; `b` MUST be `None` exactly when `against` is `"kicad-import"`.
- A `Design` given directly MUST be a side with `backend` `model`, `sha256` `None` and the evidence `INFERRED`.
- Usage faults MUST raise `ValueError`, which the command maps to `FEN-2001`.

#### Scenario: Two models
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb` and the same design with one value changed
- **WHEN** `fenolite.api.equivalent(d, changed)` runs
- **THEN** `result.report.equivalent` is `False`, the one difference is `value` at the component's reference, and both sides have `backend` `model`

#### Scenario: Usage fault
- **WHEN** `fenolite.api.equivalent(d, None)` runs without `against`
- **THEN** it raises `ValueError` naming `b`

### Requirement: Public API errors and effects
`fenolite.api.equivalent` SHALL keep the types and codes of reader errors and of the triangle's tool errors, SHALL write no file, and SHALL run no subprocess unless `against` is given or a schematic side needs `kicad-cli`. `import fenolite` MUST NOT import `fenolite.api`.

#### Scenario: Hermetic call
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and a snapshot of the folder of the two-layer board
- **WHEN** `uv run pytest tests/unit/api/test_equivalence_api.py -k hermetic` calls `equivalent` on the board and itself
- **THEN** the call returns an equivalent report and the folder is unchanged

### Requirement: Schematic sides
A side whose path ends in `.kicad_sch` SHALL be read, with the sheets that its tree names in its folder, into a `Design` that holds a circuit and no board. `max_level` of such a side MUST be 2, and its `netlist_source` MUST be `schematic`. Its evidence MUST be that of the own netlist, or `ORACLE-VERIFIED(kicad-cli)` for the exported one ("Schematic side netlist").

#### Scenario: Level above a schematic side
- **WHEN** `fenolite equivalent proj.kicad_sch proj.kicad_pcb --level 3` runs
- **THEN** the exit code is 2 with `FEN-2001`, and the message names side `a` and the highest level, 2

### Requirement: Schematic side netlist
The netlist of a schematic side SHALL be `sch_netlist.own_netlist` when `sch_netlist.grammar_issues` reports nothing for the tree, and otherwise the netlist that `oracle.export_schematic_netlist` reads from `kicad-cli sch export netlist`; without a `kicad-cli` that path MUST exit 6 with `FEN-6001`.
- Each netlist component MUST give one component with its reference and value; each netlist net one net with its `REF-PIN` members.

#### Scenario: Generated schematic, no tool
- **GIVEN** a project built for target 10 from the blink design, and `subprocess.run` patched to raise
- **WHEN** `uv run pytest tests/unit/api/test_equivalence_api.py -k schematic_own` compares `<project>/blink.kicad_sch` with `<project>/blink.kicad_pcb`
- **THEN** the comparison runs levels 1 and 2 and reports no difference

#### Scenario: Hand-drawn schematic through kicad-cli
- **GIVEN** a demo schematic of the corpus whose sheets fail the grammar check, and `kicad-cli` 9.0.9 or 10.0.6
- **WHEN** `uv run pytest tests/kicad/equivalence/test_schematic_side.py -rA` compares it with the board of the same demo project
- **THEN** levels 1 and 2 run with `netlist_source` `schematic` on side `a`, and the probe `equiv-schside` records the outcome

### Requirement: Power symbols of a schematic side
A schematic side SHALL hold no component for a power symbol (a symbol whose reference starts with `#`), which KiCad's netlist and Fenolite's own one leave out (`H-K-NETLIST-SHAPE`); a netlist component whose reference starts with `#` MUST be left out too. The side's `power_symbols` MUST be the number of distinct such references of its sheets.

#### Scenario: Power symbol left out
- **GIVEN** the built blink project, whose sheet holds power symbols
- **WHEN** `uv run pytest tests/unit/api/test_equivalence_api.py -k power` reads `blink.kicad_sch` as a side
- **THEN** no component of the side's circuit has a reference starting with `#`, and its `power_symbols` is the number of `#` references of the sheet

### Requirement: Fitted flag of a schematic side
The do-not-populate flag of a component of a schematic side SHALL come from the field that `H-K-EQ-SCHSIDE` names: a `comp` of the exported netlist that holds a `property` named `dnp` is not fitted, and for the own netlist the `dnp` attribute of the component's symbol, which KiCad exports as that property, gives the flag. Level 1 MUST compare it as for any other side.

#### Scenario: Flag read
- **GIVEN** a netlist export whose `D1` holds `(property (name "dnp"))`, read as side `a`, and side `b` with `D1` fitted
- **WHEN** `uv run pytest tests/unit/api/test_equivalence_api.py -k dnp` runs level 1
- **THEN** one `dnp` difference is reported at `D1`, `true` on side `a` and `false` on side `b`

### Requirement: Equivalent result schema
`schemas/fenolite.equivalent.v0.json` SHALL be a JSON Schema of the `result` object of `fenolite equivalent`: every key of "Equivalent command" with its type, `additionalProperties` false on every object, and the kinds of difference as the closed list of `docs/equivalence.md`. `tests/consistency` MUST validate the `result` of every command for which a file `schemas/fenolite.<name>.v0.json` exists.

#### Scenario: Reply validates
- **WHEN** `uv run pytest tests/consistency -k equivalent` runs the command's `example_args`
- **THEN** the envelope validates against the envelope schema and `result` against `fenolite.equivalent.v0.json`

#### Scenario: Unknown key refused
- **GIVEN** a reply whose `result` gains a key `extra`
- **WHEN** it is validated against the schema
- **THEN** validation fails naming `extra`

## MODIFIED Requirements

### Requirement: Equivalent command
`fenolite equivalent A [B]` SHALL be registered by `src/fenolite/cli/cmd_equivalent.py` with `mutates=False`. It SHALL compare two designs and write no file under either input. It SHALL read its sides and compare them through `fenolite.api.equivalent` ("Public equivalence API"), and its `result` SHALL be `EquivalenceResult.to_json()` of that call.
- **Sides.** Each of `A` and `B` MUST be one of:
  - a `.fenolite/` folder, recognised by a file `meta.json` or `build.json` directly inside it, read with `model.canonical.load_dir` (a built design);
  - a `.kicad_pro` file or a folder, resolved with `backends.kicad.projectset.resolve_board` and then read as a board;
  - a root KiCad schematic, a file ending in `.kicad_sch`, read with its sheet tree into a circuit ("Schematic sides");
  - any other file, read with `registry.for_path(path).read(path)`: a KiCad board, or whatever c0043's Altium backend reads (a PCB document, a schematic document, a project file).

  A path no backend detects MUST exit 2 with `FEN-2001`. A missing path MUST exit 3 with `FEN-3001`. A read that returns a library MUST exit 2 with `FEN-2001`. A reader error keeps its own code.
- **Options.** `--level N` (1 to 5; the default is `max_level` of the two sides), `--tolerance-nm N`, `--tolerance-udeg N` and `--tolerance-ppm N` (non-negative integers, default 0), `--frame absolute|relative` (default `absolute`), `--ignore-ref GLOB` (repeatable), `--exclusions FILE` with `--profile NAME`, `--against kicad-import`, `--kicad-cli PATH` and `--timeout SECONDS` (default 300). A level above `max_level`, a bad value, `--exclusions` without `--profile` or the reverse, a profile the file lacks, and `B` together with `--against` or neither of them, and `--exclusions` or `--profile` together with `--against`, MUST exit 2 with `FEN-2001`; the message for a level names the side without footprints, or without copper for level 5, and the highest level available.
- **Profile defaults.** A selected profile supplies `frame`, `tolerance_nm`, `tolerance_udeg` and `tolerance_ppm`; an option given on the command line overrides the profile's value.
- **Result.** `result` MUST validate against `schemas/fenolite.equivalent.v0.json` ("Equivalent result schema") and MUST hold `level`, `equivalent`, `sides` (`a` and `b`, each with `path` as the name without its folder, `sha256` for a file, `backend`, `netlist_source` (`board`, `circuit` or `schematic`), `components` and `footprints`), `tolerances` (`length_nm`, `angle_udeg`, `length_ppm`), `frame`, `translation`, `levels` (one object per level run with `level`, `name`, `compared`, `differences`, `excluded` and `notices` as counts, and `summary`), `differences`, `notices` and `excluded` (lists of objects with `level`, `kind`, `where`, `field`, `a`, `b`, and `rule` for excluded ones) and `profile` (`null`, or `name`, `tool_version` and the count of rules).
- **Issues and exit.** `issues` MUST be `difference_issues(report)`, then the notices of the triangle (`equiv.no-exclusion-profile`, `equiv.import-message`), then the readers' warnings and infos of both sides. The exit code MUST be 5 when any difference is not excluded and 0 otherwise.
- **Evidence.** The envelope evidence MUST be `Evidence.combine` of the two reads' evidence; a built design counts as `INFERRED`.
- **Determinism.** The output MUST hold no absolute path and no temporary path, and two runs on the same inputs MUST be equal except `elapsed_ms`.
- `example_args` MUST be `(EXAMPLE_BOARD, EXAMPLE_BOARD, "--level", "4")`, which runs no subprocess.

#### Scenario: A board equals itself
- **WHEN** `uv run fenolite equivalent tests/data/kicad/board/two_layer.kicad_pcb tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.equivalent` is `true`, `result.level` is 5 (the board holds tracks), and `result.levels` holds five objects with `differences` 0

#### Scenario: Differences give exit 5
- **GIVEN** a copy of the two-layer board, written with the KiCad backend, in which one footprint is moved by 1 mm and one pad is on another net
- **WHEN** `fenolite equivalent two_layer.kicad_pcb copy.kicad_pcb --json` runs
- **THEN** the exit code is 5, stdout holds a `netlist.assignment-differs` error whose `where` is the pad's `REF-PIN` and an `equiv.position` error whose `where` is the footprint's reference, and the same run with `--level 1` exits 0

#### Scenario: Built design against its board
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`
- **WHEN** `fenolite equivalent <project>/.fenolite <project> --json` runs
- **THEN** the exit code is 0, `result.sides.a.backend` is `fenolite`, and `result.sides.b.backend` is `kicad`

#### Scenario: Two backends, one design
- **GIVEN** the KiCad board built from the blink design of `tests/_altium.py::blink` and the committed `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** `uv run pytest tests/unit/cli/test_equivalent_cmd.py -k two_backends` runs `equivalent` on them with `--frame relative` and the tolerances the test names
- **THEN** levels 1 to 4 report no difference outside the differences the test lists by kind with their cause, and no subprocess runs

#### Scenario: Usage errors
- **WHEN** `fenolite equivalent a.kicad_pcb` runs without `B` and without `--against`, and `fenolite equivalent a.kicad_pcb b.kicad_pcb --level 6` runs
- **THEN** both exit 2 with `FEN-2001`

#### Scenario: Read-only and hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and a snapshot of both input folders
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py tests/unit/cli/test_equivalent_cmd.py -k "hermetic or readonly"` runs `equivalent` with its `example_args`
- **THEN** the exit code is 0 and both folders are unchanged

#### Scenario: Consistency suite
- **WHEN** `uv run pytest tests/consistency` runs from a temporary working directory
- **THEN** it passes for `equivalent`


#### Scenario: Schematic against an Altium project
- **GIVEN** the KiCad project built from the blink design of `tests/_altium.py::blink` and the committed `tests/data/altium/blink/blink.PrjPcb`
- **WHEN** `fenolite equivalent <project>/blink.kicad_sch tests/data/altium/blink/blink.PrjPcb --json` runs
- **THEN** `result.level` is 2, `result.sides.a.netlist_source` is `schematic`, no difference is reported outside those that `tests/unit/cli/test_equivalent_cmd.py -k schematic_two_backends` lists by kind with their cause, and no subprocess runs (the sheets pass the grammar check of the own netlist)


### Requirement: Tolerances and normalisation
`Tolerances(length_nm=0, angle_udeg=0, length_ppm=0)` SHALL hold three non-negative integers; a negative value or a non-integer MUST raise `ValueError`. The rules of `norm.py` MUST be these, in integer arithmetic only:
- **Length.** Two lengths are equal when the absolute value of their difference is at most `length_nm`. Two points are equal when both coordinates are; no Euclidean distance is taken. Two sizes are equal when both axes are.
- **Routed length.** Two routed lengths `p` and `q` of level 5 are equal when the absolute value of their difference is at most `max(length_nm, max(p, q) × length_ppm // 1_000_000)`. `length_ppm` applies to nothing else.
- **Angle.** `normalise(angle)` is `angle mod 360_000_000`, in `[0, 360_000_000)`. `angle_distance(a, b, period)` is `min(d, period - d)` with `d = (a - b) mod period`. Two angles are equal when their distance is at most `angle_udeg`. The period is `360_000_000` unless a rule below says otherwise.
- **Side.** `top` and `bottom` are compared exactly. No tolerance applies.
- **Text.** Values, references, pin numbers and footprint names are compared as exact strings; no case folding and no trimming.
- **Footprint name.** The compared name is the part of `FootprintInstance.lib_ref` after its last `:`, or the whole text when it has none.
- **Pad rotation by shape.** A `circle` pad, and an `oval` pad whose two sizes are equal within the tolerance, has no rotation: the field is not compared. A `rect`, `oval` or `roundrect` pad is compared with period `180_000_000`, and it MUST also be equal to a pad whose size axes are swapped and whose rotation differs by `90_000_000` modulo `180_000_000`; in that case neither `pad-size` nor `pad-rotation` is reported. A `trapezoid` or `custom` pad is compared with period `360_000_000`. When the two pads of a pair have different shapes, the field is not compared if either has no rotation, and the smaller of the two periods applies otherwise.
- **Pad shape.** `shape_class(pad, tolerances)` is `circle` for an `oval` pad whose two sizes are equal within `length_nm`, and `Pad.shape` otherwise. `pad-shape` MUST compare the two classes, so an equal-sized `oval` and a `circle` of that size are the same shape; their sizes are still compared.
- **Copper span.** A pad's copper span is the subset of `{top, inner, bottom}` its `layers` reach: a layer name is looked up in `Board.layers`; a `copper` layer with the lowest ordinal among copper layers is `top`, with the highest `bottom`, any other `inner`. Layers of another kind are ignored. A layer name that `Board.layers` lacks makes the span unknown, and an unknown span is not compared and is counted in the level summary as `copper_unknown`.
- **Frame.** With `frame="absolute"` the translation is `(0, 0)`. With `frame="relative"` the translation is `(median_low(dx), median_low(dy))` over the components compared at level 4, with `dx` and `dy` the position of side `b` minus that of side `a`; it is `(0, 0)` when no component is compared. A position differs when `b - a - translation` exceeds the length tolerance on either axis. The report MUST hold the translation.
- No rotation or mirror of a whole board is removed.

#### Scenario: Angle wraps
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_norm.py -k angle` runs
- **THEN** `angle_distance(359_999_999, 0, 360_000_000)` is 1, `normalise(-90_000_000)` is `270_000_000`, and two rotations of `-90_000_000` and `270_000_000` are equal at tolerance 0

#### Scenario: Length tolerance is per coordinate
- **GIVEN** two points that differ by 10 nm on x and 10 nm on y
- **WHEN** they are compared with `Tolerances(length_nm=10)` and with `Tolerances(length_nm=9)`
- **THEN** they are equal in the first case and different in the second

#### Scenario: Rectangular pad turned by a quarter
- **GIVEN** a `rect` pad of `1000000x500000` at rotation 0 and a `rect` pad of `500000x1000000` at rotation `90_000_000`
- **WHEN** level 3 compares them at tolerance 0
- **THEN** no `pad-size` and no `pad-rotation` difference is reported, and the same pads at rotations 0 and `45_000_000` give one `pad-rotation` difference

#### Scenario: Equal-sized oval is a circle
- **GIVEN** an `oval` pad of `1600000x1600000` on side `a` and a `circle` pad of `1600000x1600000` with the same number on side `b`
- **WHEN** level 3 runs at tolerance 0
- **THEN** no `pad-shape` difference is reported, and the same `oval` of `1600000x1700000` gives one `pad-shape` difference `oval`/`circle`

#### Scenario: Board moved as a whole
- **GIVEN** a design with three footprints and a copy with every footprint moved by `(5_000_000, -3_000_000)` and one of them moved by a further `(1_000_000, 0)`
- **WHEN** level 4 runs with `frame="relative"` and then with `frame="absolute"`
- **THEN** the first run reports the translation `(5_000_000, -3_000_000)` and exactly one `position` difference, for the footprint moved further, and the second run reports a `position` difference for every footprint

#### Scenario: Bad tolerance
- **WHEN** `Tolerances(length_nm=-1)` is built
- **THEN** it raises `ValueError`

