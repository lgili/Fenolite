## ADDED Requirements

### Requirement: Finding subjects
`fenolite.checks.stages.StageResult` SHALL gain `subjects: tuple[tuple[Subject, ...], ...] = ()`, empty or of the length of `issues`, where `checks.subjects.Subject(kind, id, name)` names one model entity: `kind` in the closed tuple `SUBJECT_KINDS`, `id` its model id and `name` its human form (`U1`, `U1-4`, `3V3`). Non-empty `subjects` of another length than `issues` MUST raise `ValueError`.

#### Scenario: Misaligned subjects refused
- **WHEN** `uv run pytest tests/unit/checks/test_subjects.py -k misaligned` builds a `StageResult` with two issues and one subject tuple
- **THEN** `ValueError` is raised

#### Scenario: Closed kinds
- **WHEN** `SUBJECT_KINDS` is read
- **THEN** it is `component`, `pin`, `pad`, `net`, `netclass`, `interface`, `track`, `arc`, `via`, `zone`, `rule_area`, `rule`

### Requirement: Subjects in the check result
`fenolite check` SHALL put in `result.subjects` one `{issue, items}` per issue that has subjects, `issue` being its index in the envelope's `issues` and `items` its subjects as `{kind, id, name}`, in the order of the issues. The envelope and its issue object MUST NOT change, and the output MUST stay deterministic.

#### Scenario: Envelope unchanged
- **WHEN** `uv run pytest tests/consistency -k envelope` validates every command's reply
- **THEN** every issue object still has exactly the keys `code`, `severity`, `message`, `where`, `hint` and `retryable`

### Requirement: Stages that name their subjects
The stages `circuit.rules` (c0253), `copper.clearance`, `length.rules`, `placement.rules` and `roles.rules` SHALL give subjects for each of their issues that names a model entity.

#### Scenario: A rating finding names its part and net
- **GIVEN** an authored built project whose capacitor `C1` is rated below its rail `V12` (c0253)
- **WHEN** `uv run pytest tests/unit/checks/test_subjects.py -k rating` runs `fenolite check <dir> --stages circuit.rules --json`
- **THEN** `result.subjects` holds one entry whose `issue` is the index of that finding and whose items are the component `C1` and the net `V12` with the ids that `fenolite.dsl.KEYS` derives

#### Scenario: A length finding names its net
- **GIVEN** the pair-skew project of `tests/_lengthbench.py`
- **WHEN** `uv run pytest tests/unit/checks/test_subjects.py -k length` runs the stage `length.rules`
- **THEN** the `length.skew-out-of-range` issue has the subjects `SK_P` and `SK_N` of kind `net`

#### Scenario: Visible indices after concise output and pagination
- **GIVEN** findings with subjects, including multiple findings of one code
- **WHEN** check uses --format concise or --limit and --cursor
- **THEN** subject indices refer to the visible issues and a concise finding retains the subjects of all grouped findings
