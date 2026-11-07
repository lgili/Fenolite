## 1. Entry

- [x] 1.1 Validate this change; decide whether `cli/_viewrun.py` reuses `fenolite.mcp.backend.FenoliteBackend` or a runner core moved to a shared `fenolite.cli` module (design, "Risks"), and record the decision here. Decision: the runner core (`_run`, `_wait`, `_stop`, `_stderr`) moves to `fenolite.cli.childrun.run_child`, which `FenoliteBackend._run` now calls; `cli/_viewrun.py` uses that core directly and the MCP `Catalog` only to build the words of a run from the command's parser, so the viewer does not depend on the MCP server's call and image handling, and c0303's action templates use the same core. `view` imports nothing new. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0302-viewer-run-checks --strict --no-interactive`; `uv run pytest tests/unit/mcp tests/unit/test_import_graph.py -q -n 2`.

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

- [x] 5.1 Add the Run controls of the cards, the Run menu and palette commands with their forms from `GET /runs`, the run strip with progress and Cancel, and polling under the navigation guard; no control on exported or `--no-run` pages (scenarios "A failed DRC card from a run", "An exported page"; requirement "Runs only on request in a live server"). Proof: `uv run pytest tests/visual/test_run.py tests/visual/test_project_review.py -q` in the `viewer` CI job.

## 6. Teaching and documentation

- [x] 6.1 Add tested lines for `--run-timeout` and `--no-run` to the closest page of the agent guide and regenerate the command guide; update `docs/viewer.md` ("Project review": running checks from the page) and `docs/cli-contract.md` ("view"). Proof: `uv run pytest tests/unit/agent -q -n 2`; `uv run python tools/gen_agent_guide.py --check`.

## 7. Closing

- [x] 7.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch, `viewer` and the KiCad jobs included.
- [x] 7.2 Confirm that run results keep each stage's evidence label unchanged and that no label of the matrix changes. Proof: `uv run pytest tests/unit/view/test_server.py -k evidence -q -n 2`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 7.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.

Open on the branch (2026-10-29): 7.1 waits for `make check-fast` on the maintainer's machine and the CI jobs (only focused tests ran here: ruff, ruff format, pyright of the changed packages, the residue scan, `tests/unit/view`, `tests/unit/cli/test_view_cmd.py`, the new tests, `tests/unit/agent`, `tests/consistency`, `tests/unit/mcp`, `tests/visual`). 7.3: the entry is written under `## [Unreleased]`, but `tests/unit/test_release_record_v06.py::test_changelog_section` requires `[Unreleased]` empty while `fenolite.__version__` is still `0.6.0`; it passes once the version moves on.

Changelog proof, 2026-11-01, source `b02e09fe`: the literal `uv run pytest tests/unit -k "release_record or changelog" -q -n 2` passed 167 cases with one optional MCP SDK skip. The existing Unreleased entry names this change; no extra entry is added. Complete fast-gate and exact CI tasks remain open.


## Scoped implementation closure — 2026-11-03

The maintainer clarified that problematic geometry was already outside this
closure CI batch before the run. Close only this specification’s implementation
on tested source 985f59a1d01a612b2eac0219243199896c24075a and reviewed
archival documentation. Run 41708879698 remains FAILURE: the27known c0332
geometry failures are DEFERRED_NOT_PASSED, not passed tests. KiCad9 and all
five unit jobs succeeded. The relevant KiCad10 module results are inferred
from complete unfiltered collection and the exhaustive -ra non-pass report.
Explicitly contracted unsupported-target skips remain skips; no nominal
PASSED line or green KiCad10 job is claimed.

`scoped-ci-985f59a1.json` binds the exact tests, explicit KiCad9 positive
lines, complete log hashes, reused fast proof and existing scoped records.
The isolated runtime/tests/tools/configuration remain byte-identical to985;
this does not validate later CAC runtime, close c0355 or replace subsequent
integration CI. Existing authored/native/default-map proofs and limitations
remain intact. No suite, native CAD test or CI rerun was started for archive.

Entry refresh: previously implemented prerequisites are now archived in the
required order: no literal prior archive requirement. Existing APIs and reviewed normative
unions were checked against the current living text; no runtime change or
external publication was needed. Contracted native9/10 unsupported-target
skips remain skips and are explicitly retained in the portable receipt.

The existing viewer job126171394431 passed bundle freshness and104visual
cases on source985. All eleven PNG references exactly match the prior
reviewed/published/source985 maps, preserving the dated delegated image
inspection without inventing a new approval from automation. Unit, viewer
and applicable MCP/DCO jobs are recorded individually in the portable proof.
No bundle, PNG, runtime, assertion or measurement was regenerated here.
The missing three native action CI cases ofc0303 and six real variant views
ofc0305 remain separate open requirements; neither is closed by this record.
