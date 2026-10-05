## ADDED Requirements

### Requirement: Parity comparison
`fenolite.checks.parity.compare(side, board, *, issues=None) -> ParityReport` SHALL compare a schematic side with a board, and SHALL report every difference with one code of "Parity issue codes".
- `side` MUST be a `SchematicSide(components, nodes, fold, single_prefix)` of `backends.base`, re-exported here: `components` maps each reference to `SideComponent(value, footprint, pins, attributes)`, `pins` being the pin numbers of all the component's units in body style 1 and of its common pins, and `attributes` those of the flags `dnp` and `exclude_from_bom` that the symbol has; `nodes` maps (reference, pin number) to a net name in the backend's stored form. References that start with `#` MUST NOT be components.
- `board` MUST be a `Design` with a board, as `read_board` gives it.
- **Net names.** Both sides MUST be compared after the replacements of `side.fold` (KiCad: `{slash}` and `/` are one spelling). When `side.single_prefix` is not empty, a board net named `<node>_<digits>` MUST be the net of a node whose name starts with that prefix (a further pad of the number of a pin on no net).
- **Matching.** Components and footprints MUST be matched by reference only. With several footprints of one reference, the component MUST be matched with the first in board order, a footprint with the attribute `board_only` included.
- **Findings.** `parity.missing-footprint` for a component without a footprint of its reference; `parity.extra-footprint` for each footprint without a component, footprints with the attribute `board_only` left out; `parity.duplicate-footprints` for each further footprint of a reference (`n - 1` for `n` footprints, the empty reference included), footprints with `board_only` left out; `parity.footprint-mismatch` once per differing field of `FIELDS`: `value`, `footprint` (the library id) or `attributes` (the flags of `SHARED_ATTRIBUTES` that the symbol and the footprint do not share, one finding for all); `parity.net-conflict` for each numbered pad of a matched footprint whose net is not the node of its number, a pad on no net whose node has one and a pad on a net whose number no pin names included.
- **Symbol and footprint.** For each matched pair: `parity.pin-without-pad` for a pin number that names no pad, an error when the node's net has another node and a warning otherwise; `parity.pad-without-pin` (info), once per number, for a numbered pad of a kind other than `np_thru_hole` that is on no net and whose number no pin names. A pin without a number and a pad without a number MUST NOT be compared.
- **Report.** `ParityReport.findings` MUST be sorted by code, then key, then field; each `ParityFinding` holds `code`, `severity`, `key` (the reference, or `REF-PAD`), `field`, and the `schematic` and `board` values. `summary` MUST hold the count of each code and `refs_one_side` (missing plus extra footprints), `connections_missing` (net conflicts whose pad has no net while its node has one) and `nets_split` (schematic nets whose pads carry more than one board net name, or one other than the schematic's).
- `KICAD_TYPES` MUST map each of the first five codes to its KiCad parity type (`H-K-PARITY-TYPES`), and `parity.pin-without-pad` to `net_conflict`: KiCad reports such a pin as a net conflict of the footprint. `oracle_entry(finding)` MUST give the KiCad type and key of a finding (the reference for a pin without a pad), or `None` for a finding that KiCad does not make.
- The module MUST import only `core`, `model`, `geometry` and `backends.base`, and MUST be pure. `EVIDENCE` MUST be `INFERRED` with `H-K-PARITY-OWN`.

#### Scenario: Agreeing project
- **GIVEN** the side and board of the blink built with a schematic
- **WHEN** `compare` runs
- **THEN** `findings` is empty, and every summary count is 0

#### Scenario: Reference on one side
- **GIVEN** the same board with `R1`'s reference changed to `R99` by token edit
- **WHEN** `compare` runs
- **THEN** `findings` holds `parity.missing-footprint` keyed `R1` and `parity.extra-footprint` keyed `R99`, and `summary.refs_one_side` is 2

#### Scenario: Pad on no net
- **GIVEN** the same board with the net of pad 2 of `R1` removed by token edit
- **WHEN** `compare` runs
- **THEN** `findings` holds `parity.net-conflict` keyed `R1-2`, and `summary.connections_missing` is 1

#### Scenario: Pin without a pad
- **GIVEN** an authored side whose `U1` has a pin `33` on the net `VIN`, which also holds `R1` pin 1, and a board whose `U1` footprint has 32 pads
- **WHEN** `compare` runs
- **THEN** `findings` holds one `parity.pin-without-pad` error keyed `U1-33`

#### Scenario: Board-only footprint
- **GIVEN** the blink board with a footprint `H1` that has the attribute `board_only`
- **WHEN** `compare` runs
- **THEN** no finding names `H1`

#### Scenario: Duplicated reference
- **GIVEN** the blink board whose `R1` was given the reference `D1`
- **WHEN** `compare` runs
- **THEN** `findings` holds one `parity.duplicate-footprints` keyed `D1` and one `parity.missing-footprint` keyed `R1`, and nothing else, because the footprint `D1` that comes first is the diode's own

### Requirement: Parity stage
`fenolite check` SHALL gain the stage `parity`, after `drc.kicad` and before `roundtrip` in `STAGE_ORDER`, as "Check stages and statuses" allows, run by `checks.parity_stage.parity_stage`.
- The stage MUST be `skipped` with the reason `no-schematic` when the project has no `<board stem>.kicad_sch`, with `read-refused` when the board was not read, and with `netlist-unavailable` when the sheet tree is outside Fenolite's netlist grammar and no netlist oracle is injected. The stage is not one of `ORACLE_STAGES`: selecting it alone builds no oracle.
- The side MUST come from the validator when it is a `ParityInputs` of `backends.base` (`schematic_side(project, *, nodes=None) -> SideOutcome`): with the backend's own netlist when the tree is inside the grammar, else with the schematic netlist of the injected `SchematicNetlistOracle` (c0063). An oracle that writes no netlist MUST give `check.oracle-failed`, and a schematic that cannot be read `check.read-refused`.
- Symbol ↔ footprint findings (`parity.pin-without-pad`, `parity.pad-without-pin`) MUST always become issues.
- When `drc.kicad` ran in the same check with `summary.parity_judged` true, the other findings MUST NOT become issues. They MUST be compared with KiCad's parity entries by KiCad type and key (`oracle_entry`; the key of a KiCad entry is its first item's location, and the reference in its text for a missing footprint), and each difference MUST give one `parity.oracle-differs` (warning) naming the type, the key and the side that holds it. A KiCad type without a Fenolite code is not compared. Otherwise they MUST become issues.
- `summary` MUST hold `netlist` (`own` or `oracle`), `compared` (whether KiCad's entries were compared), `differences`, and the counts of `ParityReport.summary`.
- The stage evidence MUST be `checks.parity.EVIDENCE` combined with the netlist's, and `KICAD-VERIFIED` evidence of `drc.kicad` MUST NOT be lowered by this stage.

#### Scenario: Agreement with KiCad
- **GIVEN** the blink built with a schematic, whose pad 2 of `R1` was moved to `GND` by token edit
- **WHEN** `fenolite check <dir> --stages drc.kicad,parity --json` runs with `kicad-cli`
- **THEN** `drc.kicad` reports `kicad.drc.net-conflict` at `R1-2`, the stage `parity` reports no `parity.net-conflict` and no `parity.oracle-differs`, and its `summary.compared` is `true`

#### Scenario: Without KiCad
- **WHEN** the same check runs with `--stages parity` and no `kicad-cli`
- **THEN** the stage `parity` reports `parity.net-conflict` at `R1-2`, `summary.netlist` is `own`, `summary.compared` is `false`, and the exit code is 5

#### Scenario: Disagreement reported
- **GIVEN** a fake oracle whose parity entries omit the net conflict
- **WHEN** the check runs with both stages
- **THEN** the stage `parity` reports one `parity.oracle-differs` naming `net_conflict`, `R1-2` and the side `fenolite`

### Requirement: Parity issue codes
`checks.parity.PARITY_ISSUE_CODES` SHALL be this closed table, and the codes SHALL join the check issue codes.

| code | severity | when |
|---|---|---|
| `parity.missing-footprint` | error | a schematic component has no footprint |
| `parity.extra-footprint` | error | a footprint has no schematic component |
| `parity.duplicate-footprints` | error | a footprint holds the reference of an earlier one |
| `parity.net-conflict` | error | a pad's net differs from the schematic's, or no pin names a pad that is on a net |
| `parity.pin-without-pad` | error or warning | a pin names no pad: error when its net has another node |
| `parity.footprint-mismatch` | warning | the value, the footprint or the shared flags differ |
| `parity.oracle-differs` | warning | Fenolite's comparison and KiCad's parity test disagree |
| `parity.pad-without-pin` | info | a numbered copper pad on no net that no pin names |

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/checks/test_parity.py -k closed_set` collects the codes that `test_parity.py` and `test_parity_stage.py` name
- **THEN** each is a key of `PARITY_ISSUE_CODES` with an allowed severity, and every key is produced by at least one test
