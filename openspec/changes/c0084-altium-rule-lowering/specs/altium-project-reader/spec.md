## ADDED Requirements

### Requirement: More rule kinds onto the neutral model
The reading of Altium rules onto the neutral model SHALL map every kind that `rulemap.TABLE` marks `exact`, from rule records of a PCB document and from rule files alike, and `PENDING_KINDS` SHALL hold no kind of the table.
- A rule of a mapped kind whose scope is outside the closed grammar MUST stay listed with the reason it is not mapped, as today.
- Kinds outside the table MUST stay opaque and counted.

#### Scenario: Board outline clearance
- **GIVEN** a corpus PCB document whose rules hold a board outline clearance for all objects
- **WHEN** it is imported
- **THEN** the neutral rules hold that edge clearance, and the import lists no pending kind

### Requirement: Rule file written
`fenolite.backends.altium.read.rul.write_rule_file(rules)` SHALL return the text of an Altium rule file that holds the lowered rules, in the form that `read_rule_file` reads.
- `read_rule_file(write_rule_file(rules))` mapped onto the neutral model MUST give the lowered subset of `rules`.
- The text MUST use the line ends and the encoding that `docs/formats/altium/rule-file.md` records for files that Altium imports.

#### Scenario: Written file reads back
- **WHEN** `uv run pytest tests/unit/exports/test_altium_rul.py -k readback` writes and reads the rules of every example script
- **THEN** the rules read equal the lowered subset
