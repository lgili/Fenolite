## ADDED Requirements

### Requirement: Routed connectivity of a net
`fenolite.checks.equivalence.routing.pieces(design)` SHALL return, for each net of a design with a board, the connected pieces of its copper: tracks, arcs, vias, the filled polygons of zones and the pads of the net, joined when two of them touch on a shared copper layer by the exact touch test of the copper check.
- Each `Piece` MUST hold `pads` (the sorted `REF-PAD` elements it contains), `vias` (the count per pair of copper spans) and `lengths` (the routed length of its tracks and arcs per copper span, in nanometres; an arc counts its true length).
- A copper span MUST be named `top` for the copper layer of the lowest ordinal, `bottom` for the highest and `inner<k>` for the `k`-th copper layer between them, so that two boards whose layers have other names compare. A through via spans `top`–`bottom`.
- A pad's copper MUST be shaped from the model alone, in the board frame of `docs/design-model.md` ("Pad frame"), on each copper layer of `Pad.layers`: a disc for `circle`, a stadium for `oval`, and the rectangle of its size for every other shape (a superset of a `roundrect`, `trapezoid` or `custom` pad). An `np_thru_hole` pad has no copper. A pad without a number joins copper and gives no element.
- The length of a span MUST be the sum of the piece's tracks on it, where the tracks that lie on one line are added exactly and their sum is rounded once to the nearest nanometre, and of its arcs, each from its three points and rounded half to even. Copper drawn twice counts twice.
- An unfilled zone MUST NOT join anything, and the number of unfilled zones MUST be returned: the result is a mapping from net id to pieces that also holds `zones_unfilled`, the ids of the nets that hold an unfilled zone, and the counts of copper items without a net and of items that could not be shaped.
- The result MUST NOT depend on the order of the items, and splitting a track at a point of itself MUST NOT change it.
- The module MUST import only `core`, `model`, `geometry` and other `checks` modules.

#### Scenario: Two pads joined through a via
- **GIVEN** a net with a pad on the top layer, a track to a via, and a track on the bottom layer to a second pad
- **WHEN** `pieces` runs
- **THEN** the net has one piece with both pads, one via for the pair top–bottom, and a length on each of the two layers

#### Scenario: An open connection
- **GIVEN** the same net with the bottom track removed
- **WHEN** `pieces` runs
- **THEN** the net has two pieces, one with the first pad and the via, one with the second pad alone

#### Scenario: Re-segmented track
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_routing.py -k split_invariance` splits and joins the tracks of generated boards
- **THEN** the pieces of each board are unchanged

### Requirement: Level 5 compares routing per net
`level_routing(a, b, pairing, tolerances)` SHALL compare the pieces of the nets that level 2 pairs, and SHALL report each difference with one code, located by the net's name on side `a` and the pads involved.
- `equiv.route-missing` (error): one side has copper on the net and the other has none.
- `equiv.route-connectivity` (error): the multisets of the pad sets of the pieces differ; `where` names the first pad set on one side only.
- `equiv.route-vias` (error): for equal pad sets, the via counts per span pair differ.
- `equiv.route-length` (error): for equal pad sets, a length per copper span differs by more than `max(length_nm, length × length_ppm / 1_000_000)`.
- `equiv.route-stub` (warning): the pieces without a pad differ in number or in total length beyond the tolerance.
- `equiv.route-unjudged` (info): a net whose pads are joined only through an unfilled zone on either side; such a net gives no other difference.
- `pairing` MUST hold the pairs of net ids whose `REF-PIN` blocks are equal at level 2 and the elements both sides hold; a net that level 2 reported is not compared again, and the summary counts the nets of each side that no pair holds. Pads outside those elements give no element at this level.
- The four error kinds MUST be judged in the order above; `route-missing` and `route-connectivity` end the judgement of a net. `route-stub` and `route-unjudged` are notices (`LevelResult.notices`): they are reported and located, and they never make two designs unequal.
- A net is unjudged when a side holds an unfilled zone on it and more than one piece of it.
- The comparison rule (the kinds, their order and what each compares) MUST be one table of `routing.py`, so that another rule can be added beside it without a change to `pieces`.
- Copper spans MUST be compared as level 3 compares them. The level summary MUST hold the nets compared, the pieces, the vias, the total length per side and `zones_unfilled`.

#### Scenario: A faithful copy
- **GIVEN** the routed two-layer board and a copy written and re-read by the KiCad backend
- **WHEN** level 5 runs
- **THEN** it reports no difference

#### Scenario: Five planted edits
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_level5.py -k planted` removes a track, removes a via, moves a track to another layer, opens a connection and deletes a net's copper, one at a time
- **THEN** each run reports one difference, of the code `equiv.route-connectivity`, `equiv.route-vias`, `equiv.route-length`, `equiv.route-connectivity` and `equiv.route-missing` in that order, naming the net

### Requirement: Level 5 in the equivalent command
`fenolite equivalent` SHALL accept `--level 5`, and `max_level` SHALL be 5 when both sides hold at least one track, arc or via.
- `--tolerance-ppm N` (a non-negative integer, default 0) MUST set the relative length tolerance; a profile MAY supply it.
- `--level 5` when a side holds no copper MUST exit 2 with `FEN-2001` naming that side. A level above 5 MUST exit 2.
- `result.levels` MUST hold the object of level 5 with its counts and summary, and the differences of the level MUST follow the rules of the command for issues, exclusions and exit code.

#### Scenario: Routed board against itself
- **WHEN** `fenolite equivalent routed.kicad_pcb routed.kicad_pcb --json` runs on a routed board
- **THEN** the exit code is 0, `result.level` is 5, and `result.levels` holds five objects with `differences` 0

#### Scenario: Unrouted side
- **WHEN** `fenolite equivalent routed.kicad_pcb unrouted.kicad_pcb --level 5` runs
- **THEN** the exit code is 2 and the message names the second side

### Requirement: Level 5 over the triangle
The triangle oracle of c0045 SHALL run at level 5 on routed boards: the KiCad board, the Altium PCB document that Fenolite writes from it and KiCad's import of that document MUST be pairwise equal at level 5 within the tolerances of the triangle's profile, and `docs/evidence/equivalence-triangle.md` MUST hold the boards, the tolerances and every exclusion with its cause.

#### Scenario: Samples and corpus boards
- **WHEN** `uv run pytest tests/kicad/equivalence/test_triangle_level5.py -rA` runs with KiCad 10.0.6 and the corpus cached
- **THEN** every pair is equal at level 5, and the probe `equiv-l5-triangle` records `equal`

## MODIFIED Requirements

### Requirement: Equivalence package
The package `fenolite.checks.equivalence` SHALL compare two `fenolite.model.design.Design` values and SHALL hold the modules `model.py`, `norm.py`, `levels.py`, `routing.py`, `exclusions.py` and `codes.py`.
- It MUST import only the standard library, `fenolite.core`, `fenolite.model`, `fenolite.geometry`, `fenolite.backends.base` and `fenolite.checks`. It MUST name no backend: no string `kicad` or `altium` appears in its code outside docstrings.
- `fenolite.checks.equivalence` MUST re-export `LEVELS`, `LEVEL_NAMES`, `Tolerances`, `Difference`, `Excluded`, `LevelResult`, `EquivalenceReport`, `compare_designs`, `max_level`, `difference_issues`, `Rule`, `Profile`, `load_profiles`, `select_profile` and `EQUIVALENCE_CODES`.
- `LEVELS` MUST be `(1, 2, 3, 4, 5)` and `LEVEL_NAMES` MUST map them to `components`, `netlist`, `footprints`, `placement` and `routing`.
- `compare_designs(a, b, *, level, tolerances=Tolerances(), frame="absolute", ignore_refs=(), rules=())` MUST run the levels 1 to `level` in order and return an `EquivalenceReport` with one `LevelResult` per level run. A `level` outside `LEVELS` MUST raise `ValueError`.
- `max_level(a, b)` MUST return 5 when both designs hold a board with at least one footprint and at least one track, arc or via, 4 when both hold a board with at least one footprint, and 2 otherwise. `compare_designs` with a `level` above `max_level(a, b)` MUST raise `ValueError` naming the side without footprints, or the side without copper when only level 5 is out of reach.
- The comparison MUST be pure: it reads no file, runs no tool and uses no float.

#### Scenario: Layering holds
- **GIVEN** the modules of `src/fenolite/checks/equivalence/`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py tests/unit/checks/equivalence/test_package.py` runs
- **THEN** both pass, with no change to `ALLOWED`, and the AST check finds no `float` call, no float literal and no backend name

#### Scenario: A design compared with itself
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `compare_designs(d, d, level=4)` runs
- **THEN** the report holds four level results, each with no difference, and `report.equivalent` is `True`

#### Scenario: Level above what both sides hold
- **GIVEN** a design whose board has no footprint and the two-layer design
- **WHEN** `compare_designs(a, b, level=3)` runs
- **THEN** it raises `ValueError` whose message names side `a`

### Requirement: Differences are located
Every difference SHALL be a `Difference(level, kind, where, field, a, b)`.
- `where` MUST be the component reference `REF` at levels 1 and 4 and for footprint kinds, and `REF-PIN` (the reference, `-`, the pin or pad number) for pin and pad kinds. A pad without a number MUST give `REF-` followed by `@<x>,<y>`, its footprint-local position in nanometres. At level 5 `where` MUST be the net's name on side `a`, followed, for a kind that concerns one pad set, by `:` and the first three pads of the set joined by `,` (then `,+<n>` for the `n` pads left out).
- `a` and `b` MUST be the two values as strings: text verbatim, lengths as decimal integers of nanometres, points as `<x>,<y>`, sizes as `<w>x<h>`, angles as decimal integers of microdegrees, a missing object as the empty string.
- The kinds and their levels MUST be exactly those of this table.

| level | kind | field | meaning |
|---|---|---|---|
| 1 | `component-missing` | `ref` | a reference that only one side holds |
| 1 | `ref-ambiguous` | `ref` | a reference that a side holds more than once, or an empty reference |
| 1 | `value` | `value` | `Component.value` differs |
| 1 | `dnp` | `dnp` | `Component.dnp` differs |
| 2 | `pin-missing` | `pin` | a `REF-PIN` of a common component that only one side holds |
| 2 | `net` | `net` | a `REF-PIN` whose net block differs |
| 3 | `footprint-missing` | `footprint` | a common component that is placed on one side only |
| 3 | `footprint-name` | `lib_ref` | the footprint names differ |
| 3 | `pad-missing` | `pad` | the two footprints hold different counts of pads of one number |
| 3 | `pad-kind` | `kind` | `Pad.kind` differs |
| 3 | `pad-shape` | `shape` | `Pad.shape` differs |
| 3 | `pad-size` | `size` | the sizes differ beyond the tolerance |
| 3 | `pad-drill` | `drill` | the drills differ beyond the tolerance, or only one pad has a drill |
| 3 | `pad-position` | `position` | the footprint-local positions differ beyond the tolerance |
| 3 | `pad-rotation` | `rotation` | the footprint-relative rotations differ beyond the tolerance |
| 3 | `pad-copper` | `layers` | the copper spans differ |
| 4 | `side` | `side` | `FootprintInstance.side` differs |
| 4 | `position` | `position` | the positions differ beyond the tolerance, in the chosen frame |
| 4 | `rotation` | `rotation` | the rotations differ beyond the tolerance |
| 5 | `route-missing` | `copper` | one side has copper on the net and the other has none |
| 5 | `route-connectivity` | `pads` | the copper of the net joins other pad sets |
| 5 | `route-vias` | `vias` | the via counts per pair of copper spans differ for one pad set |
| 5 | `route-length` | `length` | a routed length per copper span differs beyond the tolerance for one pad set |
| 5 | `route-stub` | `stubs` | the pieces without a pad differ in number or in total length (a notice) |
| 5 | `route-unjudged` | `zones` | the net's connectivity depends on an unfilled zone (a notice) |

- The differences of a level MUST be sorted by `(where, kind, field)` in code-point order, so that equal inputs give equal output.
- A component reported as `component-missing` or `ref-ambiguous` MUST NOT be compared at any level, and a component reported as `footprint-missing` MUST NOT be compared further at levels 3 and 4: each fault is reported once.
- `difference_issues(report)` MUST return one `Issue` of severity `error` per difference that no rule excludes, with `where` as above. Its code MUST be `netlist.assignment-differs` for kind `net` (c0020's code, built with `checks.codes.issue`) and `equiv.<kind>` for every other kind. It MUST then return one `Issue` per notice of a level (`LevelResult.notices`) that no rule excludes, of code `equiv.<kind>` and of severity `warning` for `route-stub` and `info` for `route-unjudged`; a notice is located as a difference is and never makes `EquivalenceReport.equivalent` false. `EQUIVALENCE_CODES` (also named `ISSUE_CODES` in `codes.py`, the name by which `fenolite explain` finds issue-code tables) MUST map each `equiv.*` code this capability emits to its severities, including `equiv.excluded` (info), `equiv.import-message` (info), `equiv.no-exclusion-profile` (warning) and `equiv.oracle-failed` (error).

#### Scenario: Kinds table is closed
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_codes.py` runs
- **THEN** the kinds of `levels.py` equal the table above, each `equiv.*` code matches `fenolite.core.errors.ISSUE_CODE`, and `docs/equivalence.md` lists the same kinds

#### Scenario: Output order is stable
- **GIVEN** two designs with differences on `R2`, `R10` and `C1`
- **WHEN** `compare_designs` runs twice, the second time with the footprints of both designs in reverse order
- **THEN** both reports are equal, and the level-1 differences come in the order `C1`, `R10`, `R2`

### Requirement: Tolerances and normalisation
`Tolerances(length_nm=0, angle_udeg=0, length_ppm=0)` SHALL hold three non-negative integers; a negative value or a non-integer MUST raise `ValueError`. The rules of `norm.py` MUST be these, in integer arithmetic only:
- **Length.** Two lengths are equal when the absolute value of their difference is at most `length_nm`. Two points are equal when both coordinates are; no Euclidean distance is taken. Two sizes are equal when both axes are.
- **Routed length.** Two routed lengths `p` and `q` of level 5 are equal when the absolute value of their difference is at most `max(length_nm, max(p, q) × length_ppm // 1_000_000)`. `length_ppm` applies to nothing else.
- **Angle.** `normalise(angle)` is `angle mod 360_000_000`, in `[0, 360_000_000)`. `angle_distance(a, b, period)` is `min(d, period - d)` with `d = (a - b) mod period`. Two angles are equal when their distance is at most `angle_udeg`. The period is `360_000_000` unless a rule below says otherwise.
- **Side.** `top` and `bottom` are compared exactly. No tolerance applies.
- **Text.** Values, references, pin numbers and footprint names are compared as exact strings; no case folding and no trimming.
- **Footprint name.** The compared name is the part of `FootprintInstance.lib_ref` after its last `:`, or the whole text when it has none.
- **Pad rotation by shape.** A `circle` pad, and an `oval` pad whose two sizes are equal within the tolerance, has no rotation: the field is not compared. A `rect`, `oval` or `roundrect` pad is compared with period `180_000_000`, and it MUST also be equal to a pad whose size axes are swapped and whose rotation differs by `90_000_000` modulo `180_000_000`; in that case neither `pad-size` nor `pad-rotation` is reported. A `trapezoid` or `custom` pad is compared with period `360_000_000`. When the two pads of a pair have different shapes, the field is not compared if either has no rotation, and the smaller of the two periods applies otherwise.
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

#### Scenario: Board moved as a whole
- **GIVEN** a design with three footprints and a copy with every footprint moved by `(5_000_000, -3_000_000)` and one of them moved by a further `(1_000_000, 0)`
- **WHEN** level 4 runs with `frame="relative"` and then with `frame="absolute"`
- **THEN** the first run reports the translation `(5_000_000, -3_000_000)` and exactly one `position` difference, for the footprint moved further, and the second run reports a `position` difference for every footprint

#### Scenario: Bad tolerance
- **WHEN** `Tolerances(length_nm=-1)` is built
- **THEN** it raises `ValueError`

### Requirement: Exclusion lists
`exclusions.py` SHALL read exclusion profiles from TOML text with `load_profiles(text, *, file="")`, and `compare_designs` SHALL apply the `rules` it is given.
- **File.** The root MUST hold `schema = 1` and `[[profile]]` tables. A profile MUST hold `name`, `tool`, `tool_version`, `frame` (`absolute` or `relative`), `tolerance_nm`, `tolerance_udeg` and zero or more `[[profile.rule]]` tables, and MAY hold `tolerance_ppm` (a non-negative integer, 0 when absent). A rule MUST hold `id` (unique in the file), `level`, `kind` (a kind of that level), `where` (an `fnmatch` glob over the difference's `where`), `attribution` (`importer` or `undecided`), `reason` and `hypothesis`, and MAY hold `field` and `corpus` (a list of corpus row ids). Any other key, a missing key, a kind of another level or a duplicate id MUST raise `FormatError` naming the file and the rule.
- **Selection.** `select_profile(profiles, name, tool_version)` MUST return the profile of that name whose `tool_version` is the longest prefix of the given version at a dot boundary (`10.0` matches `10.0.6` and not `10.01`), or `None`.
- **Effect.** A difference that a rule matches (level, kind, glob and, when given, field) MUST be moved from `LevelResult.differences` to `LevelResult.excluded` as `Excluded(difference, rule_id, reason)`, `reason` being the rule's reason. The first matching rule in file order wins. An excluded difference never makes `EquivalenceReport.equivalent` false. A notice of level 5 that a rule matches MUST be moved to `excluded` in the same way.
- A rule MUST NOT stop a comparison: the level still runs and still reports the other differences of the same component.
- `difference_issues` MUST add one `equiv.excluded` info per rule that matched, with the count and the rule's reason.

#### Scenario: Rule excludes and reports
- **GIVEN** two designs whose only differences are `footprint-name` on `R1` and `value` on `R2`, and a rule of level 3, kind `footprint-name`, `where` `R*`
- **WHEN** `compare_designs(..., level=4, rules=(rule,))` runs
- **THEN** level 3 has no difference and one `Excluded` naming the rule, level 1 keeps the `value` difference, and `report.equivalent` is `False`

#### Scenario: Version prefix
- **GIVEN** profiles named `kicad-import` for `tool_version` `10` and `10.0`
- **WHEN** `select_profile` runs for `10.0.6`, for `10.1.0` and for `11.0.0`
- **THEN** it returns the `10.0` profile, the `10` profile and `None`

#### Scenario: Malformed rule
- **GIVEN** a file whose rule has `level = 1` and `kind = "pad-size"`
- **WHEN** `load_profiles` runs
- **THEN** it raises `FormatError` naming the rule id

### Requirement: Equivalent command
`fenolite equivalent A [B]` SHALL be registered by `src/fenolite/cli/cmd_equivalent.py` with `mutates=False`. It SHALL compare two designs and write no file under either input.
- **Sides.** Each of `A` and `B` MUST be one of:
  - a `.fenolite/` folder, recognised by a file `meta.json` or `build.json` directly inside it, read with `model.canonical.load_dir` (a built design);
  - a `.kicad_pro` file or a folder, resolved with `backends.kicad.projectset.resolve_board` and then read as a board;
  - any other file, read with `registry.for_path(path).read(path)`: a KiCad board, or whatever c0043's Altium backend reads (a PCB document, a schematic document, a project file).

  A path no backend detects MUST exit 2 with `FEN-2001`. A missing path MUST exit 3 with `FEN-3001`. A read that returns a library MUST exit 2 with `FEN-2001`. A reader error keeps its own code.
- **Options.** `--level N` (1 to 5; the default is `max_level` of the two sides), `--tolerance-nm N`, `--tolerance-udeg N` and `--tolerance-ppm N` (non-negative integers, default 0), `--frame absolute|relative` (default `absolute`), `--ignore-ref GLOB` (repeatable), `--exclusions FILE` with `--profile NAME`, `--against kicad-import`, `--kicad-cli PATH` and `--timeout SECONDS` (default 300). A level above `max_level`, a bad value, `--exclusions` without `--profile` or the reverse, a profile the file lacks, and `B` together with `--against` or neither of them, and `--exclusions` or `--profile` together with `--against`, MUST exit 2 with `FEN-2001`; the message for a level names the side without footprints, or without copper for level 5, and the highest level available.
- **Profile defaults.** A selected profile supplies `frame`, `tolerance_nm`, `tolerance_udeg` and `tolerance_ppm`; an option given on the command line overrides the profile's value.
- **Result.** `result` MUST hold `level`, `equivalent`, `sides` (`a` and `b`, each with `path` as the name without its folder, `sha256` for a file, `backend`, `netlist_source`, `components` and `footprints`), `tolerances` (`length_nm`, `angle_udeg`, `length_ppm`), `frame`, `translation`, `levels` (one object per level run with `level`, `name`, `compared`, `differences`, `excluded` and `notices` as counts, and `summary`), `differences`, `notices` and `excluded` (lists of objects with `level`, `kind`, `where`, `field`, `a`, `b`, and `rule` for excluded ones) and `profile` (`null`, or `name`, `tool_version` and the count of rules).
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

### Requirement: Equivalence documentation
`docs/equivalence.md` SHALL describe the five levels, the routed pieces of level 5, the kinds table, the tolerance and normalisation rules, the frame, the exclusion file format and the triangle, and `docs/cli-contract.md` SHALL gain a section `equivalent` with the options, the result keys, the issue codes and the exit codes.
- `docs/roadmap.md` MUST mark levels 1 to 4 as delivered by c0045 and level 5 as delivered by c0089, and no page MUST say that level 5 is not built.
- `fenolite capabilities --json` MUST list `equivalent` with `mutates` `false`.

#### Scenario: Codes are documented
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_codes.py -k docs` runs
- **THEN** every code of `EQUIVALENCE_CODES` appears in `docs/cli-contract.md` and every kind in `docs/equivalence.md`

#### Scenario: Command is discoverable
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result.commands` holds an entry named `equivalent` with `mutates` `false` and `schema` `fenolite.equivalent.v0`
