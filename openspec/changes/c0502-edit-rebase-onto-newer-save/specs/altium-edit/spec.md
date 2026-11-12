## ADDED Requirements

### Requirement: Edit plan of a PCB session
`Session.plan() -> EditPlan` SHALL record the queued operations of a PCB edit session as canonical JSON of schema `fenolite.altium-edit-plan.v0`: the document's name and SHA-256, the declared nets, and per operation its ops-file entry (change c0497), gate, label, target identity, and the `base` and `result` fingerprints of its target (change c0502). Entries MUST hold only integers (nanometres, microdegrees), strings, booleans, null and lists or objects of them. An `add_component` source MUST be a path relative to the plan file with its SHA-256; a session given source bytes MUST raise `ValueError` from `plan()`. `plan()` MUST write nothing and MUST NOT depend on the gates. `EditPlan.read(text)` MUST raise `FormatError` for a text that is not of the schema or names an unknown operation.

#### Scenario: A plan written and read back
- **GIVEN** the kit board and a session that moves a track, sets a component's comment and adds a fill
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_plan.py -k round_trip` writes `session.plan()` and reads it back
- **THEN** the two plans are equal, the text holds no float and no absolute path, and writing it twice gives the same bytes

#### Scenario: Source bytes cannot be planned
- **WHEN** the test calls `plan()` on a session whose `add_component` was given bytes
- **THEN** it raises `ValueError` naming the operation

### Requirement: Edit targets found by stable identity
A replayed operation SHALL find its target by the `UNIQUEID` of a component or polygon where the document holds one, else by the item's content key (`ops.View.find`), and never by record index. A fingerprint MUST hold only the fields its operation reads or writes, as the document holds them, compared exactly.

#### Scenario: Records reordered and a component renamed
- **GIVEN** a plan made on the kit board that rotates `D1` and moves a track, and a copy of the board whose `Tracks6` records are reversed and whose `D1` is renamed `D7`
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_plan.py -k reordered` replays the plan on the copy and commits it
- **THEN** it is written: `D7` is rotated and the same track is moved, and no other record changes

### Requirement: Rebase onto a newer save
`edit.replay(plan, path, *, gates=None) -> Session` SHALL queue the plan's operations on the document at `path`, each after a three-way rebase step on the state the earlier operations left. A target whose fingerprint equals `base` MUST be edited as recorded. A target whose fingerprint equals `result`, or a missing target or creation whose `result` the document holds, MUST be skipped with `altium.edit.rebase-applied` (info). A target that changed otherwise MUST give `altium.edit.rebase-conflict` naming each field with its base and current value. A missing target MUST give `altium.edit.rebase-missing`. Any conflict or missing target MUST refuse the commit with every such issue listed, and nothing MUST be written or applied in part.

#### Scenario: Unrelated changes in the newer save
- **GIVEN** a plan that moves one track, and a newer save in which another track was moved and a via added
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_plan.py -k unrelated` replays it and commits
- **THEN** it is written with both the user's changes and the plan's move

#### Scenario: The target changed in the newer save
- **GIVEN** a plan that sets the width of a track from 0.25 mm to 0.5 mm, and a newer save in which the user set it to 0.3 mm
- **WHEN** the test replays it and commits
- **THEN** the exit code is 5, the issues hold one `altium.edit.rebase-conflict` naming `width` with 0.25 mm and 0.3 mm, and nothing is written

#### Scenario: The target deleted in the newer save
- **WHEN** the test replays a plan that moves a track the newer save no longer holds
- **THEN** the commit is refused with `altium.edit.rebase-missing` naming the track, and nothing is written

#### Scenario: A plan replayed on its own result
- **GIVEN** the document a committed plan wrote
- **WHEN** the test replays the same plan on it
- **THEN** every operation is skipped with `altium.edit.rebase-applied`, and the written bytes equal the input's

### Requirement: Rebase issue codes
`EDIT_ISSUE_CODES` SHALL hold `altium.edit.rebase-conflict` (error), `altium.edit.rebase-missing` (error) and `altium.edit.rebase-applied` (info), and `fenolite explain` SHALL explain each.

#### Scenario: Codes explained
- **WHEN** `fenolite explain altium.edit.rebase-conflict --json` runs
- **THEN** the exit code is 0 and the reply says how to drop or update the conflicting operation in the plan file
