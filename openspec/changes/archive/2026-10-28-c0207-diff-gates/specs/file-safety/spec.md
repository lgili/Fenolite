## ADDED Requirements

### Requirement: Gated differences
`fenolite diff A B --allow KINDS` SHALL report each change of the model view whose kind (the first segment of its path) is not in the comma-separated `KINDS` as one `diff.not-allowed` error whose `where` is the change's path, so the exit code is 5.
- An unknown kind, and `--allow` outside the model view, MUST exit 2 with `FEN-2001`.

#### Scenario: A change outside the allowed set
- **GIVEN** two designs read from the authored two-layer board, one with a track moved and a rule changed
- **WHEN** `uv run pytest tests/unit/checks/test_diff_gate.py -k outside` gates their difference with the kind `track`
- **THEN** each `diff.not-allowed` error names the rule change, and none names the track

#### Scenario: The command exits 5
- **GIVEN** a copy of the authored two-layer board with a track moved and the footprint R1 moved
- **WHEN** `uv run pytest tests/unit/cli/test_diff_gates.py -k outside` runs `fenolite diff <board> <copy> --allow track --json`
- **THEN** the exit code is 5 and the one issue is `diff.not-allowed` at `/footprint/R1/position`

### Requirement: Three-way difference of KiCad boards
`fenolite diff BASE OURS --three-way THEIRS --out FILE` SHALL plan `FILE` as `THEIRS` with the root items that changed from `BASE` to `OURS` applied, under the mutation protocol.
- Items MUST be matched by `<head> <uuid>`, else by a head each board holds at most once, else by their text.
- `FILE` MUST keep the bytes of every item of `THEIRS` that the merge does not change.
- The four paths MUST be `.kicad_pcb` files, else exit 2 with `FEN-2001`.

#### Scenario: Changes of two sides are merged
- **GIVEN** three saves of an authored board: OURS moves a track and adds one, THEIRS moves a footprint
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_merge.py -k merged` merges them
- **THEN** the merged board is THEIRS with the two tracks of OURS spliced in, and its model difference from THEIRS is the one from BASE to OURS

#### Scenario: The merge is a planned write
- **GIVEN** the same three boards
- **WHEN** `uv run pytest tests/unit/cli/test_diff_gates.py -k protocol` runs the merge without, then with `--confirm`
- **THEN** the first run exits 4 with the plan of `merged.kicad_pcb`, and the second writes it

### Requirement: Three-way conflicts
`fenolite diff BASE OURS --three-way THEIRS --out FILE` SHALL report one `diff.conflict` error for each item changed from `BASE` to `OURS` that `THEIRS` changed otherwise, and SHALL then write nothing (exit 5).
- An item that `THEIRS` already holds as in `OURS` MUST be `already`, not a conflict.
- Boards of two versions, or whose numbered net tables differ, MUST be `diff.unmergeable` (error).

#### Scenario: An item changed on both sides
- **GIVEN** three saves of an authored board where OURS and THEIRS move one track to two places
- **WHEN** `uv run pytest tests/unit/cli/test_diff_gates.py -k conflict` runs the merge with `--confirm`
- **THEN** the exit code is 5, the one issue is `diff.conflict` naming that track, and no file is written

### Requirement: Resave differences of Altium documents
In `fenolite diff A B --view records`, a changed record whose differing keys all hold values that decode to equal values within the format's units SHALL be classified `resave`: counted in `result.resave` and left out of `differences`.
- A key that holds free text MUST be compared as written.

#### Scenario: A resaved record
- **GIVEN** two authored schematics whose wire differs only by `X1=10` against `X1=10.0` and `T` against `TRUE`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_resave.py -k left_out` compares their records
- **THEN** the wire is classified `resave`, and only the changed text of a label stays in the difference
