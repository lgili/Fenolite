## 1. Entry

- [x] 1.1 Validate this change and confirm that c0302's run routes, guard, jobs and runner core are on the branch (this change depends on them). Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0303-viewer-actions --strict --no-interactive`; `uv run pytest tests/unit/view/test_server.py -k run -q -n 2`.

## 2. Allow-list and guard

- [x] 2.1 Add `fenolite.view.actions` with `ACTIONS`, the templates, the typed options, the root confinement of outputs and the Altium refusal (requirement "Allowed actions", scenario "Refused actions"). Proof: `uv run pytest tests/unit/view/test_actions.py tests/unit/test_import_graph.py -q -n 2`.
- [x] 2.2 Add `--allow-actions`, the session token, `GET /actions` and the action guard; refuse every action route without the option (requirements "Writing actions are opt-in", "Action request guard", "View command allows writing actions"). Proof: `uv run pytest tests/unit/view/test_server.py -k "actions_off or action_guard" tests/unit/cli/test_view_cmd.py -k allow_actions -q -n 2`.

## 3. Plan, confirm, undo

- [x] 3.1 Add `POST /action/plan`: the dry run through the runner core, the plan check against the command and the root, and the preview from the staged board (scenario "A designator plan previewed"). Proof: `uv run pytest tests/unit/cli/test_view_actions.py -k silk_plan -q -n 2`.
- [x] 3.2 Add `POST /action/confirm` for plans of the session, with `FEN-4002` passed through (scenario "The file changed after the review"). Proof: `uv run pytest tests/unit/cli/test_view_actions.py -k "confirm or changed" -q -n 2`.
- [x] 3.3 Keep the receipts, write them to the state folder, add `POST /action/undo` through `restore`, and `result.serve.writes` (scenarios "Write and undo", "Receipts in the reply"). Proof: `uv run pytest tests/unit/cli/test_view_actions.py -k "undo or reply" -q -n 2`.
- [ ] 3.4 Cover `move`, `shift` and `turn` (one moved part in the preview), `export` and `bom` (writes under `fab/` only) and `testpoints`; mark `fill` and `tidy --gate drc` as needing `kicad-cli`. Proof: `uv run pytest tests/unit/cli/test_view_actions.py -q -n 2`; the KiCad CI jobs for the tests that need `kicad-cli`.

  Reopened 2026-11-03: the pure move/export-boundary/testpoints controls exist,
  but CI 985f59a1 did not execute the three native action cases. All five unit
  jobs lacked kicad-cli and skipped them; native 9 collected tests/kicad only,
  native 10 collected tests/kicad and tests/corpus only. The original export,
  fill and tidy tests remain in tests/unit/cli/test_view_actions.py. Their
  native CI proof is pending; passing visual/fake-runner cases do not replace it.
- [x] 3.5 Before completing the remaining native proof of 3.4, add an explicit
  three-node native-action step to each pinned KiCad 9/10 job. Keep the original
  test bodies, assertions, fixtures, fill minimum-major 10 skip, main suite commands
  and deferred geometry manifest unchanged. Require kicad-cli in the new step,
  and extend the existing strict workflow checker with mutations that remove
  each selected node. Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`;
  collect only the three original nodeIDs; focused Ruff/format, strict OpenSpec,
  diff and private residue checks. Expected later native execution: 9 collects 3,
  runs export/tidy and skips fill; 10 runs all 3. Local collection/checks do not
  complete 3.4 or closing task 6.1, which await actual native CI.


  Local proof 2026-11-03: the existing workflow checker first reproduces the
  missing collection with 3 failures/49 passes on the unchanged workflow.
  After the two explicit steps and guards, all 53 focused workflow tests pass
  (0.28 s), including removal of each node in each job (six mutations) and
  removal of the CLI requirement in each focused step (two mutations).
  Collect-only reports exactly the three original nodes (0.53 s); it executes
  no test body or CAD. Ruff, format, strict OpenSpec and diff checks pass;
  staged private residue scans four changed files with zero hits, gate on.
  Original native test bytes, the fill-on-9 skip and geometry deferral manifest
  are unchanged; removing only the two new steps reproduces the base workflow
  byte for byte. Task 3.4 and closing 6.1 remain open for the real native CI.

## 4. Page

- [x] 4.1 Add the Actions group, the forms, the inspector actions (Move or rotate, Move with copper, Waive finding), the review dialog with the board preview, Confirm, the receipt view with reload, Undo and Review again on `FEN-4002`; no action control on exported pages or when actions are not enabled. Proof: `uv run pytest tests/visual/test_actions.py tests/visual/test_run.py -q` in the `viewer` CI job.
- [x] 4.2 (found in testing, 2026-10-29) Do not offer Waive on a finding of a check of an earlier revision of the file (the report's binding does not match the document, or its digest differs from the scene's): the review and the inspector say why and offer Run again. Proof: `uv run pytest tests/visual/test_actions.py -k older_revision -q` in the `viewer` CI job.
- [x] 4.3 (found in testing, 2026-10-29) After an action writes a project file the checks read (a waiver writes `.kicad_pro`, not the board, so the board's digest still matches), mark that document's review results stale until a check runs again, and offer Run again (the document's last run) in the run strip, the Project review and the inspector; Waive is not offered meanwhile. Proof: `uv run pytest tests/visual/test_actions.py -k stale -q` in the `viewer` CI job.

## 5. Teaching and documentation

- [x] 5.1 Add a tested line for `--allow-actions` to the closest page of the agent guide and regenerate the command guide; update `docs/viewer.md` (a section "Actions" with the security notes and undo) and `docs/cli-contract.md` ("view"). Proof: `uv run pytest tests/unit/agent -q -n 2`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch, `viewer` and the KiCad jobs included.
- [x] 6.2 Confirm that each action's reply keeps its command's evidence and that no label of the matrix changes. Proof: `uv run pytest tests/unit/cli/test_view_actions.py -k evidence -q -n 2`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.

Open on the branch (2026-10-29): 6.1 waits for `make check-fast` on the maintainer's machine and the CI jobs (only focused tests ran here: ruff, ruff format, pyright of the changed packages, the residue scan, `tests/unit/view`, `tests/unit/cli/test_view_cmd.py`, the new tests, `tests/unit/agent`, `tests/consistency`, `tests/unit/mcp`, `tests/visual`). 6.3: the entry is written under `## [Unreleased]`, but `tests/unit/test_release_record_v06.py::test_changelog_section` requires `[Unreleased]` empty while `fenolite.__version__` is still `0.6.0`; it passes once the version moves on.

Changelog proof, 2026-11-01, source `b02e09fe`: the literal `uv run pytest tests/unit -k "release_record or changelog" -q -n 2` passed 167 cases with one optional MCP SDK skip. The existing Unreleased entry names this change; no extra entry is added. Complete fast-gate and exact CI tasks remain open.
