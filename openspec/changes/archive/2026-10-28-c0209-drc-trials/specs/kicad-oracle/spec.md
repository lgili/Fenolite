## ADDED Requirements

### Requirement: Trial edits judged by DRC
`fenolite.api.trial(board, edit, *, kicad_cli=None, refill=True, gate=False) -> TrialResult` SHALL apply `edit`, a callable that returns the edited board model and the ids of the items it added, removed or changed, write the unedited and the edited model for the board's major, run `kicad-cli` DRC on a copy of each with the project files, and return the entries only the edited copy holds, counted by type and item uuid set, each with the edit ids it names.

#### Scenario: A new clearance names the edit's track
- **GIVEN** the authored bench of `tests/kicad/check/test_trial.py` and an edit adding two tracks, one 0.1 mm from two pads of other nets
- **WHEN** `uv run pytest tests/kicad/check/test_trial.py -k maps` runs the trial without the gate
- **THEN** every new finding is a `clearance` that names only the second track and a pad of `R5`, and both tracks are kept

### Requirement: Trial gate
With `gate=True`, `trial` SHALL drop the edit's items that new findings name, removing an added item and putting back a changed or removed one, and run again until no new finding names an item of the edit or none is left to drop. `TrialResult.board_text` MUST then be the board to write, `kept` and `dropped` MUST split the edit's ids, and each dropped item MUST carry its findings. Nothing is written.

#### Scenario: One offending track dropped
- **GIVEN** the bench and the edit of "A new clearance names the edit's track"
- **WHEN** `uv run pytest tests/kicad/check/test_trial.py -k gate` runs the trial with `gate=True`
- **THEN** the result is clean after three runs, its board holds the first track only, and `dropped` names the second track with its `clearance` finding

### Requirement: Trial refill and tool
With `refill=True`, `trial` SHALL check both copies with `pcb drc --refill-zones` on KiCad 10; on KiCad 9 a board with zones MUST give `trial.not-refilled` (warning) and keep the stored fills. Without a `kicad-cli`, `trial` MUST raise `ToolMissingError` (`FEN-6001`).

#### Scenario: Zones refilled before the trial
- **GIVEN** a zone whose stored fill covers its outline, and an edit laying a track of another net across it
- **WHEN** `uv run pytest tests/kicad/check/test_trial.py -k refill` runs the trial with and without `refill` on KiCad 10
- **THEN** the refilled trial has no `clearance` or `shorting_items` finding and the other has one

#### Scenario: No tool
- **WHEN** `uv run pytest tests/unit/api/test_trial_api.py -k without_kicad_cli` runs a trial with no `kicad-cli` found
- **THEN** it raises `ToolMissingError` with `FEN-6001`

### Requirement: DRC exclusions written
`fenolite check BOARD --exclude CODE:ITEM_A[:ITEM_B] --reason TEXT` SHALL store a KiCad DRC exclusion of the one finding that `CODE` (type or `kicad.drc.*` code) and the items (uuids or `where` names, either order) name in `<stem>.kicad_pro`, under the mutation protocol, in both item orders, with the reason as comment, at the marker position found by probe keys on a copy, and only after a run on a copy shows the entry excluded.

#### Scenario: An accepted unconnected item
- **GIVEN** the authored bench of `tests/kicad/check/test_exclusions_write.py` with two tracks of one net 1 mm apart
- **WHEN** `uv run pytest tests/kicad/check/test_exclusions_write.py -k accepted` writes the exclusion and runs `fenolite check --stages drc.kicad`
- **THEN** the two keys sit at the end of the first track, the entry is excluded with the reason, and `summary.accepted` lists the exclusion as live

### Requirement: Exclusion lookup refusals
`check --exclude` MUST plan no write and exit 5 when no entry matches (`check.exclusion-unmatched`), when several do (`check.exclusion-ambiguous`) or when no probe key applies (`check.exclusion-unlocated`); when both keys are stored it MUST plan nothing and give `check.exclusion-present` (info). Without `--reason` or with `--stages` it MUST exit 2, and without a `kicad-cli` exit 6, writing nothing.

#### Scenario: An exclusion that matches nothing
- **WHEN** `uv run pytest tests/kicad/check/test_exclusions_write.py -k unmatched` excludes a clearance between a track and a via that are far apart
- **THEN** the exit code is 5 with `check.exclusion-unmatched`, and a dry run of a valid exclusion leaves the project file unchanged

#### Scenario: Usage errors and no tool
- **WHEN** `uv run pytest tests/unit/cli/test_check_exclude.py` runs the usage errors and an exclusion without `kicad-cli`
- **THEN** each usage error exits 2, the run without a tool exits 6, and no file changes

### Requirement: Written exclusions judged
The `drc.kicad` stage SHALL judge two stored keys of one type, position and item pair in both orders as one exception: both live when the report marks an entry of that type naming the two items, in either order, as excluded; else both unjudged for `clearance`, `hole_clearance`, `unconnected_items` and `shorting_items`, or without a report; else both stale with one `check.exclusion-stale`. `summary.accepted` MUST list each such exception.

#### Scenario: Mirrored keys without a tool
- **WHEN** `uv run pytest tests/unit/checks/test_drc_accepted.py` judges mirrored keys against reports
- **THEN** an excluded unconnected entry in either order makes both keys live, an absent one leaves them unjudged, and a repeatable type gives one stale warning

### Requirement: Written exclusion facts
`tests/kicad/check/test_exclusions_write.py` SHALL pin, on the running `kicad-cli`, the facts the writer relies on (`docs/formats/kicad/drc.md`, "Written exclusions"; `H-K-DRC-EXCLUSION`): a missing-connection key applies at its marker in either uuid order, and a clearance key only in the report's order at the first item's position, also when the uuid order makes the report name the items the other way.

#### Scenario: Key order on the running major
- **WHEN** `uv run pytest tests/kicad/check/test_exclusions_write.py -k order` runs on `kicad-cli`
- **THEN** both orders of the unconnected key apply, and of the four clearance keys only the report-order key at the first item's position does
