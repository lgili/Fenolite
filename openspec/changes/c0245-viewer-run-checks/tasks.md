## 1. Entry

- [x] 1.1 Validate this change; decide whether `cli/_viewrun.py` reuses `fenolite.mcp.backend.FenoliteBackend` or a runner core moved to a shared `fenolite.cli` module (design, "Risks"), and record the decision here. Decision: the runner core (`_run`, `_wait`, `_stop`, `_stderr`) moves to `fenolite.cli.childrun.run_child`, which `FenoliteBackend._run` now calls; `cli/_viewrun.py` uses that core directly and the MCP `Catalog` only to build the words of a run from the command's parser, so the viewer does not depend on the MCP server's call and image handling, and c0246's action templates use the same core. `view` imports nothing new. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0245-viewer-run-checks --strict --no-interactive`; `uv run pytest tests/unit/mcp tests/unit/test_import_graph.py -q -n 2`.

## 2. Allow-list and guard

- [x] 2.1 Add `fenolite.view.runs` with `ALLOWED`, `request(body, tree)` and the runner protocol, standard library only (requirement "Allowed run commands", scenario "Refused requests"). Proof: `uv run pytest tests/unit/view/test_runs.py tests/unit/test_import_graph.py -q -n 2`.
- [x] 2.2 Factor the `/marks` guard into one function and apply it to the run routes with `X-Fenolite-Run` and the 16 KiB limit (requirement "Run request guard", scenario "A request from another origin"). Proof: `uv run pytest tests/unit/view/test_server.py -k "guard or marks" -q -n 2`.

## 3. Jobs and runner

- [x] 3.1 Add the jobs to `Live` and the routes `GET /runs`, `POST /run`, `GET /run/<job>`, `POST /run/<job>/cancel` with a fake runner in tests (scenarios "One run at a time", "Cancel a blocked run"). Proof: `uv run pytest tests/unit/view/test_server.py -k run -q -n 2`.
- [x] 3.2 Add `cli/_viewrun.py`, the child-process runner with timeout, cancel and progress, and pass it from `cmd_view` to `Live` (scenario "A check run from the page"). Proof: `uv run pytest tests/unit/view/test_server.py -k run_check -q -n 2`.
- [x] 3.3 Add `--run-timeout`, `--no-run` and `result.serve.runs` to `fenolite view` (requirement "View command runs read-only commands"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -k "run_options or runs_counted" -q -n 2`.

## 4. Results

- [x] 4.1 Add `project_review.merge` and derive the review, the check overlay, the `analyze` groups and the `ready` and `equivalent` findings of a finished job (requirement "Run results in the review", scenario "Stages merged by name"). Proof: `uv run pytest tests/unit/view/test_project_review.py tests/unit/view/test_check_overlay.py tests/unit/view/test_server.py -k "merge or result" -q -n 2`.

## 5. Page

- [ ] 5.1 Add the Run controls of the cards, the Run menu and palette commands with their forms from `GET /runs`, the run strip with progress and Cancel, and polling under the navigation guard; no control on exported or `--no-run` pages (scenarios "A failed DRC card from a run", "An exported page"; requirement "Runs only on request in a live server"). Proof: `uv run pytest tests/visual/test_run.py tests/visual/test_project_review.py -q` in the `viewer` CI job.

## 6. Teaching and documentation

- [ ] 6.1 Add tested lines for `--run-timeout` and `--no-run` to the closest page of the agent guide and regenerate the command guide; update `docs/viewer.md` ("Project review": running checks from the page) and `docs/cli-contract.md` ("view"). Proof: `uv run pytest tests/unit/agent -q -n 2`; `uv run python tools/gen_agent_guide.py --check`.

## 7. Closing

- [ ] 7.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch, `viewer` and the KiCad jobs included.
- [ ] 7.2 Confirm that run results keep each stage's evidence label unchanged and that no label of the matrix changes. Proof: `uv run pytest tests/unit/view/test_server.py -k evidence -q -n 2`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 7.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.
