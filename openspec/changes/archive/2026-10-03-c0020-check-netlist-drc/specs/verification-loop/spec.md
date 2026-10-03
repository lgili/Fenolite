## ADDED Requirements

### Requirement: Stages added for findings and round trips
`fenolite.checks.stages.STAGE_ORDER` SHALL be `("model.validate", "erc.lite", "drc.kicad", "netlist.assignment_compare", "roundtrip", "roundtrip.rt2")`: this change inserts `netlist.assignment_compare` before `roundtrip` and `roundtrip.rt2` after it, as "Check stages and statuses" allows.
- `OPT_IN_STAGES` MUST be `("roundtrip.rt2",)` and `DEFAULT_STAGES` MUST be `STAGE_ORDER` without them. `fenolite check` without `--stages` MUST run `DEFAULT_STAGES`, and `--stages` MUST accept every name of `STAGE_ORDER`.
- `ORACLE_STAGES` MUST be `("drc.kicad", "netlist.assignment_compare", "roundtrip.rt2")`. When any of them is selected, `cmd_check` MUST run the `kicad-cli` pre-flight of "Check exit codes" and MUST pass `KicadOracle(KicadCli(path, timeout=…))` as the oracle.
- `run_checks` MUST pass the `Validation` of its single `validator.validate` call, or `None` when that read was refused, to `assignment_stage`, and its board model (`Validation.read.design`), or `None`, to `drc_stage`. It MUST still call `validator.validate` at most once per run.
- The functions of the two new stages MUST be `checks.assignment_compare.assignment_stage` and `checks.rt2.rt2_stage`. Each MUST be skipped with reason `read-refused` when the board read was refused, and with reason `unsupported-oracle` when `isinstance(oracle, NetlistOracle)`, respectively `isinstance(oracle, RoundTripOracle)`, is false (`backend-protocol`, "Netlist and round-trip oracles"). A stage skipped with `unsupported-oracle` MUST NOT count in the envelope evidence.
- The new stages MUST keep "Check is read-only" and "Check output is deterministic".

#### Scenario: Default stages leave RT2 out
- **GIVEN** the native `two_layer` project and a fake `kicad-cli` 10.0.6 that writes a DRC report and an IPC-D-356 export, passed with `--kicad-cli`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/cli/test_check_cmd.py -k default_stages` runs `fenolite check <project> --json`
- **THEN** `result.stages` names `model.validate`, `erc.lite`, `drc.kicad`, `netlist.assignment_compare` and `roundtrip` in this order, and no `roundtrip.rt2`

#### Scenario: RT2 selected
- **GIVEN** the same project and fake
- **WHEN** `fenolite check <project> --stages roundtrip.rt2,roundtrip --json` runs
- **THEN** `result.stages` names `roundtrip` then `roundtrip.rt2`

#### Scenario: New stages need kicad-cli
- **GIVEN** no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages netlist.assignment_compare --json` and the same command with `--stages roundtrip.rt2` run
- **THEN** both exit 6 with `FEN-6001`, and no stage runs

#### Scenario: Refused read skips the new stages
- **GIVEN** a fake `Validator` that raises `FormatError` and a fake oracle that satisfies `NetlistOracle` and `RoundTripOracle`
- **WHEN** `uv run pytest tests/unit/checks -k new_stages` calls `run_checks` with `stages=("netlist.assignment_compare", "roundtrip.rt2")` on native input
- **THEN** both stages are skipped with reason `read-refused` and give no issue

#### Scenario: Oracle without the operation
- **GIVEN** a fake `Oracle` that implements only `drc`
- **WHEN** `run_checks` runs `netlist.assignment_compare` with it
- **THEN** the stage is skipped with reason `unsupported-oracle`, and the envelope evidence does not count it

#### Scenario: New stages stay read-only
- **GIVEN** a fake `kicad-cli` that writes `x.kicad_prl` next to its input and rewrites its input board
- **WHEN** `uv run pytest tests/unit/cli/test_check_readonly.py -k new_stages` runs `fenolite check <project> --stages netlist.assignment_compare,roundtrip.rt2`
- **THEN** the project snapshot is equal before and after, and no `.fenolite/`, `native/` or `.kicad_prl` entry was created

### Requirement: DRC findings as issues
`fenolite.checks.drc_json.finding_issues(report, *, oracle, design) -> tuple[Issue, ...]` SHALL map every violation and every unconnected item of a DRC report, after the canary was stripped, to exactly one issue. `schematic_parity` entries MUST be counted in `summary` and MUST NOT be mapped, because no parity check runs before v0.2a.
- **Code.** `type_code(oracle, type)` MUST return `f"{oracle}.drc.{suffix}"`. The suffix is the type in lower case, with `_` and every other character outside `[a-z0-9-]` replaced by `-`, runs of `-` collapsed, leading and trailing `-` removed, and `unknown` when nothing remains. A suffix in `RESERVED_SUFFIXES = ("rules-not-loaded", "rules-unchecked")` MUST become `type-<suffix>`, so a KiCad type never takes a rules-verdict code. The raw type MUST be kept in `summary.types`.
- **Severity.** `issue_severity(violation)` MUST give `info` when `excluded` is true, otherwise `error` for `error`, `warning` for `warning`, and `error` for any other value.
- **Where.** The locations of the items, in report order, joined with `, `. `item_locations(design, oracle)` MUST map each uuid that names exactly one entity of the design's board through `native_ids[oracle]`: a numbered pad gives `REF-PIN` (its component's reference, `-`, the pad number), a pad without a number and a footprint give `REF`, and any other entity gives its `provenance.locator`. A uuid that names no entity or several, and every item when `design` is `None`, MUST give `@<x>,<y>`: the item's report position in millimetres, written as an exact decimal without trailing zeros.
- **Message.** The message MUST be `<type>: <description>`, with the parent folder of `report.source` replaced by `<tmp>` and the home directory by `~`, so the check output holds no temporary or absolute path.
- `finding_issues` MUST NOT emit a code literal; every code it emits matches the `ISSUE_CODES` key `<oracle>.drc.<type>` ("Findings stage issue codes").

#### Scenario: Codes without underscores
- **WHEN** `type_code` is called with `("kicad", "shorting_items")`, `("kicad", "lib_footprint_mismatch")`, `("kicad", "rules_not_loaded")` and `("kicad", "")`
- **THEN** it returns `kicad.drc.shorting-items`, `kicad.drc.lib-footprint-mismatch`, `kicad.drc.type-rules-not-loaded` and `kicad.drc.unknown`, each matching `ISSUE_CODE`

#### Scenario: Pad located as REF-PIN
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb`, and a `DrcReport` whose one `clearance` violation of severity `error` names the uuid of one of the board's tracks and then the uuid of pad 2 of `R1`
- **WHEN** `uv run pytest tests/unit/checks/test_drc_json.py -k ref_pin` calls `finding_issues(report, oracle="kicad", design=design)`
- **THEN** it returns one `kicad.drc.clearance` error whose `where` is that track's `provenance.locator`, then `, `, then `R1-2`

#### Scenario: Unknown item
- **GIVEN** a violation whose only item uuid names no entity of the design, at x 12.5 mm and y 3.25 mm
- **WHEN** it is mapped
- **THEN** the issue's `where` is `@12.5,3.25`

#### Scenario: Excluded and unknown severities
- **GIVEN** one violation with `excluded` true and severity `error`, and one with severity `fatal`
- **WHEN** they are mapped
- **THEN** the first gives severity `info` and the second severity `error`

#### Scenario: Paths removed from messages
- **GIVEN** a report whose `source` is `/tmp/fenolite-kicad-x/b.kicad_pcb` and whose violation description holds `/tmp/fenolite-kicad-x/lib` and the home directory
- **WHEN** it is mapped
- **THEN** the message holds `<tmp>/lib` and `~`, and no absolute path

### Requirement: Assignment compare stage
`fenolite.checks.assignment_compare.assignment_stage(oracle, project, *, validation, model, built, min_pins=1) -> StageResult` SHALL compare the net-to-pad assignments of the model, of the re-read board and of the tool's netlist export as partitions of `REF-PIN` elements, never by net name.
- **Sources.** `board_netlist(design)` (source `board`), with `design = validation.read.design`, MUST give, for each numbered pad of each footprint, `PadAssignment(f"{ref}-{number}", label)`, where the label is the pad's `net_id`, or `NO_NET` (`""`) for a pad on no net; pads with an empty number MUST be counted in `summary.unnumbered` and not compared. `model_netlist(model)` (source `model`, built input only) MUST give each `PinRef` member of a net with the net's id as label, and each other pin of a component with `NO_NET`. The export is the `PadNetList` of `oracle.netlist(project, board=design)` (source `export`). When the `.fenolite/` model could not be loaded, built input compares only (`board`, `export`).
- **Pairs.** The stage MUST compare (`model`, `board`) on built input and (`board`, `export`) on every input.
- **Partitions.** `compare(a, b, *, min_pins=1) -> PairResult` MUST use the elements that both sides cover. Two of them are together on a side when they share a label there, and `NO_NET` is a label like any other. An element with two labels on one side MUST always be a difference; apart from such elements, `compare` MUST give no difference exactly when the two relations are equal.
- **min_pins.** Blocks of fewer than `min_pins` elements MUST be left out of their side, and their elements counted as uncovered with reason `below-min-pins`. The default 1 keeps single-pin nets.
- **Location.** Each difference MUST name one element. For each block of either side, when one block of the other side holds more of its elements than every other block does, each of its elements outside that block MUST be flagged. When the relations differ and nothing is flagged, every element of a block that has no equal block on the other side MUST be flagged.
- **Issues.** One `netlist.assignment-differs` error per flagged element and pair, with the element as `where` and a message naming both sources and both nets (net names for `model` and `board`, the exported label for `export`). One `netlist.uncovered` info per pair, side and reason, with the count and the first five elements in sorted order. A reason is the source's own `Uncovered` reason, or `below-min-pins`, or `not-in-<source>` for an element that the other source does not name at all. No export, or a timeout, MUST give `check.oracle-failed` (error, `retryable: true` on a timeout).
- **Summary.** `summary` MUST hold `pairs` (one `{a, b, common, only_a, only_b, differences}` per pair), `min_pins` and `unnumbered`.
- **Evidence.** The stage evidence MUST be `Evidence.combine` of `validation.read.evidence`, `NetlistOutcome.evidence` and, on built input, `INFERRED` for Fenolite's model rules; `UNVERIFIED` when the export failed.

#### Scenario: Names do not matter
- **GIVEN** a `board` list with `R1-1` on `VIN` and `R1-2` and `D1-2` on `LED_A`, and an `export` list with `R1-1` on `N1` and `R1-2` and `D1-2` on `N2`
- **WHEN** `uv run pytest tests/unit/checks/test_assignment_compare.py -k names` calls `compare`
- **THEN** it returns no difference and `common == 3`

#### Scenario: Reassigned pad located
- **GIVEN** a `model` list with `R1-2` and `D1-2` on `LED_A` and `D1-1` and `U1-9` on `GND`, and a `board` list equal except that `R1-2` is on `GND`
- **WHEN** `compare(model, board)` runs
- **THEN** it returns exactly one difference, naming `R1-2`

#### Scenario: Swapped pairs flagged
- **GIVEN** an `a` list with blocks `{P1-1, P2-1}` and `{P3-1, P4-1}`, and a `b` list with blocks `{P1-1, P3-1}` and `{P2-1, P4-1}`
- **WHEN** `compare(a, b)` runs
- **THEN** it returns four differences, one per element

#### Scenario: Uncovered elements are coverage
- **GIVEN** a `board` list holding `MH1-1` on no net and an `export` list without it, both otherwise equal
- **WHEN** the stage runs with a fake netlist oracle
- **THEN** it reports no `netlist.assignment-differs`, one `netlist.uncovered` info naming `MH1-1`, and status `ok`

#### Scenario: Single-pin nets
- **GIVEN** a net with one element on both sides of a pair
- **WHEN** `compare` runs with `min_pins=1` and then with `min_pins=2`
- **THEN** the element is common in the first run, and counted as uncovered with reason `below-min-pins` in the second

#### Scenario: Native input compares board and export only
- **GIVEN** the native `two_layer` project and a fake netlist oracle that returns the board's own partition under other labels
- **WHEN** the stage runs
- **THEN** `summary.pairs` holds one pair, (`board`, `export`), with 0 differences, and the status is `ok`

### Requirement: RT2 stage
`fenolite.checks.rt2.rt2_stage(oracle, project) -> StageResult` SHALL report RT2 of the board: KiCad's DRC gives the same violations for the board and for Fenolite's re-dump of it, as the reports of `oracle.rt2(project)` show (`kicad-oracle`, "RT2 oracle").
- **Keys.** `violation_key(group, violation, *, source)` MUST be `(group, type, severity, excluded, items)`, where `group` is `violations` or `unconnected_items` and `items` is the sorted tuple of each item's description and position. Item uuids MUST be left out, because a re-save drops or replaces some (`H-K-UUID-KEEP-2`). The parent folder of `source` MUST be replaced by `<tmp>` in descriptions.
- **Stability.** `compare_runs(outcome) -> Rt2Verdict(holds, unstable, differences, judged)` MUST treat a key as unstable when its count differs between the runs of the original (`before`) or between the runs of the re-dump (`after` and `repeats`); such keys MUST be left out of both sides and counted. `holds` MUST be true when the remaining keys of the first run of the original and of the first run of the re-dump have equal counts.
- **Judged.** A tool may not repeat its own report (`H-K-RT2-STABLE-2`), so a difference stands only when both sides repeat: `judged` MUST be true when `holds` is true or no key is unstable, and false otherwise. When `judged` is false the stage neither passes nor fails on the difference: it reports no `check.rt2-failed`, its status is `ok`, and its evidence is `UNVERIFIED`.
- **Issues.** When `judged` is true, one `check.rt2-failed` error per differing key, with its type and both counts in the message and the `@<x>,<y>` of its first item as `where` (empty when it has none). One `check.rt2-unstable` info with the count of unstable keys, when it is not 0; when `judged` is false, its message MUST also give the count of the other differing keys and say that RT2 is not judged. Fewer than two reports of the original, or no report of the re-dump, MUST give `check.oracle-failed` (error, `retryable: true` on a timeout).
- **Summary.** `summary` MUST hold `holds`, `judged`, `normalised`, `runs` (`original` and `redump` counts), `before` and `after` (violations and unconnected items of the first original run and of the first re-dump run), `unstable` and `differences`.
- **Evidence.** The stage evidence MUST be `Rt2Outcome.evidence` when both sides were compared and `judged` is true, and `UNVERIFIED` otherwise.

#### Scenario: Equal runs hold
- **GIVEN** a fake `RoundTripOracle` whose two original reports and re-dump report are equal
- **WHEN** `uv run pytest tests/unit/checks/test_rt2_stage.py -k equal` runs the stage
- **THEN** the status is `ok`, `summary.holds` is true and `summary.unstable` is 0

#### Scenario: Unstable violation excluded
- **GIVEN** a first original report with one more `silk_overlap` warning than the second, and a re-dump report equal to the second
- **WHEN** the stage runs
- **THEN** `summary.holds` is true, and one `check.rt2-unstable` info reports the count 1

#### Scenario: Changed re-dump fails
- **GIVEN** equal original reports and a re-dump report with one more `clearance` error
- **WHEN** the stage runs
- **THEN** it reports one `check.rt2-failed` error naming `clearance` with the counts 0 and 1, and the status is `errors`

#### Scenario: Difference on an unstable board is not judged
- **GIVEN** two original reports that differ in one `silk_overlap` warning, and a re-dump report with one more `clearance` error than both
- **WHEN** the stage runs
- **THEN** it reports no `check.rt2-failed` and one `check.rt2-unstable` info saying that RT2 is not judged, `summary.judged` and `summary.holds` are false, the status is `ok` and the evidence level is `UNVERIFIED`

#### Scenario: Repeated difference fails
- **GIVEN** five equal original reports, and a re-dump report with one more `clearance` error that its three repeats also hold
- **WHEN** the stage runs
- **THEN** it reports one `check.rt2-failed` error, `summary.judged` is true and the status is `errors`

#### Scenario: Item uuids masked
- **GIVEN** a re-dump report equal to the original reports except for every item uuid
- **WHEN** the stage runs
- **THEN** `summary.holds` is true

#### Scenario: Real runs on both majors
- **GIVEN** the native `two_layer` project and the authored built project
- **WHEN** `uv run pytest tests/kicad/check/test_rt2_stage.py` runs `fenolite check <project> --stages roundtrip.rt2 --json` on 9.0.9 and on 10.0.6
- **THEN** `roundtrip.rt2` has status `ok`, `summary.holds` is true, `summary.normalised` is true on 10.0.6 and false on 9.0.9, and the project snapshot is unchanged

### Requirement: Findings stage issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities, and `docs/cli-contract.md` MUST document each of them, with `kicad` for `<oracle>` ("Check issue codes").

| code | severity | when |
|---|---|---|
| `<oracle>.drc.<type>` | error, warning, info | one per DRC violation or unconnected item, `<type>` from `type_code` |
| `netlist.assignment-differs` | error | an element whose net block differs between the two sources of a pair |
| `netlist.uncovered` | info | elements that one side of a pair does not cover, per reason |
| `check.rt2-failed` | error | a violation key whose counts differ between the original and the re-dump |
| `check.rt2-unstable` | info | violation keys that differ between runs of one side; its message says when RT2 is therefore not judged |

- `netlist.assignment_compare` and `roundtrip.rt2` MUST also report `check.oracle-failed` when the tool writes no export or report, or times out.
- Every generated finding code MUST match `ISSUE_CODE` and MUST differ from every rules-verdict code.

#### Scenario: New literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each new literal is a key of `ISSUE_CODES` with the severities of this table

#### Scenario: New codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** `kicad.drc.<type>`, `netlist.assignment-differs`, `netlist.uncovered`, `check.rt2-failed` and `check.rt2-unstable` appear in `docs/cli-contract.md`

### Requirement: Negative tests and a positive control
`tests/kicad/check/test_negatives.py` (markers `needs_kicad`, major-aware) SHALL prove on 9.0.9 and 10.0.6 that `fenolite check` locates two seeded faults, and SHALL keep c0018's overlapping-rules fixture as a permanent positive control. `tests/kicad/check/_fixtures.py` MUST write each project into `tmp_path` from c0013's authored built project or from a bench of c0018's `tests/kicad/rules/_rulecases.py::order`:
- **Reassigned pad.** Pad 2 of `R1` moved from `LED_A` to `GND` on the board only (`read_board`, the pad's `net_id` replaced, `write_board` for the running major), with the `.fenolite/` model unchanged: a `netlist.assignment-differs` error with `where` `R1-2` for the pair (`model`, `board`).
- **Bridging track.** One `F.Cu` track of net `VIN` from pad 1 to pad 2 of `R1` added to the board: a `kicad.drc.shorting-items` error whose `where` names `R1-2`.
- **Positive control.** The `forward` and `reverse` benches of `order(direction)`: a `_rulebench.builder()` bench, which holds c0018's canary pair, with the pair `ord` on `ORD_A` and `ORD_B` 2 mm apart, and `tests/data/kicad/rules/overlap.kicad_dru` (its two rules reversed for `reverse`) behind c0018's canary rule. c0018's own report of each bench (`order(direction).report`) MUST pass `require_canary`, and `violations_between` MUST find the `ord` pair's `clearance` violation in the forward one only. `overlap_bench` MUST write the same `Bench.design` and rules text into `tmp_path` with a `{}` project. Because the bench carries the canary (living `kicad-oracle`, "Rules proofs carry a canary"), the check output MUST be judged by item, matching issue codes and the locations that `item_locations` gives for `Bench.uuids(label)`: the forward run MUST give exactly one `kicad.drc.clearance` error whose `where` names the two `ord` tracks, and the reverse run none naming an `ord` track; both runs MUST give one `kicad.drc.clearance` error whose `where` names the two canary tracks, and `summary.canary` `fired`. A run without that canary finding MUST fail the test with "rules file not loaded", as `require_canary` does.
- The unmodified authored built project MUST give neither `netlist.assignment-differs` nor `kicad.drc.shorting-items`.

#### Scenario: Reassigned pad caught with location
- **GIVEN** the reassigned-pad project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_negatives.py -k reassigned` runs on 9.0.9 and on 10.0.6
- **THEN** `fenolite check <project> --json` exits 5 with a `netlist.assignment-differs` error whose `where` is `R1-2`

#### Scenario: Bridging track caught with location
- **GIVEN** the bridging-track project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_negatives.py -k bridging` runs on 9.0.9 and on 10.0.6
- **THEN** `fenolite check <project> --json` exits 5 with a `kicad.drc.shorting-items` error whose `where` contains `R1-2`

#### Scenario: Overlapping rules
- **GIVEN** the `forward` and `reverse` benches of `_rulecases.order`, whose own reports pass `require_canary`, written by `overlap_bench`
- **WHEN** `uv run pytest tests/kicad/check/test_negatives.py -k overlap` runs `fenolite check <bench> --json` on 9.0.9 and on 10.0.6
- **THEN** the forward run reports exactly one `kicad.drc.clearance` error whose `where` names the two `ord` tracks and the reverse run none naming an `ord` track, both runs report one `kicad.drc.clearance` error whose `where` names the two canary tracks, and `summary.canary` is `fired` in both

#### Scenario: Clean control
- **GIVEN** the unmodified authored built project
- **WHEN** the same test runs it
- **THEN** no `netlist.assignment-differs` and no `kicad.drc.shorting-items` issue is reported

### Requirement: Built examples have no assignment differences
`tests/kicad/check/test_check_built.py` SHALL check c0011's `examples/blink_2layer`, built into `tmp_path` with `fenolite build examples/blink_2layer/design.py --out <tmp> --kicad-version <target> --confirm` for each target the running major loads (9 on 9.0.9; 9 and 10 on 10.0.6), and c0013's authored built project, with `fenolite check <dir> --json` (v0.1 acceptance item 1, part).
- `netlist.assignment_compare` MUST have status `ok` with 0 differences in both pairs, and no `netlist.uncovered` with reason `unmatched-record` or `net-label-ambiguous`.
- Every `kicad.drc.unconnected-items` finding MUST name `REF-PIN` pads in its `where`.
- The second example board of v0.1 is checked by the same test once it exists (c0025).

#### Scenario: Blink on both majors
- **GIVEN** the blink built for each target the running major loads
- **WHEN** `uv run pytest tests/kicad/check/test_check_built.py -k assignment` runs on 9.0.9 and on 10.0.6
- **THEN** `netlist.assignment_compare` is `ok` with 0 differences in the pairs (`model`, `board`) and (`board`, `export`)

#### Scenario: Authored built project
- **GIVEN** c0013's authored built project for the running major
- **WHEN** the same test runs it
- **THEN** `netlist.assignment_compare` is `ok` with 0 differences, and each `kicad.drc.unconnected-items` issue names `REF-PIN` pads

## MODIFIED Requirements

### Requirement: Check command input
`fenolite check PATH` SHALL be registered by `src/fenolite/cli/cmd_check.py` with `mutates=False`, and SHALL check the KiCad project that `PATH` names without writing any file.
- **Board.** The board MUST be found with `fenolite.backends.kicad.projectset.resolve_board(PATH)` (`kicad-oracle`, "Check project copy set"). An ambiguous folder MUST exit 2 with `FEN-2001` and a hint listing the candidates. A missing path or board MUST exit 3 with `FEN-3001`.
- **Flags.** `--stages a,b` MUST select a subset of `STAGE_ORDER`; an unknown or empty stage name MUST exit 2 with `FEN-2001`. `--kicad-cli PATH` MUST be passed to `find_kicad_cli` as the explicit path. `--timeout SECONDS` MUST default to 300 and MUST be passed to `KicadCli`.
- **Built or native.** The input MUST be built when `<root>/.fenolite/meta.json` or `<root>/.fenolite/build.json` exists, `<root>` being the board's folder, and native otherwise. Built input MUST load its model with `model.canonical.load_dir(<root>/.fenolite)`. The board's `generator` atom MUST NOT decide it.
- **Injection.** The command MUST narrow `registry.for_path(board)` with `isinstance(backend, Validator)` (`Validator` is `@runtime_checkable`), exit 2 with `FEN-2001` when no backend validates the board, and pass the narrowed backend as the `Validator` and `KicadOracle(KicadCli(path, timeout=…))` as the `Oracle` to `fenolite.checks.stages.run_checks`. It MUST build the oracle only when a stage of `ORACLE_STAGES` is selected ("Stages added for findings and round trips").
- **Result.** `result.project` MUST hold `board`, `built`, `files` and `skipped`, with names relative to `<root>`. `result.stages` MUST hold one object per selected stage. `input.path` MUST be the board name relative to `<root>`.
- `example_args` MUST be `(EXAMPLE_BOARD, "--stages", "model.validate,erc.lite,roundtrip")`, which runs no subprocess. `fenolite.cli._examples.EXAMPLE_BOARD` MUST be the absolute path of `tests/data/kicad/board/two_layer.kicad_pcb`, resolved at import from `Path(fenolite.__file__).resolve().parents[2]`, so that the consistency suite passes from any working directory of a source checkout.

#### Scenario: Project folder resolved
- **GIVEN** a folder holding `a.kicad_pro`, `a.kicad_pcb` and `b.kicad_pcb`
- **WHEN** `fenolite check <folder> --stages roundtrip --json` runs
- **THEN** `result.project.board` is `a.kicad_pcb` and the exit code is 0

#### Scenario: Ambiguous folder
- **GIVEN** a folder holding `a.kicad_pcb` and `b.kicad_pcb` and no project file
- **WHEN** `fenolite check <folder> --json` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and its hint names both boards

#### Scenario: Unknown stage or missing path
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages drc` and `fenolite check missing.kicad_pcb` run
- **THEN** the first exits 2 with `FEN-2001`, and the second exits 3 with `FEN-3001`

#### Scenario: Built input detected
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`, which writes `.fenolite/` with `dump_dir`
- **WHEN** `fenolite check <project> --stages model.validate,erc.lite,roundtrip --json` runs
- **THEN** `result.project.built` is `true` and the `erc.lite` stage has status `ok`

#### Scenario: Example arguments are hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `check` with its `example_args`
- **THEN** the exit code is 0, and `input.path` is `two_layer.kicad_pcb`

#### Scenario: Consistency suite from another folder
- **WHEN** `uv run pytest tests/consistency` runs from a temporary working directory, as in c0011's scenario "Consistency suite"
- **THEN** it passes for `check`, `inspect` and `doctor`

### Requirement: DRC stage and the rules canary
`checks.drc.drc_stage(oracle, project, *, built, design=None) -> StageResult` SHALL run DRC once through `oracle.drc(project)` and SHALL turn the rules verdict into issues. DRC violations MUST always be counted in `summary`. `summary.violations_judged` MUST be `true` exactly when the run also maps DRC violations to issues. Whenever a report exists, the stage MUST map them with `checks.drc_json.finding_issues(report, oracle=oracle.name, design=design)` ("DRC findings as issues"), where `design` is the board model that `run_checks` read, or `None` when that read was refused; without a report it maps none, and `violations_judged` is `false`.
- **Rules verdict.** Codes MUST start with `f"{oracle.name}.drc."`:
  - canary `absent`, or a `<stem>.kicad_dru` in the copy set without a `<stem>.kicad_pro`: `rules-not-loaded`, severity `error` on built input and `info` on native input;
  - canary `inconclusive`: `rules-unchecked` (warning), with `canary_reason` in the message, except for reason `no-report`, which gives only `check.oracle-failed`;
  - canary `fired`, or `not-applicable` without a rules file: no issue.
- **Summary.** `summary` MUST hold `tool_version`, `canary`, `canary_reason`, `canary_removed`, `violations` (total), `by_type`, `by_severity`, `unconnected`, `excluded`, `tool_writes`, `violations_judged` and `types` (each emitted `<oracle>.drc.<type>` code mapped to the tool's raw type), counted on the report from which every canary violation was removed.
- **Copy skips.** Each `SkippedFile` of the project MUST give one `check.copy-skipped` info naming the file and its reason. It MUST NOT lower the stage evidence.
- **No report.** When KiCad wrote no report or timed out, the stage MUST report `check.oracle-failed` (error) with `DrcOutcome.message`, and `retryable: true` on a timeout.

#### Scenario: Built project with a firing canary
- **GIVEN** the authored built project for the running major
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k canary` runs on 9.0.9 and on 10.0.6
- **THEN** `summary.canary` is `fired`, `summary.canary_removed` is 0 on a major of `CANARY_TWO_RUN` (the counted report comes from the plain run) and at least 1 otherwise, `summary.violations_judged` is `true`, and no count and no issue includes a canary item

#### Scenario: Rules not loaded on a built project
- **GIVEN** the authored built project whose `<stem>.kicad_dru` is `tests/data/kicad/rules/broken.kicad_dru` (`ten_only.kicad_dru` on 9.0.9 if `H-K-DRU-QUOTE` is refuted there)
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k rules` runs on both majors
- **THEN** `check` exits 5, `kicad.drc.rules-not-loaded` is an error issue, and every other error issue is a `kicad.drc.<type>` finding

#### Scenario: Rules not loaded on a native project
- **GIVEN** the native `two_layer` project with the same rules file
- **WHEN** `fenolite check <project> --json` runs
- **THEN** `kicad.drc.rules-not-loaded` has severity `info`, the stage level is `UNVERIFIED`, and the exit code is 5 only when another issue has severity `error`

#### Scenario: Rules file without a project file
- **GIVEN** a folder holding a board and `<stem>.kicad_dru` but no `<stem>.kicad_pro`
- **WHEN** `fenolite check <folder> --json` runs
- **THEN** the issues hold `kicad.drc.rules-not-loaded` and `summary.canary` is `not-applicable`

#### Scenario: Verdicts named by the oracle
- **GIVEN** a fake `Oracle` named `fake` that returns an empty report and canary `inconclusive` with reason `selector-unproven`
- **WHEN** `uv run pytest tests/unit/checks -k drc_stage` runs the stage on built input
- **THEN** it reports one `fake.drc.rules-unchecked` warning naming `selector-unproven`, and the stage level is `UNVERIFIED`

#### Scenario: Skipped copy does not lower evidence
- **GIVEN** a fake `Oracle` that returns an empty report and canary `fired`, and a project set with one `SkippedFile("../Other.pretty", "outside-root")`
- **WHEN** the stage runs
- **THEN** it reports one `check.copy-skipped` info naming `../Other.pretty`, and the stage keeps the oracle's `KICAD-VERIFIED`

#### Scenario: Findings mapped by the stage
- **GIVEN** a fake `Oracle` named `fake` whose report holds one `shorting_items` violation of severity `error` naming the uuid of pad 2 of `R1` of the design passed to the stage, and canary `fired`
- **WHEN** `uv run pytest tests/unit/checks -k drc_stage` runs the stage on native input
- **THEN** it reports one `fake.drc.shorting-items` error whose `where` is `R1-2`, `summary.types` maps that code to `shorting_items`, `summary.violations_judged` is `true`, and the status is `errors`

#### Scenario: No report, nothing judged
- **GIVEN** a fake `Oracle` that returns no report
- **WHEN** the stage runs
- **THEN** it reports `check.oracle-failed`, and `summary.violations_judged` is `false`

#### Scenario: Built blink before routing
- **GIVEN** c0011's `examples/blink_2layer` built into `tmp_path` for the running major with `fenolite build … --confirm`
- **WHEN** `uv run pytest tests/kicad/check/test_check_built.py` runs `fenolite check <dir> --json` on both majors
- **THEN** the stages are `model.validate`, `erc.lite`, `drc.kicad`, `netlist.assignment_compare` and `roundtrip` in this order, `erc.lite` runs, `summary.canary` is `fired`, `summary.violations_judged` is `true`, `roundtrip` is `ok`, and every `kicad.drc.unconnected-items` issue names `REF-PIN` pads in its `where`
