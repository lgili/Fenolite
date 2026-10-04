## MODIFIED Requirements

### Requirement: Capability reports
`capabilities()` SHALL return `CapabilityReport(name, read_kinds, write_kinds, targets, default_target, downgrade, operations, evidence)`, and `CapabilityReport.to_json()` SHALL return a JSON-compatible mapping with exactly these keys, `evidence` written as `{level, oracle, hypotheses}`. Each field MUST describe what the backend implements when the report is made, so that the report stays true as later changes add writers:
- `operations` MUST list exactly the operations the backend implements, from `detect`, `read`, `write`, `lower` and `validate`. `detect` and `read` MUST always be listed.
- `read_kinds` MUST list exactly the file kinds that `read` accepts. The KiCad report MUST contain `kicad_pcb`, `kicad_mod` and `kicad_sym`.
- `write_kinds` MUST list exactly the file kinds the backend can write. While it is empty, `write` MUST NOT be in `operations`, `targets` MUST be empty and `default_target` MUST be `None`.
- `downgrade` MUST be `"unsupported"` unless the backend can write a file read at a newer version for an older target.
- `evidence` MUST be what the backend's operations return for an arbitrary file, not the level of the best-tested case. The KiCad report's evidence MUST be `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`, computed and not written as a literal.
- For every registered backend, each hypothesis the report names MUST be a row of `docs/hypotheses.md` that is not refuted, and the report's level MUST NOT be stronger than the level of any of those rows. The level MAY be weaker than every row: a row states what its test covered, and the report states what holds for any file. `tests/unit/test_capability_evidence.py` SHALL check both rules with `report_problems(evidence, rows)`, which returns one message per problem.

#### Scenario: KiCad capability report
- **WHEN** `KicadBackend().capabilities().to_json()` is called
- **THEN** it has exactly the eight keys, `name` is `kicad`, `read_kinds` contains `kicad_pcb`, `kicad_mod` and `kicad_sym`, `operations` contains `detect` and `read`, and the evidence level is `INFERRED`

#### Scenario: Unavailable operations are visible
- **GIVEN** every registered backend
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k capability_invariants` checks its report
- **THEN** every listed operation is a method of the backend, and a backend with an empty `write_kinds` lists no `write`, has empty `targets` and has `default_target` `None`, so an agent knows it cannot write

#### Scenario: Report follows its operations
- **WHEN** `uv run pytest tests/unit/test_capability_evidence.py -k operations` compares `KicadBackend().capabilities().evidence` with `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`
- **THEN** they are equal, and the source of `backends/kicad/backend.py` holds no `Level.` literal

#### Scenario: Report stronger than the register
- **GIVEN** an evidence of level `KICAD-VERIFIED` that names `H-K-PCB-READ`, and a register in which that row is `CORPUS-VERIFIED`
- **WHEN** `report_problems(evidence, rows)` is called
- **THEN** it returns one problem naming `H-K-PCB-READ`, `KICAD-VERIFIED` and `CORPUS-VERIFIED`

#### Scenario: Unregistered or refuted hypothesis
- **GIVEN** an evidence that names an id with no row, and one that names a row whose result starts with `refuted`
- **WHEN** `report_problems(evidence, rows)` is called for each
- **THEN** each call returns one problem naming the id

#### Scenario: Live reports agree with the register
- **WHEN** `uv run pytest tests/unit/test_capability_evidence.py -k live` checks every backend of `registry.all_backends()` against `docs/hypotheses.md`
- **THEN** it finds no problem
