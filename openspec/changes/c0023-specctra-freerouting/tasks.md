## 0. Go or no-go

- [ ] 0.1 Read c0016's gate verdict in `docs/evidence/routing.md` and the maintainer's decision in `docs/roadmap.md` ("Proposed cuts", c0023). If the gate passed and the maintainer has not kept this change in v0.1, stop here: move the change to v0.2a in the roadmap and leave every task below open. Proof: the decision and its date are written under this task.
  - Decision recorded on 2026-10-03 (`docs/roadmap.md`, Open decisions, row 5): the maintainer keeps this change in v0.1 whatever the gate verdict is. The day-6 gate of task 3.3 still applies.

## 1. Decision record, registers and fact pages

- [ ] 1.1 Write `docs/adr/0006-specctra-and-freerouting.md` with `Proposed` under `## Status` (design Decision 1), add its row to `docs/adr/README.md` and `0006-specctra-and-freerouting.md` to `REQUIRED` in `tests/unit/test_adrs.py`. Ask the maintainer for the decision before task 2.1 starts, and if S-0224 may not be used, apply the black-box fallback and note it under this task. Proof: `uv run pytest tests/unit/test_adrs.py`; `grep -A1 '^## Status' docs/adr/0006-specctra-and-freerouting.md` prints `Proposed`.
  - The maintainer accepted the decision on 2026-10-03 (same row): S-0224 may be read for facts and Freerouting may be run as a subprocess. The file is still written as `Proposed`; the maintainer's own commit sets `Accepted`.
- [ ] 1.2 Register sources and hypotheses. This is the first commit of the implementation after the ADR.
  - Add S-0220 to S-0226 to `docs/evidence/sources.md` from design "Sources registered by this change", after opening each page: the revision or commit read, the consultation date and the licence or notice each states.
  - Add the rows `H-G-DSN-ACCEPT`, `H-G-DSN-UNITS`, `H-G-DSN-PROTECT`, `H-G-DSN-REPEAT` and `H-G-DSN-OFFLINE` (backend `specctra`) and `H-G-DSN-ROUTE` (backend `kicad`) to `docs/hypotheses.md`, level `INFERRED`, result `pending`. Remove `H-G-DSN-*` from the reserved-families table and add the paragraph "Change c0023 (Specctra and Freerouting) adds …".

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-G-DSN-' docs/hypotheses.md` prints `6`.
- [ ] 1.3 Write `docs/formats/specctra/dsn.md` and `ses.md` in Fenolite's own words: fact tables with the header `| fact | source | label | hypothesis |`, every row `INFERRED` until its probe runs. Write `src/fenolite/backends/specctra/PROVENANCE.md` and add a `LEGAL-ANNEX.md` session row naming S-0224 as read for facts and Freerouting as a program run across a process boundary. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`; `uv run python tools/residue/scan.py` exits 0.

## 2. Probes first (Freerouting 2.4.1, Java 25; `kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [ ] 2.1 Install the pinned jar and Java 25 outside the repository; record the jar's SHA-256, the Java version and the platform in `docs/evidence/routing.md`. Add the marker `needs_freerouting` and the resource `freerouting` to `tests/conftest.py`. Proof: `uv run pytest tests/unit/test_conftest_require.py -k freerouting`; `java -jar <jar> --help` or its documented equivalent runs.
- [ ] 2.2 Write `src/fenolite/backends/specctra/lexer.py` and `tests/unit/backends/specctra/test_lexer.py` (scenarios of "Specctra syntax"), then `tests/routing/test_freerouting_gate.py` with `test_accept` and `test_units` on a DSN written by a helper in the test for the two-pad board. Record the outcomes with `FENOLITE_ROUTING_EVIDENCE=1`. If Freerouting rejects the file, change only what its message names and note each change under this task. Proof: `uv run pytest tests/unit/backends/specctra/test_lexer.py`; `FENOLITE_REQUIRE=freerouting uv run pytest tests/routing/test_freerouting_gate.py -k "accept or units" -rA`.

## 3. Writer and reader

- [ ] 3.1 Write `src/fenolite/backends/specctra/dsn.py` (design Decisions 4 to 7) and `tests/unit/backends/specctra/test_dsn.py`, covering every scenario of "Design files are written from the model" plus a through-hole pad, a polygon pad, a cut-out, shared padstacks, a renamed net and determinism. Commit `tests/data/specctra/two_pads.dsn` with its row in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/unit/backends/specctra/test_dsn.py tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 3.2 Write `src/fenolite/backends/specctra/ses.py` (design Decision 8) and `tests/unit/backends/specctra/test_ses.py`, covering every scenario of "Session files are read into copper" plus an unknown padstack, an unknown list and a session in another resolution. Commit `tests/data/specctra/two_pads.ses`. Proof: `uv run pytest tests/unit/backends/specctra`; `uv run pyright src`.
- [ ] 3.3 Day-6 gate. Switch the gate tests to `write_dsn` and `to_copper`, add `test_protect`, and run `test_route` for target 10 through a helper that merges with c0016's `merge.apply`. If `dsn-accept` or `dsn-route-t10` does not hold, stop: record what was learned in `docs/evidence/routing.md`, move the remaining tasks to v0.2a in the roadmap, and close the change without archiving its routing delta. Proof: `FENOLITE_REQUIRE=kicad,freerouting uv run pytest tests/routing/test_freerouting_gate.py -rA` on the local KiCad 10.0.6; the verdict is written under this task.

## 4. Plugin and doctor

- [ ] 4.1 Add `RoutingJob.extra` and fill it in `cmd_route` (requirement "Job extras"), with its test. Write `tests/_fakefreerouting.py` and `src/fenolite/routing/plugins/specctra/freerouting.py` (design Decision 9), declare the entry point, and write `tests/unit/routing/test_freerouting.py`, covering every scenario of "Freerouting plugin" plus a timeout, the container command line with `--network none`, and `HOME` set to the run folder. Proof: `uv run pytest tests/unit/routing tests/unit/cli/test_route_cmd.py tests/unit/test_import_graph.py tests/unit/test_pyproject_invariants.py`; `uv run pyright src`.
- [ ] 4.2 Add the Java check to `doctor`'s router entry and the tests of "Freerouting in doctor"; document the router in `docs/routing.md` (installation, Java 25, the offline flag, the container form) and in `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli -k "doctor or route" tests/consistency`.

## 5. Oracle and CI

- [ ] 5.1 Complete `test_freerouting_gate.py` (`test_route` for target 9 inside the 9.0.9 image, `test_repeat`, `test_offline` in a container) and write `tests/routing/test_freerouting_oracle.py::test_loop` (build, route, fill, rebuild; routes kept). When `dsn-offline` is `present`, set `sends_data_offsite = False` in the same commit. Proof: `FENOLITE_REQUIRE=kicad,freerouting uv run pytest tests/routing -m needs_freerouting -rA` on both majors; `docs/evidence/routing/freerouting-2.4.1.json` holds the seven outcomes.
- [ ] 5.2 Extend the `routing` job (requirement "Freerouting in the routing job") and `tests/unit/test_ci_workflow.py`. Proof: `uv run pytest tests/unit/test_ci_workflow.py`; the job's run is linked under this task.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0023-specctra-freerouting --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence labels: `H-G-DSN-ACCEPT`, `H-G-DSN-UNITS` and `H-G-DSN-PROTECT` become `ORACLE-VERIFIED(freerouting 2.4.1)`, `H-G-DSN-ROUTE` `KICAD-VERIFIED (9.0.x, 10.0.x)`, or each is refuted with a successor and its fallback; `H-G-DSN-REPEAT` and `H-G-DSN-OFFLINE` record their outcomes. The labels in `docs/formats/specctra/` follow: a fact gets the level of the probe that proves it and stays `INFERRED` otherwise. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "Freerouting plugin: a Specctra DSN writer and session reader of Fenolite's own, and `--router freerouting`, which runs Freerouting 2.4.1 as a subprocess with analytics disabled". Update `docs/roadmap.md`. Proof: `git diff CHANGELOG.md docs/roadmap.md`.

_Note: the maintainer's acceptance of ADR-0006 is calendar time, not a task. The change is archived only after the maintainer's own commit sets `Accepted (<date>)` and adds the matching `LEGAL-ANNEX.md` row._
