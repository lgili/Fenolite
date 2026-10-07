## 0. Entry check

- [ ] 0.1 Read the living `routing` and `cli-contract` specs and `openspec list`. Write under this task, with the date and the commit: that `0.3.0` is released; whether another change modified "Freerouting plugin" or "Mutation protocol" since this proposal (then regenerate the MODIFIED delta from the living text; c0109, c0110 and c0120 are meant to land after this change); the reason text of a missing jar as the plugin prints it today; and the options of the hidden `_echo` command (`--issues` of c0066 sits beside the new `--defer`). c0066 is archived, so the receipt fields `id` and `undo` apply to the receipt of `fetch` with no extra work: confirm it with one `_echo --write` run. Proof: `openspec validate c0078-router-fetch --strict --no-interactive` passes after any re-base.

## 1. Register

- [ ] 1.1 Add the row `H-G-FETCH-PIN` to `docs/hypotheses.md` (backend `general`, level `INFERRED`, the test and criterion of `design.md`, result `pending`). The size (`64 076 787 bytes`) and the digest of the asset are already in `docs/evidence/routing.md`; change nothing there. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/verify/test_cited_ids.py -q`; `grep -c '^| H-G-FETCH-PIN ' docs/hypotheses.md` prints `1`.
- [ ] 1.2 Record the maintainer's decision in `docs/roadmap.md`, "Open decisions", as a new row with the next free number (36 at `9aba2dff`): "v0.4: Fenolite may download the pinned Freerouting jar, only inside `fenolite fetch` and only with `--confirm`", source "proposal of c0078", "decided by the maintainer on 2026-10-05, confirmed on 2026-10-07". Proof: `grep -c 'fenolite fetch' docs/roadmap.md` is at least 1; `uv run pytest tests/consistency tests/unit/test_repo_layout.py -q`.

## 2. Tools folder and deferred writes

- [ ] 2.1 Write `src/fenolite/core/tools.py` and `tests/unit/core/test_tools.py` (scenarios "Explicit folder" and "Platform defaults"). Proof: `uv run pytest tests/unit/core/test_tools.py tests/unit/test_import_graph.py -q`; `uv run pyright src`.
- [ ] 2.2 Add `source`, `size` and `sha256` to `PlannedWrite`, resolve deferred writes in the dispatcher, add `--defer` and `--defer-bad` to the hidden `_echo` command, and register `FEN-3006` and `FEN-6003` with their rows in `docs/cli-contract.md` and their tables in `src/fenolite/cli/data/explain.toml` (scenarios of "Deferred writes" and "Fetch error codes"). Proof: `uv run pytest tests/unit/cli/test_fetch_cmd.py -k deferred tests/unit/cli/test_exitcodes.py tests/unit/cli/test_main.py tests/unit/cli/test_explain_cmd.py tests/consistency -q`.

## 3. The command

- [ ] 3.1 Write `src/fenolite/cli/data/fetch.toml` (the rows `freerouting` and `_selftest`), `cli/data/fetch-selftest.txt`, and `src/fenolite/cli/fetch.py` with `rows`, `public_names`, `download`, `read_file` and `matches`; add the table tests: every public row has an `https` address and a registered source, and the `bytes` and `sha256` of the row `freerouting` equal the size and the digest that `docs/evidence/routing.md` records (scenario "Table agrees with the evidence page"). Proof: `uv run pytest tests/unit/cli/test_fetch_cmd.py -k table tests/residue -q`; `uv build` lists both data files in the wheel.
- [ ] 3.2 Write `src/fenolite/cli/cmd_fetch.py` and the rest of `tests/unit/cli/test_fetch_cmd.py` (scenarios of "Fetch command" and "Relative folder refused"), and the section `fetch` of `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli/test_fetch_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py -q`.
- [ ] 3.3 Only when c0080 is archived: add one tested line for `fetch` to the guide page `routing` and name `FEN-3006` and `FEN-6003` on the page `recovery`, as its coverage rule asks. Otherwise write "c0080 is open: nothing to add" under this task. Proof: `uv run pytest tests/unit/cli/test_fetch_cmd.py -q` passes and, when the folder `tests/unit/agent` exists, `uv run pytest tests/unit/agent -q` passes too.

## 4. The router

- [ ] 4.1 Add the third location, `jar_source` and the new reason to `routing/plugins/specctra/freerouting.py`; give `fenolite route` its hint and `fenolite doctor` its `source` key (scenarios "Fetched jar is found", "Missing jar names the command", "No connection outside fetch"). Update the tests that hold the old reason text and the docstring of `tests/_resources.py` that says the jar is never downloaded. Proof: `uv run pytest tests/unit/routing/test_freerouting.py tests/unit/cli/test_route_cmd.py tests/unit/cli/test_doctor_cmd.py tests/unit/cli/test_fetch_cmd.py -k "fetched or missing_jar or no_connection or freerouting" -q`; `grep -rn "never downloads" src tests` prints nothing.

## 5. Decision record and documentation

- [ ] 5.1 Write `docs/adr/0007-fetching-external-tools.md` (status `Accepted`, the maintainer's decision of 2026-10-05, confirmed on 2026-10-07, with the number of the roadmap row of task 1.2), add the dated line to ADR-0006, list ADR-0007 in `docs/adr/README.md`, and add the `LEGAL-ANNEX.md` row (scenarios of "Fetched tools decision record"). Proof: `uv run pytest tests/unit/test_adrs.py tests/unit/test_legal_docs.py tests/unit/test_provenance.py -q`.
- [ ] 5.2 Rewrite "Install" under "Freerouting" in `docs/routing.md` around `fenolite fetch freerouting --confirm`, keep the manual way as the second option, and name the tools folder per platform. Update the docstring of the plugin and, in `agent/SKILL.md` (or the start page, when c0079 has moved it), the sentence that says where the jar comes from. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/unit/test_agent_skill.py tests/residue -q`.

## 6. CI

- [ ] 6.1 Replace the `curl` and `sha256sum` step of the `routing` job in `.github/workflows/ci.yml` (the step "Install pinned Freerouting jar") with `uv run fenolite fetch freerouting --dir /tmp/freerouting --confirm --json`, keep `FENOLITE_FREEROUTING_JAR`, and update `tests/unit/test_ci_workflow.py`. Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`. The `routing` job of the pull request, on both targets, is the settling run of `H-G-FETCH-PIN` and is read in task 7.1.

## 7. Closing

- [ ] 7.1 Update the evidence labels: `H-G-FETCH-PIN` records the `routing` run that installed the jar with `fetch` and passed the gate, or what failed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.
- [ ] 7.2 Add to `CHANGELOG.md` under `## [Unreleased]`: "**New command `fenolite fetch freerouting`**: downloads the pinned Freerouting jar from its publisher after `--confirm`, checks its size and SHA-256 and installs it in the user's tools folder, where `route --router freerouting` finds it; no other command downloads anything (ADR-0007)". Update the row of this change in `docs/roadmap.md`. Proof: `git diff --stat HEAD -- CHANGELOG.md docs/roadmap.md` lists both files.
- [ ] 7.3 Stop and report "ready for the long runs": `make check-fast`, the unit suite on Python 3.11 (`uv run --python 3.11 pytest tests/unit -q`), `uv run pytest tests/residue tests/corpus/test_manifest.py -q` after `git add -A`, `uv run python tools/residue/scan.py`, and `openspec validate --all --strict --no-interactive`. The full `make check` is run once by the coordinator on the rebased branch, not by the implementing agent. Proof: each command exits 0.
