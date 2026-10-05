## ADDED Requirements

### Requirement: Parity comparison
`fenolite.checks.parity.compare(side, board, *, issues=None) -> ParityReport` SHALL compare a schematic side with a board, and SHALL report every difference with one code of "Parity issue codes".
- `side` MUST be a `SchematicSide(components, nodes)`: `components` maps each reference to `SideComponent(value, footprint, pins)`, `pins` being the pin numbers of all the component's units in body style 1 and of its common pins; `nodes` maps (reference, pin number) to a net name in KiCad's stored form. References that start with `#` MUST NOT be components.
- `board` MUST be a `Design` with a board, as `read_board` gives it. Pad nets MUST be compared in the stored form (`H-K-SCH-SLASH`).
- **Matching.** Components and footprints MUST be matched by reference only. A footprint with the attribute `board_only` MUST be left out. With several footprints of one reference, the component MUST be matched with the first in board order.
- **Findings.** `parity.missing-footprint` for a component without a footprint; `parity.extra-footprint` for a footprint without a component; `parity.duplicate-footprints` once per reference held by several footprints; `parity.footprint-mismatch` once per differing field, `value` or `footprint` (the library id); `parity.net-conflict` for each numbered pad of a matched footprint whose net differs from the node of its number, a pad on no net and a node on no net included.
- **Symbol and footprint.** For each matched pair: `parity.pin-without-pad` for a pin number that names no pad, an error when the node's net has another node and a warning otherwise; `parity.pad-without-pin` (info) for a numbered pad of a kind other than `np_thru_hole` whose number no pin names.
- **Report.** `ParityReport.findings` MUST be sorted by code, then key, then field; each `ParityFinding` holds `code`, `severity`, `key` (the reference, or `REF-PAD`), `field`, and the `schematic` and `board` values. `summary` MUST hold the count of each code and `refs_one_side` (missing plus extra footprints), `connections_missing` (net conflicts whose pad has no net while its node has one) and `nets_split` (schematic nets whose pads carry more than one board net name, or one other than the schematic's).
- `KICAD_TYPES` MUST map each of the first five codes to its KiCad parity type (`H-K-PARITY-TYPES`).
- The module MUST import only `core`, `model`, `geometry` and `backends.base`, and MUST be pure. `EVIDENCE` MUST be `INFERRED` with `H-K-PARITY-OWN`.

#### Scenario: Agreeing project
- **GIVEN** the side and board of the blink built with a schematic
- **WHEN** `compare` runs
- **THEN** `findings` holds no finding of severity error or warning, and every summary count is 0

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

### Requirement: Parity stage
`fenolite check` SHALL gain the stage `parity`, after `drc.kicad` and before `roundtrip` in `STAGE_ORDER`, as "Check stages and statuses" allows, run by `checks.parity_stage.parity_stage`.
- The stage MUST be `skipped` with the reason `no-schematic` when the project has no `<board stem>.kicad_sch`, and with `netlist-unavailable` when the sheet tree is outside Fenolite's netlist grammar and no netlist oracle is injected.
- The side MUST be built with the own netlist when the tree is inside the grammar, else with the injected netlist oracle (c0063).
- Symbol ↔ footprint findings (`parity.pin-without-pad`, `parity.pad-without-pin`) MUST always become issues.
- When `drc.kicad` ran in the same check with `summary.parity_judged` true, the other findings MUST NOT become issues. They MUST be compared with KiCad's parity entries by KiCad type and key, and each difference MUST give one `parity.oracle-differs` (warning) naming the type, the key and the side that holds it. Otherwise they MUST become issues.
- `summary` MUST hold `netlist` (`own` or `oracle`), `compared` (whether KiCad's entries were compared), `differences`, and the counts of `ParityReport.summary`.
- The stage evidence MUST be `checks.parity.EVIDENCE` combined with the netlist's, and `KICAD-VERIFIED` evidence of `drc.kicad` MUST NOT be lowered by this stage.

#### Scenario: Agreement with KiCad
- **GIVEN** the blink built with a schematic, whose pad 2 of `R1` was moved to `GND` by token edit
- **WHEN** `fenolite check <dir> --stages drc.kicad,parity --json` runs with `kicad-cli`
- **THEN** `drc.kicad` reports `kicad.drc.net-conflict` at `R1-2`, the stage `parity` reports no `parity.net-conflict` and no `parity.oracle-differs`, and its `summary.compared` is `true`

#### Scenario: Without KiCad
- **WHEN** the same check runs with `--stages parity` and no `kicad-cli`
- **THEN** the stage `parity` reports `parity.net-conflict` at `R1-2`, `summary.netlist` is `own`, and the exit code is 5

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
| `parity.duplicate-footprints` | error | several footprints hold one reference |
| `parity.net-conflict` | error | a pad's net differs from the schematic's |
| `parity.pin-without-pad` | error or warning | a pin names no pad: error when its net has another node |
| `parity.footprint-mismatch` | warning | the value or the footprint differs |
| `parity.oracle-differs` | warning | Fenolite's comparison and KiCad's parity test disagree |
| `parity.pad-without-pin` | info | a numbered copper pad that no pin names |

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/checks/test_parity.py -k closed_set` collects the codes produced by its tests
- **THEN** each is a key of `PARITY_ISSUE_CODES` with an allowed severity, and every key is produced by at least one test
