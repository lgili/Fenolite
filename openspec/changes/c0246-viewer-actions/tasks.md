## 1. Entry

- [x] 1.1 Validate this change and confirm that c0245's run routes, guard, jobs and runner core are on the branch (this change depends on them). Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0246-viewer-actions --strict --no-interactive`; `uv run pytest tests/unit/view/test_server.py -k run -q -n 2`.

## 2. Allow-list and guard

- [x] 2.1 Add `fenolite.view.actions` with `ACTIONS`, the templates, the typed options, the root confinement of outputs and the Altium refusal (requirement "Allowed actions", scenario "Refused actions"). Proof: `uv run pytest tests/unit/view/test_actions.py tests/unit/test_import_graph.py -q -n 2`.
- [ ] 2.2 Add `--allow-actions`, the session token, `GET /actions` and the action guard; refuse every action route without the option (requirements "Writing actions are opt-in", "Action request guard", "View command allows writing actions"). Proof: `uv run pytest tests/unit/view/test_server.py -k "actions_off or action_guard" tests/unit/cli/test_view_cmd.py -k allow_actions -q -n 2`.

## 3. Plan, confirm, undo

- [ ] 3.1 Add `POST /action/plan`: the dry run through the runner core, the plan check against the command and the root, and the preview from the staged board (scenario "A designator plan previewed"). Proof: `uv run pytest tests/unit/cli/test_view_actions.py -k silk_plan -q -n 2`.
- [ ] 3.2 Add `POST /action/confirm` for plans of the session, with `FEN-4002` passed through (scenario "The file changed after the review"). Proof: `uv run pytest tests/unit/cli/test_view_actions.py -k "confirm or changed" -q -n 2`.
- [ ] 3.3 Keep the receipts, write them to the state folder, add `POST /action/undo` through `restore`, and `result.serve.writes` (scenarios "Write and undo", "Receipts in the reply"). Proof: `uv run pytest tests/unit/cli/test_view_actions.py -k "undo or reply" -q -n 2`.
- [ ] 3.4 Cover `move`, `shift` and `turn` (one moved part in the preview), `export` and `bom` (writes under `fab/` only) and `testpoints`; mark `fill` and `tidy --gate drc` as needing `kicad-cli`. Proof: `uv run pytest tests/unit/cli/test_view_actions.py -q -n 2`; the KiCad CI jobs for the tests that need `kicad-cli`.

## 4. Page

- [ ] 4.1 Add the Actions group, the forms, the inspector actions (Move or rotate, Move with copper, Waive finding), the review dialog with the board preview, Confirm, the receipt view with reload, Undo and Review again on `FEN-4002`; no action control on exported pages or when actions are not enabled. Proof: `uv run pytest tests/visual/test_actions.py tests/visual/test_run.py -q` in the `viewer` CI job.

## 5. Teaching and documentation

- [ ] 5.1 Add a tested line for `--allow-actions` to the closest page of the agent guide and regenerate the command guide; update `docs/viewer.md` (a section "Actions" with the security notes and undo) and `docs/cli-contract.md` ("view"). Proof: `uv run pytest tests/unit/agent -q -n 2`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch, `viewer` and the KiCad jobs included.
- [ ] 6.2 Confirm that each action's reply keeps its command's evidence and that no label of the matrix changes. Proof: `uv run pytest tests/unit/cli/test_view_actions.py -k evidence -q -n 2`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.
