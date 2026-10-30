## MODIFIED Requirements

### Requirement: Equivalence package
The package `fenolite.checks.equivalence` SHALL compare two `fenolite.model.design.Design` values and SHALL hold the modules `model.py`, `norm.py`, `levels.py`, `routing.py`, `strict.py`, `rules.py`, `shapes.py`, `drawn.py`, `exclusions.py` and `codes.py`.
- It MUST import only the standard library, `fenolite.core`, `fenolite.model`, `fenolite.geometry`, `fenolite.backends.base` and `fenolite.checks`. It MUST name no backend: no string `kicad` or `altium` appears in its code outside docstrings.
- `fenolite.checks.equivalence` MUST re-export `LEVELS`, `LEVEL_NAMES`, `Tolerances`, `Difference`, `Excluded`, `LevelResult`, `EquivalenceReport`, `compare_designs`, `max_level`, `difference_issues`, `Rule`, `Profile`, `load_profiles`, `select_profile`, `EQUIVALENCE_CODES`, `PRESENTATION_LEVEL`, `SCHEMATIC_LEVEL`, `compare_drawn` and `accepted_rules`.
- `LEVELS` MUST be `(1, 2, 3, 4, 5, 6, 7)` and `LEVEL_NAMES` MUST map them to `components`, `netlist`, `footprints`, `placement`, `routing`, `rules` and `geometry`. `PRESENTATION_LEVEL` MUST be `8` (named `presentation`) and `SCHEMATIC_LEVEL` MUST be `"S"` (named `schematic`); `compare_designs` runs neither: level 8 renders ("Level 8 compares rendered presentation") and level S compares drawn schematics (`compare_drawn`).
- `compare_designs(a, b, *, level, tolerances=Tolerances(), frame="absolute", ignore_refs=(), rules=(), strict=False)` MUST run the levels 1 to `level` in order, level 5 with the item rule of "Level 5 strict compares copper items" too when `strict` is true, and return an `EquivalenceReport` with one `LevelResult` per level run. A `level` outside `LEVELS` MUST raise `ValueError`.
- `max_level(a, b)` MUST return 5 when both designs hold a board with at least one footprint and at least one track, arc or via, 4 when both hold a board with at least one footprint, and 2 otherwise; it never returns 6 or 7. Levels 6 and 7 MUST be available when both designs hold a board with at least one footprint, and level 7 then also compares level 5 when both sides hold copper. `compare_designs` with a `level` of 5 or less above `max_level(a, b)`, or with level 6 or 7 when a side has no footprint, MUST raise `ValueError` naming the side without footprints, or the side without copper when only level 5 is out of reach.
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

#### Scenario: Levels 6 and 7 on request
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `compare_designs(d, d, level=7, strict=True)` runs
- **THEN** the report holds seven level results, each with no difference, and `max_level(d, d)` is still 5

### Requirement: Differences are located
Every difference SHALL be a `Difference(level, kind, where, field, a, b)`, whose `level` is an `int` of 1 to 8 or the text `S`.
- `where` MUST be the component reference `REF` at levels 1 and 4 and for footprint kinds, and `REF-PIN` (the reference, `-`, the pin or pad number) for pin and pad kinds. A pad without a number MUST give `REF-` followed by `@<x>,<y>`, its footprint-local position in nanometres. At level 5 `where` MUST be the net's name on side `a`, followed, for a kind that concerns one pad set, by `:` and the first three pads of the set joined by `,` (then `,+<n>` for the `n` pads left out).
- At the strict kinds of level 5 and at levels 6 to 8 and S, `where` MUST be the form that "Level 5 strict compares copper items", "Level 6 compares rules", "Level 7 compares exact geometry", "Level 8 compares rendered presentation" and "Level S compares drawn schematics" give.
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
| 5 | `track-missing` | `track` | strict: a track that only one side holds |
| 5 | `track-width` | `width` | strict: matched tracks of different widths |
| 5 | `track-net` | `net` | strict: matched tracks on nets of different names |
| 5 | `arc-missing` | `arc` | strict: an arc that only one side holds |
| 5 | `arc-width` | `width` | strict: matched arcs of different widths |
| 5 | `arc-net` | `net` | strict: matched arcs on nets of different names |
| 5 | `via-missing` | `via` | strict: a via that only one side holds |
| 5 | `via-size` | `diameter` | strict: matched vias of different diameters |
| 5 | `via-drill` | `drill` | strict: matched vias of different drills |
| 5 | `via-span` | `layers` | strict: matched vias of different copper spans or types |
| 5 | `via-net` | `net` | strict: matched vias on nets of different names |
| 5 | `copper-locked` | `locked` | strict: matched items whose lock differs (a notice) |
| 6 | `netclass-missing` | `name` | a net class that only one side holds |
| 6 | `netclass-field` | the field | a field of a net class differs |
| 6 | `netclass-members` | `nets` | the nets assigned to a net class differ |
| 6 | `rule-missing` | `name` | a custom rule that only one side holds |
| 6 | `rule-field` | the field | a field of a custom rule differs |
| 6 | `ruleset-field` | the field | a board-wide rule or minimum differs |
| 6 | `stackup-missing` | `layer` | a stack-up layer that only one side holds, or out of order |
| 6 | `stackup-field` | the field | a field of a stack-up layer, or the finish, differs |
| 6 | `layer-missing` | `layer` | a board layer of one kind and ordinal that only one side holds |
| 7 | `outline-missing` | `ring` | an outline ring, cut-out or slot that only one side holds |
| 7 | `zone-missing` | `zone` | a zone outline that only one side holds |
| 7 | `zone-field` | the field | a field of matched zones differs (never the fill) |
| 7 | `keepout-missing` | `keepout` | a rule area that only one side holds |
| 7 | `keepout-field` | the field | a field of matched rule areas differs |
| 7 | `graphic-missing` | `graphic` | a board or footprint graphic that only one side holds |
| 7 | `text-missing` | `text` | a board or footprint text that only one side holds |
| 7 | `text-field` | the field | a field of matched texts differs |
| 7 | `field-pose` | the field | a field of a footprint field (reference, value, user field) differs |
| 7 | `hole-missing` | `hole` | a board hole that only one side holds |
| 7 | `dimension-missing` | `dimension` | a dimension that only one side holds |
| 8 | `render-missing` | `layer` | a layer or sheet that only one side renders |
| 8 | `render-pixels` | `pixels` | a layer or sheet whose rendered masks differ beyond the pixel tolerance |
| S | `sheet-missing` | `sheet` | a sheet instance that only one side holds |
| S | `symbol-missing` | `symbol` | a symbol unit that only one side draws |
| S | `symbol-pose` | the field | the position, rotation or mirror of a matched symbol differs |
| S | `symbol-field` | the field | the pose of a field of a matched symbol differs |
| S | `item-missing` | the item kind | a wire, bus, bus entry, junction, no-connect flag, label, power symbol, sheet reference, sheet pin or opaque item that only one side holds |
| S | `item-field` | the field | a field of a matched label, sheet reference or sheet pin differs |
| S | `drawn-net` | `net` | the drawn connectivity differs (a `REF-PIN` in another group) |

- The differences of a level MUST be sorted by `(where, kind, field)` in code-point order, so that equal inputs give equal output.
- A component reported as `component-missing` or `ref-ambiguous` MUST NOT be compared at any level, and a component reported as `footprint-missing` MUST NOT be compared further at levels 3 and 4: each fault is reported once.
- `difference_issues(report)` MUST return one `Issue` of severity `error` per difference that no rule excludes, with `where` as above. Its code MUST be `netlist.assignment-differs` for kind `net` (c0020's code, built with `checks.codes.issue`) and `equiv.<kind>` for every other kind. It MUST then return one `Issue` per notice of a level (`LevelResult.notices`) that no rule excludes, of code `equiv.<kind>` and of severity `warning` for `route-stub` and `copper-locked` and `info` for `route-unjudged`; a notice is located as a difference is and never makes `EquivalenceReport.equivalent` false. `EQUIVALENCE_CODES` (also named `ISSUE_CODES` in `codes.py`, the name by which `fenolite explain` finds issue-code tables) MUST map each `equiv.*` code this capability emits to its severities, including `equiv.excluded` (info), `equiv.import-message` (info), `equiv.no-exclusion-profile` (warning) and `equiv.oracle-failed` (error).

#### Scenario: Kinds table is closed
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_codes.py` runs
- **THEN** the kinds of `levels.py` equal the table above, each `equiv.*` code matches `fenolite.core.errors.ISSUE_CODE`, and `docs/equivalence.md` lists the same kinds

#### Scenario: Output order is stable
- **GIVEN** two designs with differences on `R2`, `R10` and `C1`
- **WHEN** `compare_designs` runs twice, the second time with the footprints of both designs in reverse order
- **THEN** both reports are equal, and the level-1 differences come in the order `C1`, `R10`, `R2`

### Requirement: Equivalent command
`fenolite equivalent A [B]` SHALL be registered by `src/fenolite/cli/cmd_equivalent.py` with `mutates=False`. It SHALL compare two designs and write no file under either input. It SHALL read its sides and compare them through `fenolite.api.equivalent` ("Public equivalence API"), and its `result` SHALL be `EquivalenceResult.to_json()` of that call.
- **Sides.** Each of `A` and `B` MUST be one of:
  - a `.fenolite/` folder, recognised by a file `meta.json` or `build.json` directly inside it, read with `model.canonical.load_dir` (a built design);
  - a `.kicad_pro` file or a folder, resolved with `backends.kicad.projectset.resolve_board` and then read as a board;
  - a root KiCad schematic, a file ending in `.kicad_sch`, read with its sheet tree into a circuit ("Schematic sides");
  - any other file, read with `registry.for_path(path).read(path)`: a KiCad board, or whatever c0043's Altium backend reads (a PCB document, a schematic document, a project file).

  A path no backend detects MUST exit 2 with `FEN-2001`. A missing path MUST exit 3 with `FEN-3001`. A read that returns a library MUST exit 2 with `FEN-2001`. A reader error keeps its own code.
- **Options.** `--level N` (1 to 8 or `S`; the default is `max_level` of the two sides; levels 6 to 8 and S follow "Levels 6 to 8 and S in the equivalent command"), `--strict`, `--tolerance-nm N`, `--tolerance-udeg N` and `--tolerance-ppm N` (non-negative integers, default 0), `--frame absolute|relative` (default `absolute`), `--ignore-ref GLOB` (repeatable), `--exclusions FILE` with `--profile NAME`, `--against kicad-import`, `--kicad-cli PATH` and `--timeout SECONDS` (default 300). A level above `max_level`, a bad value, `--exclusions` without `--profile` or the reverse, a profile the file lacks, and `B` together with `--against` or neither of them, and `--exclusions` or `--profile` together with `--against`, MUST exit 2 with `FEN-2001`; the message for a level names the side without footprints, or without copper for level 5, and the highest level available.
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
- **WHEN** `fenolite equivalent a.kicad_pcb` runs without `B` and without `--against`, and `fenolite equivalent a.kicad_pcb b.kicad_pcb --level 9` runs
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

### Requirement: Level 5 in the equivalent command
`fenolite equivalent` SHALL accept `--level 5`, and `max_level` SHALL be 5 when both sides hold at least one track, arc or via.
- `--tolerance-ppm N` (a non-negative integer, default 0) MUST set the relative length tolerance; a profile MAY supply it.
- `--level 5` when a side holds no copper MUST exit 2 with `FEN-2001` naming that side. A level above 8 MUST exit 2.
- `--strict` MUST run the item rule of "Level 5 strict compares copper items" at level 5; it MUST exit 2 with `FEN-2001` when the level run is below 5.
- `result.levels` MUST hold the object of level 5 with its counts and summary, and the differences of the level MUST follow the rules of the command for issues, exclusions and exit code.

#### Scenario: Routed board against itself
- **WHEN** `fenolite equivalent routed.kicad_pcb routed.kicad_pcb --json` runs on a routed board
- **THEN** the exit code is 0, `result.level` is 5, and `result.levels` holds five objects with `differences` 0

#### Scenario: Unrouted side
- **WHEN** `fenolite equivalent routed.kicad_pcb unrouted.kicad_pcb --level 5` runs
- **THEN** the exit code is 2 and the message names the second side

#### Scenario: Strict copy
- **WHEN** `fenolite equivalent routed.kicad_pcb routed.kicad_pcb --level 5 --strict --json` runs on a routed board
- **THEN** the exit code is 0, and `result.levels` holds the strict counts of level 5 with `differences` 0

### Requirement: Equivalence documentation
`docs/equivalence.md` SHALL describe the eight levels and level S, the strict rule of level 5, the matching and normalisation of levels 6 and 7, the rendering and pixel tolerance of level 8, the routed pieces of level 5, the kinds table, the tolerance and normalisation rules, the frame, the exclusion file format and the triangle, and `docs/cli-contract.md` SHALL gain a section `equivalent` with the options, the result keys, the issue codes and the exit codes.
- `docs/roadmap.md` MUST mark levels 1 to 4 as delivered by c0045, level 5 as delivered by c0089 and its strict rule, levels 6 to 8 and level S as delivered by c0278, and no page MUST say that a level is not built.
- `fenolite capabilities --json` MUST list `equivalent` with `mutates` `false`.

#### Scenario: Codes are documented
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_codes.py -k docs` runs
- **THEN** every code of `EQUIVALENCE_CODES` appears in `docs/cli-contract.md` and every kind in `docs/equivalence.md`

#### Scenario: Command is discoverable
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result.commands` holds an entry named `equivalent` with `mutates` `false` and `schema` `fenolite.equivalent.v0`

## ADDED Requirements

### Requirement: Level 5 strict compares copper items
With `strict=True`, level 5 SHALL also compare the tracks, arcs and vias of the two boards item by item, by the rule table of `strict.py` beside the rule of `routing.py`: each kind matched as a multiset, then the widths, drills, spans, types and net names of matched items compared. Copper spans MUST be named as level 5 names them. The routing rule MUST still run, and its differences come first.

#### Scenario: A faithful copy is strictly equal
- **GIVEN** the routed two-layer board and a copy written and re-read by the KiCad backend
- **WHEN** level 5 runs with `strict=True`
- **THEN** it reports no difference and the summary counts the matched tracks, arcs and vias

#### Scenario: Same connectivity, other path
- **GIVEN** a copy in which one track of a net is replaced by two tracks through a new corner point that join the same pads
- **WHEN** level 5 runs without and with `strict=True`
- **THEN** the first reports nothing, and the second reports one `track-missing` with side `a` filled and two with side `b` filled

#### Scenario: Planted strict edits
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_strict.py -k planted` widens a track, changes a via drill, makes a through via blind and unlocks an arc, one at a time
- **THEN** each run reports exactly `track-width`, `via-drill`, `via-span` and the notice `copper-locked`, in that order

### Requirement: Level 5 strict matching
Strict matching SHALL be deterministic: items of one kind are keyed by copper span and geometry (a track by its two ends as an unordered pair, an arc by its ends and mid, a via by its position), matched first on equal keys, then each unmatched item of side `a` in key order with the first unmatched item of side `b` within the length tolerance. `where` MUST be `<net name>:<kind>:<span>:<points>`.

#### Scenario: Reversed track
- **GIVEN** a copy in which one track's start and end are exchanged
- **WHEN** level 5 runs with `strict=True` at tolerance 0
- **THEN** no difference is reported

#### Scenario: Tolerance
- **GIVEN** a copy with one via moved by 5 nm on x
- **WHEN** level 5 runs with `strict=True` at `length_nm` 4 and at 5
- **THEN** the first reports one `via-missing` per side, located `GND:via:top-bottom:<x>,<y>`, and the second reports nothing

### Requirement: Level 6 compares rules
Level 6 SHALL compare net classes by name, custom rules by name, the board-wide rule set, the stack-up layers in order and the board layers by kind and ordinal. Fields MUST be the fields of the canonical JSON of each entity except `id`, `native_ids`, `ext` and provenance, compared exactly, lengths with the length tolerance; `field` is the dotted path. Net class members MUST be compared as sets of net names.

#### Scenario: A clearance changed
- **GIVEN** the two-layer design and a copy whose net class `Default` has a clearance 1 nm larger
- **WHEN** level 6 runs at tolerance 0
- **THEN** it reports one `netclass-field` at `Default` with field `clearance`

#### Scenario: Dielectric thickness
- **GIVEN** a four-layer design and a copy whose second dielectric is thicker
- **WHEN** level 6 runs
- **THEN** it reports one `stackup-field` naming the layer and `thickness`

#### Scenario: Ids do not matter
- **GIVEN** a copy whose net classes and rules carry other ids and native ids
- **WHEN** level 6 runs
- **THEN** it reports nothing

### Requirement: Level 7 compares exact geometry
Level 7 SHALL compare the outline rings, cut-outs and slots, the zones (outline, layers, net name, priority and settings, never the fill), rule areas, board graphics, board texts, holes, dimensions, and the graphics, texts and fields of each footprint pair that level 3 compared, after the normalisation of "Level 7 normalisation". Unmatched items give `<kind>-missing`; matched items compare every field.

#### Scenario: Zone refilled is equal
- **GIVEN** the two-layer design and a copy whose zones were filled again with other fill polygons
- **WHEN** level 7 runs
- **THEN** no difference is reported

#### Scenario: Silkscreen text moved
- **GIVEN** a copy in which the reference field of `R1` is moved by 0.1 mm
- **WHEN** level 7 runs at tolerance 0
- **THEN** one `field-pose` is reported at `R1:Reference` with field `position`

#### Scenario: Outline arc changed
- **GIVEN** a copy whose outline has one arc with another mid point
- **WHEN** level 7 runs
- **THEN** one `outline-missing` is reported on each side

### Requirement: Level 7 normalisation
Before matching, level 7 SHALL normalise geometry in integer arithmetic: a closed ring starts at its smallest point in (x, y) order and runs counter-clockwise; a segment's ends form an unordered pair; an arc is kept by its ends and mid with its ends ordered; a circle by its centre and radius. Points compare with the length tolerance per coordinate, as "Tolerances and normalisation" says.

#### Scenario: Ring drawn the other way
- **GIVEN** a copy whose outline ring lists the same points from another start, clockwise
- **WHEN** level 7 runs
- **THEN** no difference is reported

#### Scenario: Pure
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_package.py` runs
- **THEN** `shapes.py` uses no float and imports no backend

### Requirement: Level 8 compares rendered presentation
Level 8 SHALL render each board layer, and each schematic sheet instance when both sides have sheets, of both sides with one renderer into integer masks on one grid, and SHALL report `render-pixels` when the differing pixels exceed `pixel_ppm` of the inked pixels, after a tolerance of one pixel. `where` MUST be the layer's span or name, or the sheet path, with the box of the largest differing region.

#### Scenario: Same board, no difference
- **WHEN** level 8 compares the two-layer board with a copy written and re-read by the KiCad backend
- **THEN** no difference is reported

#### Scenario: Moved logo on silkscreen
- **GIVEN** a copy whose silkscreen graphic is moved by 2 mm
- **WHEN** level 8 runs with the default tolerance
- **THEN** one `render-pixels` names the silkscreen layer with a box around both places

### Requirement: Level S compares drawn schematics
`compare_drawn(a, b, *, tolerances, pins_a, pins_b) -> LevelResult` SHALL compare two drawn schematics: sheet instances by path, symbols by component path and unit, and wires and buses as their maximal collinear segments, so a wire split differently is the same drawing; other items as multisets by kind and position. It MUST also resolve both drawings and report `drawn-net` for the first `REF-PIN` in another group.

#### Scenario: A drawing against itself
- **GIVEN** the drawn value extracted from the authored hierarchical fixture
- **WHEN** `compare_drawn(d, d, ...)` runs
- **THEN** it reports nothing

#### Scenario: Wire split differently
- **GIVEN** a copy in which one wire is split into two collinear segments
- **WHEN** level S runs
- **THEN** it reports nothing

#### Scenario: Junction removed
- **GIVEN** a copy without the junction on a crossing
- **WHEN** level S runs
- **THEN** it reports one `item-missing` for the junction and one `drawn-net`

### Requirement: Levels 6 to 8 and S in the equivalent command
`fenolite equivalent` SHALL accept `--level 6`, `7`, `8` and `S`. Levels 6 and 7 MUST need a footprint on both sides, level 8 a board on both sides, and level S a schematic on both sides that extraction reads; otherwise exit 2 with `FEN-2001` naming the side. `--pixel-ppm N` (default 1000) and `--render-pitch-um N` (default 50) MUST set level 8.

#### Scenario: Geometry level on request
- **WHEN** `fenolite equivalent two_layer.kicad_pcb two_layer.kicad_pcb --level 7 --json` runs
- **THEN** the exit code is 0 and `result.levels` holds seven objects

#### Scenario: Schematic level on a board
- **WHEN** `fenolite equivalent two_layer.kicad_pcb two_layer.kicad_pcb --level S` runs
- **THEN** the exit code is 2 with `FEN-2001` naming side `a`
