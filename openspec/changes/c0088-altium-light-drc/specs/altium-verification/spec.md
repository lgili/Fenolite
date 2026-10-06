## ADDED Requirements

### Requirement: Document stage order
`checks.documents.DOCUMENT_STAGES` SHALL be `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0`, `roundtrip.rta1`, `roundtrip.rta2`, in this order, and every stage SHALL be a default stage that runs no external tool.

#### Scenario: Order
- **WHEN** `uv run pytest tests/unit/checks/test_documents.py -k stage_order` reads the tuple
- **THEN** it equals the list above

### Requirement: Copper check on Altium boards
On document input that holds a PCB document, the stage `copper.clearance` SHALL run `checks.copper` on the imported board with the rules that the backend reads from that document (`DesignRulesSource`) and the outline it gives (`BoardFrame`), built and native input alike.
- The stage MUST be skipped with `single-source` when the documents hold no PCB document, and with `read-refused` when it could not be read.
- Rule kinds of the document that stayed opaque MUST give `copper.rules-incomplete` (warning) naming them.
- A polygon with poured regions MUST be checked as a filled zone. Unpoured polygons MUST be counted in `summary.unpoured`; when the count is not zero the stage MUST add one `copper.item-unsupported` (warning) with the count, and its evidence MUST be `UNVERIFIED`.
- The findings MUST use the codes and severities of "Copper stage issue codes" of `verification-loop`, unchanged.

#### Scenario: A short on an Altium board
- **GIVEN** the routed blink built for Altium, with one track moved by record edit so that it touches a pad of another net
- **WHEN** `fenolite check <dir> --stages copper.clearance --json` runs
- **THEN** the exit code is 5 and one `copper.short` names the two nets

#### Scenario: Unpoured polygons are said
- **GIVEN** a built board with two unpoured polygons and no other fault
- **WHEN** the stage runs
- **THEN** it reports one `copper.item-unsupported` with the count 2, `summary.unpoured` is 2, and its evidence level is `UNVERIFIED`

#### Scenario: Same board, two backends
- **WHEN** `uv run pytest tests/kicad/altium/test_copper_same.py` checks each sample built for KiCad and for Altium
- **THEN** the copper findings of the two readings are equal by kind, net pair and place within 2 nm

### Requirement: Parity on Altium projects
On document input that holds a PCB document and schematic documents, the stage `parity` SHALL compare them with `checks.parity.compare`, with the schematic side that the Altium backend builds from the import (`ParityInputs`): components by designator, the value from the comment, the footprint from the footprint model, the pins from the symbol and its pin-to-pad map, the nodes from the imported nets.
- The stage MUST be skipped with `no-schematic` without a schematic document and with `single-source` without a PCB document.
- Every finding MUST become an issue with the codes of "Parity issue codes"; `summary` MUST hold `netlist` = `own`, `compared` = `false` and the counts.
- `fenolite parity PATH` MUST accept an Altium project, a project folder or a PCB document with schematic documents beside it, with the same result shape; `--netlist kicad` on such input MUST exit 2.

#### Scenario: Renamed designator
- **GIVEN** the blink built for Altium whose board component `R1` was renamed `R99` by record edit
- **WHEN** `fenolite check <dir> --stages parity --json` runs
- **THEN** the exit code is 5, and the issues hold `parity.missing-footprint` at `R1` and `parity.extra-footprint` at `R99`

#### Scenario: Agreeing project
- **WHEN** `fenolite parity <blink built for Altium> --json` runs
- **THEN** the exit code is 0 and every summary count is 0
