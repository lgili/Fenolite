## MODIFIED Requirements

### Requirement: Assignment compare stage
`fenolite.checks.assignment_compare.assignment_stage(oracle, project, *, validation, model, built, min_pins=1) -> StageResult` SHALL compare the net-to-pad assignments of the model, of the re-read board and of the tool's netlist export as partitions of `REF-PIN` elements, never by net name.
- **Sources.** `board_netlist(design)` (source `board`), with `design = validation.read.design`, MUST give, for each numbered pad of each footprint, `PadAssignment(f"{ref}-{number}", label)`, where the label is the pad's `net_id`, or `NO_NET` (`""`) for a pad on no net; pads with an empty number MUST be counted in `summary.unnumbered` and not compared. `model_netlist(model)` (source `model`, built input only) MUST give each `PinRef` member of a net with the net's id as label, and each other pin of a component with `NO_NET`; an element names the pad of its pin, that is the pin number or the pad that the component's `pin_pad_map` gives it, because the board and the export speak in pad numbers. The export is the `PadNetList` of `oracle.netlist(project, board=design)` (source `export`); a pad that the IPC-D-356 export labels `N/C` MUST get the label `NO_NET`, unless a net of the board is named so. When the `.fenolite/` model could not be loaded, built input compares only (`board`, `export`).
- **Pairs.** The stage MUST compare (`model`, `board`) on built input and (`board`, `export`) on every input.
- **Partitions.** `compare(a, b, *, min_pins=1) -> PairResult` MUST use the elements that both sides cover. Two of them are together on a side when they share a label there that is not `NO_NET`. An element whose label is `NO_NET` is a block of its own: two pads on no net are not connected to each other, so a side that names the net of an unconnected pin, as KiCad does with its `unconnected-(…)` nets, equals a side that leaves that pin on no net. An element with two labels on one side MUST always be a difference; apart from such elements, `compare` MUST give no difference exactly when the two relations are equal.
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

#### Scenario: Unconnected pins named on one side
- **GIVEN** a `model` list with `U1-2` and `U1-3` on no net, and a `board` list with `U1-2` on `unconnected-(U1-PA1-Pad2)` and `U1-3` on `unconnected-(U1-PA2-Pad3)`, both otherwise equal
- **WHEN** `uv run pytest tests/unit/checks/test_assignment_compare.py -k unconnected` calls `compare`
- **THEN** it returns no difference

#### Scenario: Mapped pins are named by their pads
- **GIVEN** a model whose component `R1` has `pin_pad_map == (("1", "2"), ("2", "1"))` and whose net `VIN` lists pin `1`
- **WHEN** `model_netlist` runs
- **THEN** the element on `VIN` is `R1-2`, and `R1-1` is on no net

#### Scenario: Two unconnected pads joined on one side
- **GIVEN** a `model` list with `U1-2` and `U1-3` on no net, and a `board` list with both on one net `X`
- **WHEN** `compare(model, board)` runs
- **THEN** it returns at least one difference, naming `U1-2` or `U1-3`
