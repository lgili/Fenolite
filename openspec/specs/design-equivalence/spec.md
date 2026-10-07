# design-equivalence Specification

## Purpose
Decide whether two designs are equivalent at four levels (components, netlist as REF-PIN sets, footprints and pads, placement) with stated tolerances, normalisation and exclusion lists, and report each difference with its location. It defines `fenolite equivalent` and the triangle oracle that compares Fenolite's own read of an Altium PCB document with `kicad-cli`'s import of the same file.
## Requirements
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

### Requirement: Level 1 compares components
Level 1 SHALL compare the components of `Design.circuit.components` by their `ref`.
- A reference matching one of the `ignore_refs` globs (`fnmatch.fnmatchcase`) MUST be left out on both sides and counted in the summary as `ignored`.
- An empty reference, and a reference that a side holds more than once, MUST give one `ref-ambiguous` difference per reference, with the two counts as `a` and `b`.
- A reference held by one side only MUST give `component-missing`, with the other side's value empty.
- For each reference both sides hold once, `value` and `dnp` MUST be compared.
- `LevelResult.compared` MUST be the count of references both sides hold once.

#### Scenario: Missing and changed components
- **GIVEN** side `a` with `R1` (`10k`), `R2` (`1k`) and `C1`, and side `b` with `R1` (`10k`), `R2` (`2k2`) and `D1`
- **WHEN** level 1 runs
- **THEN** it reports `component-missing` for `C1` and for `D1`, and `value` for `R2` with `a` `1k` and `b` `2k2`, and `compared` is 2

#### Scenario: Duplicate references are not compared
- **GIVEN** side `a` holding the reference `REF**` twice and side `b` holding it once
- **WHEN** levels 1 to 4 run, and then again with `ignore_refs=("REF[*][*]",)`
- **THEN** the first run reports exactly one difference for `REF**`, of kind `ref-ambiguous`, and the second reports none and counts `ignored`

### Requirement: Level 2 compares the netlist as REF-PIN sets
Level 2 SHALL compare the net-to-pin assignments of the two sides as partitions of `REF-PIN` elements, with `fenolite.checks.assignment_compare.compare(a, b, min_pins=1)` and c0020's `PadNetList`. It MUST NOT compare net names and MUST NOT hold a second partition algorithm.
- **Source per side.** A side whose board holds at least one footprint MUST give `assignment_compare.board_netlist(design)`; any other side MUST give `assignment_compare.model_netlist(design)`. The summary MUST name the source of each side (`board` or `circuit`) and the count of unnumbered pads, which are not compared.
- **Scope.** Only elements of the components that level 1 compared take part.
- **Pins.** An element that only one side holds MUST give `pin-missing`. c0020's coverage infos are not used: at this level an element that one side lacks is a difference.
- **Nets.** Each `assignment_compare.Difference` MUST give one `net` difference, with the net names of each side as `a` and `b` (`no net` for a pad on no net).
- Pads on no net form one class, as in c0020. Single-pin nets take part.
- The summary MUST count `renamed`: the blocks that are equal on both sides and whose net names differ. A renamed net is never a difference.

#### Scenario: Reassigned pad is located
- **GIVEN** the two-layer design and a copy in which one pad of one footprint has the `net_id` of another net
- **WHEN** level 2 runs
- **THEN** it reports exactly one difference, of kind `net`, whose `where` is that pad's `REF-PIN`, and `difference_issues` gives one `netlist.assignment-differs` error

#### Scenario: Renamed nets are equivalent
- **GIVEN** the two-layer design and a copy in which every net has another name and another id
- **WHEN** level 2 runs
- **THEN** it reports no difference and `summary["renamed"]` equals the count of nets

#### Scenario: Circuit against board
- **GIVEN** a design without footprints whose circuit holds the nets of the two-layer board, and the two-layer design
- **WHEN** levels 1 and 2 run
- **THEN** no difference is reported and the summary names the sources `circuit` and `board`

#### Scenario: Pin on one side only
- **GIVEN** a copy of the two-layer design in which one footprint lost one numbered pad
- **WHEN** level 2 runs
- **THEN** it reports one `pin-missing` difference for that `REF-PIN` and no `net` difference for it

### Requirement: Level 3 compares footprints and pads
Level 3 SHALL compare, for each component that level 1 compared, the `FootprintInstance` whose `component_id` is that component, in the footprint's own frame.
- A component placed on one side only MUST give `footprint-missing`. A component placed on neither side is not compared at this level. When a component holds several footprints, the first by `(position.x, position.y, id)` is compared.
- The footprint names MUST be compared under "Tolerances and normalisation".
- **Pad pairing.** The pads of each footprint are grouped by `number`. Inside a group they are sorted by `(position.x, position.y)` and paired in that order. Groups of different sizes MUST give one `pad-missing` difference for the number, with the two counts as `a` and `b`, and the pads of that group are not compared further.
- **Pad fields.** Each pair MUST be compared on `kind`, `shape`, `size`, `drill`, `position`, `rotation` and copper span, under "Tolerances and normalisation". `Pad.position` and `Pad.rotation` are footprint-local, as `docs/design-model.md` ("Pad frame") defines them; the footprint's own position, rotation and side take no part.
- `Pad.padstack`, mask and paste layers, custom outlines, footprint graphics, attributes and 3D models are not compared.
- `LevelResult.compared` MUST be the count of pad pairs compared.

#### Scenario: Changed pad is located
- **GIVEN** the two-layer design and a copy in which one pad is 100 nm wider and its drill is absent on one side only
- **WHEN** level 3 runs at tolerance 0 and at `length_nm=100`
- **THEN** the first run reports `pad-size` and `pad-drill` for that `REF-PIN`, and the second reports only `pad-drill`

#### Scenario: Placement does not reach level 3
- **GIVEN** the two-layer design and a copy with one footprint moved, rotated by `90_000_000` and flipped to the other side with its pads unchanged
- **WHEN** `compare_designs(a, b, level=3)` runs
- **THEN** it reports no difference

#### Scenario: Two pads of one number
- **GIVEN** footprints with two pads numbered `1` on side `a` and three on side `b`
- **WHEN** level 3 runs
- **THEN** it reports one `pad-missing` difference with `a` `2` and `b` `3`, and no other difference for pads numbered `1`

#### Scenario: Unknown layer name
- **GIVEN** a pad whose `layers` hold a name that `Board.layers` lacks
- **WHEN** level 3 runs
- **THEN** no `pad-copper` difference is reported for it and `summary["copper_unknown"]` is 1

### Requirement: Level 4 compares placement
Level 4 SHALL compare, for each footprint pair that level 3 compared, `side`, `position` and `rotation`.
- `side` MUST be compared exactly, `position` in the chosen frame, and `rotation` with period `360_000_000`, under "Tolerances and normalisation".
- `locked`, attributes and text positions are not compared.
- `LevelResult.compared` MUST be the count of footprint pairs, and the summary MUST hold `frame` and `translation`.

#### Scenario: Moved footprint is located
- **GIVEN** the two-layer design and a copy with one footprint moved by 1 nm on x and rotated by 1 µdeg
- **WHEN** level 4 runs at tolerance 0, and then with `Tolerances(length_nm=1, angle_udeg=1)`
- **THEN** the first run reports `position` and `rotation` for that reference only, and the second reports nothing

#### Scenario: Flipped footprint
- **GIVEN** a copy with one footprint on the other side
- **WHEN** level 4 runs with any tolerance
- **THEN** it reports a `side` difference with `a` `top` and `b` `bottom`

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

### Requirement: Board import runner
`fenolite.backends.kicad.cli.KicadCli.import_board(source, *, format="altium")` SHALL run `kicad-cli pcb import --format <format> --report-format json --report-file import.json -o imported.kicad_pcb <name>` on a copy of `source` in the runner's temporary folder and return an `ImportRun(run, board, report)`.
- `board` MUST be the bytes of the written board, or `None` when none was written. `report` MUST be the parsed JSON object of the report, or `None` when no report was written or it is not a JSON object.
- It MUST raise `KicadCliVersionError` when the running major is below 10, through the runner's existing check for 10.0-only commands, and MUST NOT run the tool then.
- It MUST write nothing next to `source` and MUST use the runner's isolation and time limit (`kicad-oracle`, "Isolation and time limits").
- `fenolite.backends.kicad.altium_import` SHALL provide `import_design(cli, source) -> ImportedDesign`, which runs `import_board`, reads the written board with `backends.kicad.pcb.read_board` and returns the read result, the run's messages with the temporary folder replaced by `<tmp>`, and the tool version; and `exclusions_text() -> str`, the text of `src/fenolite/backends/kicad/data/altium_import_exclusions.toml`. The module MUST import nothing from `fenolite.backends.altium` or `fenolite.checks`.

#### Scenario: Import of the committed document
- **GIVEN** `kicad-cli` 10.0 and `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** `uv run pytest tests/kicad/equivalence/test_import_runner.py` runs `import_design`
- **THEN** the design holds three footprints with the references `U1`, `R1` and `D1`, the report is a JSON object, and the folder of the source is unchanged

#### Scenario: Refused on 9.0
- **GIVEN** a fake `kicad-cli` whose `version` prints `9.0.9`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_import_board.py` calls `import_board`
- **THEN** it raises `KicadCliVersionError` naming 10.0, and the fake records no `pcb import` call

#### Scenario: Tool writes no board
- **GIVEN** a fake `kicad-cli` 10.0 that exits 0 and writes nothing
- **WHEN** `import_board` runs
- **THEN** `board` and `report` are `None`, and `import_design` raises `KicadCliError`

### Requirement: Triangle oracle
`fenolite equivalent A --against kicad-import` SHALL compare Fenolite's own read of an Altium PCB document with `kicad-cli`'s import of the same file.
- Side `a` MUST be `registry.for_path(A).read(A)`, and `A` MUST be a file that c0043's Altium backend detects as a PCB document; any other input MUST exit 2 with `FEN-2001`.
- Side `b` MUST be `altium_import.import_design(cli, A)`. `result.sides.b.backend` MUST be `kicad-import`, `result.sides.b.tool_version` the running version, `result.sides.b.path` the name of `A` and `result.sides.b.sha256` `null` (the converted board holds identifiers that change between runs).
- A missing `kicad-cli` MUST exit 6 with `FEN-6001`, and a major other than 10 MUST exit 6 with `FEN-6002` and a hint naming 10.0. Neither runs an import.
- A run that writes no board, or a board the KiCad backend refuses, MUST give one `equiv.oracle-failed` error with the sanitised message and exit 5; no level runs, and `result` holds `level` 0, `equivalent` `false`, an empty `levels` list and `sides.b` `null`.
- The profile MUST be `select_profile(load_profiles(altium_import.exclusions_text()), "kicad-import", version)`. When it is `None`, the comparison MUST run with no rule, `frame="relative"` and tolerance 0, and one `equiv.no-exclusion-profile` warning MUST name the version.
- The envelope evidence MUST be `Evidence.combine` of the two reads, with `oracle` `kicad-cli`.
- Messages of the import report with severity warning or error MUST be reported as infos `equiv.import-message`, counted by text, with temporary paths replaced.

#### Scenario: Triangle on the committed document
- **GIVEN** `kicad-cli` 10.0
- **WHEN** `uv run fenolite equivalent tests/data/altium/blink/blink.PcbDoc --against kicad-import --json` runs
- **THEN** the exit code is 0, `result.level` is 4, `result.frame` is `relative`, `result.profile.name` is `kicad-import`, and `evidence.oracle` is `kicad-cli`

#### Scenario: No kicad-cli 10
- **GIVEN** a fake `kicad-cli` 9.0.9 passed with `--kicad-cli`
- **WHEN** `fenolite equivalent tests/data/altium/blink/blink.PcbDoc --against kicad-import` runs
- **THEN** the exit code is 6 and stderr carries `FEN-6002`

#### Scenario: Version without a profile
- **GIVEN** a fake `kicad-cli` that reports `10.9.0` and copies a prepared board as its import
- **WHEN** the command runs
- **THEN** one `equiv.no-exclusion-profile` warning names `10.9.0` and `result.profile` is `null`

### Requirement: Importer exclusion list per version
`src/fenolite/backends/kicad/data/altium_import_exclusions.toml` SHALL hold one profile named `kicad-import` per `kicad-cli` version line that the triangle was measured on, starting with `10.0`.
- Each rule MUST describe one behaviour of KiCad's importer, observed on a named corpus row or on the committed document, with a `hypothesis` registered in `docs/hypotheses.md` and a `reason` in Fenolite's own words.
- `attribution` MUST be `importer` only when a public source or the importer's own report shows that KiCad's importer makes the change. It MUST be `undecided` when the two reads differ and no public source says which is right.
- A difference that Fenolite's reader or adapter causes MUST NOT get a rule: it is fixed, with a regression test under `tests/unit/backends/altium/`.
- The profile's `frame` MUST be `relative` (KiCad moves an imported board on its sheet), and its `tolerance_nm` MUST be the smallest multiple of 10 that the measurement needs, with the measured maximum recorded in `docs/evidence/equivalence-triangle.md`.
- Every rule MUST match at least one difference in the corpus run; a rule that matches nothing fails the test, so the list cannot go stale. A row that `kicad-cli` cannot import on the running platform (a recorded failure of KiCad's own importer) is not judged there.
- A rule selects by level, kind, field and a glob over `where`. Where the importer's behaviour depends on a property of a pad that a rule cannot see (its layer, its shape), the glob names the pads of the corpus rows it was observed on.
- `docs/formats/kicad/cli.md` MUST gain a section "Importer differences" with one fact row per rule (`| fact | source | label | hypothesis |`).

#### Scenario: Rules are live
- **GIVEN** `kicad-cli` 10.0 and the fetched corpus documents
- **WHEN** `uv run pytest tests/kicad/equivalence/test_triangle_corpus.py -k rules_are_live` runs
- **THEN** every rule of the `10.0` profile matched on each row of its `corpus` list that was imported, and on no other row

#### Scenario: Rule facts are documented
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_exclusion_data.py` runs
- **THEN** the data file loads, every rule's hypothesis is a row of `docs/hypotheses.md`, and every rule id appears once in `docs/formats/kicad/cli.md`

### Requirement: Triangle evidence over the corpus
`tests/kicad/equivalence/test_triangle_corpus.py` SHALL run the triangle at levels 1 to 4 on every corpus row with the use `altium-pcbdoc` (the PCB document rows of c0041, `altium-pcb-reader`, "Altium PCB corpus rows"; this change adds no row and no use), and `tests/kicad/equivalence/test_triangle_blink.py` SHALL run it on `tests/data/altium/blink/blink.PcbDoc`.
- Both files MUST carry `needs_kicad` and `kicad_min_major(10)`; the corpus file MUST also carry `needs_corpus`.
- A row on which `kicad-cli` writes no board MUST be skipped by its row id and listed in the evidence page with the exit code, as c0041's reader oracle does.
- For each document and level the test MUST assert that no difference remains outside the profile's rules, and MUST print the counts `compared`, `differences` and `excluded`.
- A reference that a document holds several times (the empty reference of pads that belong to no component, a designator given to several components) cannot be paired and gets no rule: the test leaves such references out by name (`ignore_refs`), asserts their counts on both sides, and the evidence page lists them per row.
- `docs/evidence/equivalence-triangle.md` MUST record, per `kicad-cli` version, corpus row id and level: the counts, the translation, the largest position difference after the translation, and the rules that matched. Rows are named by corpus id and licence only.
- A level counts as `ORACLE-VERIFIED(kicad-cli)` for a document only when no `undecided` rule matched at that level or below. `H-G-EQ-L1` to `H-G-EQ-L4` record the result per level, and the result of `H-A-UNIT` gains the position difference measured between the two models, next to the record-level figure of c0041.
- No corpus document is committed, and no content of one appears in the repository beyond counts.

#### Scenario: Corpus triangle
- **GIVEN** `kicad-cli` 10.0 and the corpus rows fetched with `uv run python tools/corpus_fetch.py --uses altium-pcbdoc`
- **WHEN** `uv run pytest tests/kicad/equivalence/test_triangle_corpus.py -s` runs
- **THEN** it passes for every row that `kicad-cli` imports at levels 1 to 4 and prints one line of counts per row and level

#### Scenario: Skipped below 10
- **GIVEN** `FENOLITE_REQUIRE=kicad` and `kicad-cli` 9.0.9
- **WHEN** `uv run pytest tests/kicad/equivalence` runs
- **THEN** every test is skipped with a reason naming 10 and 9, and the run exits 0

#### Scenario: Evidence page matches the data
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_exclusion_data.py -k evidence_page` runs
- **THEN** every rule id and every `kicad-cli` version line of the data file appears in `docs/evidence/equivalence-triangle.md`

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
- `equiv.route-unjudged` (info): a net whose pads are joined only through an unfilled zone on either side; such a net gives no other difference. Its issue MUST carry a `hint` that names the unfilled zone as the cause, says that an open connection may be hidden, and says to fill the zones and compare again.
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

