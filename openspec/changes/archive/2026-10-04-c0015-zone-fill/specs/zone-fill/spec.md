## ADDED Requirements

### Requirement: Fills are lifted by zone uuid
`fenolite.backends.kicad.fill.lift_fills(original, refilled) -> LiftResult` SHALL return `original` with, for each zone, the `fills` and the `filled` flag of the zone of `refilled` that has the same id, and with nothing else changed.
- Zone settings, outlines, nets, layers, priorities, slots and every other entity MUST stay `original`'s, because they are inputs of the fill and `refilled` is in another format version.
- Rule areas MUST be left unchanged.
- `LiftResult.changed` MUST name, sorted, the ids of the zones whose fills or flag differ from `original`'s; fills compare as sets of `(layer, island, ring)` with each ring normalised to start at its smallest point.
- A zone of `original` that `refilled` lacks, or a zone of `refilled` that `original` lacks, MUST be named in `LiftResult.unmatched`, and `fill_board` MUST then report one `zone.fill-mismatch` (error) per id and return no text.

#### Scenario: Fills taken, settings kept
- **GIVEN** an authored model with one zone on `GND`, and a copy whose zone has two fills and another priority
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fill.py -k lift` calls `lift_fills`
- **THEN** the result's zone has the two fills and the original priority, and `changed` names it

#### Scenario: Zone missing in the refilled board
- **GIVEN** an original with zones `a` and `b` and a refilled copy with only `a`
- **WHEN** `fill_board` runs on their texts
- **THEN** it reports `zone.fill-mismatch` naming `b` and returns no text

#### Scenario: Already current
- **GIVEN** a board whose fills equal the refilled copy's
- **WHEN** `lift_fills` runs
- **THEN** `changed` is empty

### Requirement: Filled boards are written for their own major
`fill.fill_board(text, refilled_text, *, file="") -> FillResult` SHALL read both texts with `read_board`, lift the fills, and write the result with `write_board` for the major of `text` (`versions.inspect`), never for another one.
- A board older than KiCad 9 MUST be refused as c0017's writer refuses it (`FEN-7003`).
- The written text MUST pass `roundtrip.rt1`.
- Before returning, `fill_board` MUST read its own text back and require each zone's fills to equal the lifted ones; otherwise it MUST raise `FormatError` naming the zone.
- A second `fill_board` on its own output with the same refilled text MUST return the same bytes.

#### Scenario: Target 9 stays target 9
- **GIVEN** `tests/data/kicad/fill/triad_t9.kicad_pcb` and `triad_t9_refilled.kicad_pcb`, whose version is `20260206`
- **WHEN** `fill_board` runs
- **THEN** the text has `(version 20241229)`, equals `triad_t9_filled.kicad_pcb`, and its zone has the fills of the refilled copy

#### Scenario: Idempotent
- **WHEN** `fill_board` runs on `triad_t9_filled.kicad_pcb` with the same refilled copy
- **THEN** the text equals the input and `changed` is empty

### Requirement: Fill issue codes
`fill.ISSUE_CODES` SHALL map every code that `fill` emits to one severity, and SHALL hold at least: `zone.fill-mismatch` (error), `zone.fill-unstable` (warning), `zone.none` (info). Reader and writer codes MUST pass through unchanged. `docs/cli-contract.md` MUST document every key.

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** every key of `fill.ISSUE_CODES` appears in `docs/cli-contract.md`

### Requirement: Fill evidence
`fill.EVIDENCE` SHALL name `H-K-FILL-SAVE`, `H-K-FILL-LIFT` and `H-K-FILL-REPEAT`, SHALL start `INFERRED`, and SHALL become `KICAD-VERIFIED` only when the three rows are `KICAD-VERIFIED (10.0.x)`. A result of `fill` that ran `kicad-cli` MUST carry it with the oracle `kicad-cli <version>`; a result lifted with `--from` MUST carry `INFERRED`.

#### Scenario: Evidence follows the register
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fill.py -k evidence` reads `docs/hypotheses.md`
- **THEN** the level of `fill.EVIDENCE` is `KICAD-VERIFIED` exactly when the three rows are `KICAD-VERIFIED (10.0.x)`

### Requirement: Fill facts are documented
`docs/formats/kicad/board.md` SHALL record, each with a source, a label and a hypothesis: what the refill run saves, that zone uuids are kept, the format of the saved copy, and the 9.0.9 message for a fill without `filled_areas_thickness`. `docs/formats/kicad/cli.md` SHALL record the refill command and the container form.

#### Scenario: Fact rows checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes with the new rows
