## ADDED Requirements

### Requirement: Edit plan through the ops file
`fenolite edit PATH.PcbDoc --ops-file FILE` (change c0497) SHALL report the edit plan of a run on a list of entries in `result.edit_plan` (`fenolite.altium-edit-plan.v0`), and SHALL take such a plan as `FILE`, replaying it on the board as it is now through the write protocol (change c0502).
- A plan that does not read MUST exit 3 with `FEN-3004`.
- With a plan, `result` MUST hold `base_sha256`, `document_sha256`, `rebased`, and `operations`, one row per operation with `label` and `status` (`applied`, `already-applied`, `conflict`, `missing`), and `fields` for a conflict.
- Rebase conflicts and missing targets MUST be `issues` beside the session's; with an error no write MUST be planned and the exit code MUST be 5.
- The write MUST depend on the board, the plan and every `add_component` source, so a board saved again after the dry run MUST make `--confirm --plan ID` exit 4 with `FEN-4002`, and a new `--dry-run` with the same plan file MUST rebase it onto the newer save.

#### Scenario: A plan confirmed after a newer save
- **GIVEN** a copy of the kit board and an ops file that moves one track
- **WHEN** `uv run pytest tests/unit/cli/test_edit_altium_cmd.py -k newer_save` runs `--dry-run --gate move`, saves `result.edit_plan` as `plan.json`, changes another track of the board, runs `--confirm --plan ID`, then runs `--ops-file plan.json --gate move` with `--dry-run` and with `--confirm --plan`
- **THEN** the first confirmation exits 4 with `FEN-4002` and writes nothing, the dry run of the plan reports `rebased: true` and the move `applied`, and its confirmation writes a board holding both changes

#### Scenario: A conflict plans no write
- **WHEN** the test runs `--dry-run` with a plan whose target the board changed
- **THEN** the exit code is 5, `issues` hold `altium.edit.rebase-conflict`, and `result.plan` holds no write
