# Tasks: c0502-edit-rebase-onto-newer-save

Rules for every task:

- The board this was found on is private. Nothing from it (names, nets, coordinates, files) goes into
  tests, fixtures, commits or messages. A "newer save" in the tests is a copy of the Part J kit board that
  the test changes itself.
- No float in a plan: lengths in nanometres, angles in microdegrees.
- Run each touched test file alone with `-n 0`.

## 1. Operations as data

- [ ] 1.1 After c0497 is merged: `session._Queued` keeps the ops-file entry each public `Session` method
  queues, in integer nm and microdegrees (design D1). A test queues every operation, turns the entries back
  into a session with c0497's reader, and gets the same written bytes. No behaviour change.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit -q -n 0`

## 2. Plan, identity, fingerprint

- [ ] 2.1 `ops.fingerprint(view, op, item)` with the field table of design D2, and the identity lookup
  (`UNIQUEID` first, then the content key).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_plan.py -k "fingerprint or reordered" -q -n 0`
- [ ] 2.2 `edit/plan.py`: `EditPlan`, `Session.plan()`, `EditPlan.read` and the canonical JSON of design D3;
  scenarios of "Edit plan of a PCB session". Generate the schema.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_plan.py -k "round_trip or source_bytes" -q -n 0`
  - Proof: `uv run python tools/gen_schemas.py --check`

## 3. Replay and rebase

- [ ] 3.1 `edit.replay` with the three-way step of design D4 and the three codes in `EDIT_ISSUE_CODES`;
  scenarios of "Rebase onto a newer save".
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_plan.py -q -n 0`
- [ ] 3.2 Explain the three codes in `src/fenolite/cli/data/explain.toml`.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_explain_cmd.py -q -n 0`

## 4. CLI

- [ ] 4.1 c0497's `fenolite edit PATH.PcbDoc --ops-file` reports `result.edit_plan` and reads an edit plan
  (design D5); scenarios of "Edit plan through the ops file". Regenerate the result schema.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_edit_altium_cmd.py tests/unit/cli/test_edit_cmd.py -q -n 0`
  - Proof: `uv run python tools/gen_schemas.py --check`
- [ ] 4.2 Regenerate the agent guide for the changed arguments of `edit`.
  - Proof: `uv run python tools/gen_agent_guide.py --check`

## 5. Kit check

- [ ] 5.1 Replay a plan made on the kit board of case J1 onto its re-saved copy (`J01-resave.PcbDoc`, kept
  outside the repository) and open the result in Altium Designer 24.5.2.23. Record the operation statuses
  and what Altium shows in `docs/evidence/altium-edit.md`, beside J1.
  - Proof: `uv run --extra dev pytest tests/unit/test_altium_verification_docs.py -k part_j -q -n 0`

## 6. Docs, guide, changelog

- [ ] 6.1 `docs/cli-contract.md`, "edit": the plan file, `result.edit_plan` and the rebase after `FEN-4002`.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_edit_cmd.py tests/unit/cli/test_edit_altium_cmd.py -q -n 0`
- [ ] 6.2 Teach the plan file, `fenolite edit BOARD.PcbDoc --ops-file PLAN.json` after a newer save and the
  three rebase codes in `src/fenolite/agent/skill/references/altium.md` (one tested command line).
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 6.3 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
