# Design — c0052 release hygiene

## Context

Three groups of small items found by a review of `main` on 2026-10-04. None changes a format, a model field or a command. The change touches one source file (`backends/kicad/backend.py`), `pyproject.toml`, four documents and six test files.

## Decisions

### 1. The KiCad capability level stays `INFERRED`, and is computed

The review read the label as stale: `INFERRED` beside two rows that are `CORPUS-VERIFIED` (`H-K-PCB-READ`) and `KICAD-VERIFIED` (`H-K-PCB-WRITE`). The living specs say otherwise:

- `kicad-file-backend`, "Board reading evidence": "`pcb.EVIDENCE` SHALL be `INFERRED`, linked to `H-K-PCB-READ`, and SHALL stay so; RT1 makes the lossless read `CORPUS-VERIFIED`, not the meaning of each field."
- The result of `H-K-PCB-WRITE` ends with "writing arbitrary designs stays `INFERRED` (`pcb.WRITE_EVIDENCE`)".
- `backend-protocol`, scenario "KiCad capability report": "the evidence level is `INFERRED`".

So a row's level states what its test covered, and an operation's level states what holds for any file. A report at `CORPUS-VERIFIED` would say more than `read` and `write` return for the same backend, and more than the register supports for an arbitrary design. Rule "lowest wins" gives `INFERRED`.

What was wrong is that the level was a literal with no link to either side. The fix:

- `backend.py` imports `pcb` at module level and sets `evidence=Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`. The result is the same value as today (`INFERRED`, no oracle, `H-K-PCB-READ` and `H-K-PCB-WRITE`), so no output changes. `pcb` does not import `backend`, so there is no cycle; `backend` is still imported lazily by the registry.
- `tests/unit/test_capability_evidence.py` holds `report_problems(evidence, rows) -> list[str]`: one message for a named id with no row, for a refuted row, and for a level stronger than a named row (`core.evidence.strength`). It is called on synthetic cases and on every backend of `registry.all_backends()` with `load_register("docs/hypotheses.md")`. A second test compares the KiCad report with the combination of the two constants and checks that `backend.py` holds no `Level.` literal.
- `docs/cli-contract.md`, "Discovery", gains two sentences that explain the difference between a row's level and the report's level.

Evidence level: `INFERRED`, unchanged.

### 2. Package metadata

- `[project.urls]`: `Homepage` and `Source` = `https://github.com/lgili/Fenolite`, `Issues` = `…/issues`, `Changelog` = `…/blob/main/CHANGELOG.md`.
- Classifier: `Development Status :: 3 - Alpha`. The version is not touched (c0025).
- The description is not changed (Non-goals).

### 3. The `route` extra is removed

`route = ["freerouting-client>=2.3"]` dates from the bootstrap. That package is a client of Freerouting's cloud API. c0023's proposal runs the jar with `java -jar` or in a container, registers the router through c0016's entry-point group, and lists "Freerouting's cloud API" under Non-goals; its plugin must also keep usage data off. c0016 declares entry points only. So no archived or active change imports the package, and the extra would advertise a path that sends board data to a service.

Removal touches: `pyproject.toml`, `uv.lock` (`uv lock --offline`, which only drops packages), `ALLOWED_EXTRAS` in `tests/unit/test_pyproject_invariants.py`, the extras set in `tests/unit/cli/test_capabilities.py`, and the extras sentence of `README.md`. c0016 and c0023 name `test_pyproject_invariants.py` as a proof; they add no extra, so their proofs still pass.

### 4. The source distribution is an allowlist

Today: 1 332 files, 3.7 MB, with `openspec/` (421 files), `AGENTS.md`, `CLAUDE.md`, `packaging/`, `uv.lock`, `Makefile`, and any untracked file of the root that `.gitignore` does not match. Measured with `uv build --offline` in a scratch folder.

`[tool.hatch.build.targets.sdist]` gets `include` (the thirteen entries of the spec) and loses `exclude`. Measured with that list: 901 files, 1.8 MB; top level `src`, `tests`, `docs`, `examples`, `schemas`, `tools`, seven documents, plus `pyproject.toml`, `PKG-INFO` and `.gitignore`, which the build backend adds; an untracked `AGENTS.md.bak-1` in the root does not ship; the wheel built from the archive lists the same 178 files as before.

`tests/` ships although some tests read files that do not (`openspec/`, `AGENTS.md`, `Makefile`, the CI workflow): the archive is for building and for reading, and the test suite is run from a checkout. `tests/unit/test_pyproject_invariants.py` checks the table statically with `sdist_problems(table)`; the built archive is checked by the task's proof, because a unit test must not need the build backend.

### 5. `template` section of the contract

Written from runs of the command on 2026-10-04 (exit 4 without `--confirm`, exit 0 and a plan with `--dry-run`, a receipt with `--confirm`, exit 2 for `--target other`, exit 3 with `FEN-3001` for a missing file and with `FEN-3004` plus one `template.*` issue per problem for a malformed one). `tests/consistency/test_cli_consistency.py` gains `undescribed_commands(names, page)` and two tests. The command name counts as described by the text `fenolite <name>` or by a level-2 heading, so c0016's `route` section passes in either form.

### 6. Dead skip guards

- `tests/unit/backends/kicad/test_rules_text.py::test_canary_round_trip`: the guard on the canary file is removed; a missing file now fails.
- `tests/unit/backends/kicad/test_projectset.py::test_worksheet_pointer_matches_pro`: the test reads `pro.PAGE_LAYOUT_POINTER` directly.

### 7. Register rows

Both rows keep `INFERRED`; only `result` and `date` change.

- `H-G-ANGLE` ("both targets"): the KiCad half holds on two origins. Checked on 2026-10-04 with `FENOLITE_CENSUS_OUT`: `reader_inexact` is empty for the native demos (`tests/corpus/test_board_census.py`) and for the upgraded third-party copies (`tests/kicad/board/test_board_upgraded.py`). The second-backend half has no reader, so the row cannot rise. Same form as `H-K-LIB-READ` ("footprint half … symbol half pending").
- `H-A-UNIT`: the criterion asks for positions decoded from public corpus boards within 1.27 nm. What exists is the opposite direction: a document Fenolite writes in units of 2.54 nm is imported by `kicad-cli pcb import` 10.0.6 with relative pad positions within 10 nm (`tests/kicad/altium/test_pcbdoc_oracle.py`, passed on 2026-10-04). That is supporting data; the criterion is not met.

### 8. Private gate section

`docs/provenance.md` gains "Private residue gate", written from `tools/residue/scan.py` (`private_tokens`, `load_config`, the summary line of `main`) and the first lines of the `Makefile`. No private file is opened. `tests/residue/test_scan.py` gains `test_gate_documented`.

## Hypotheses registered by this change

None.

## Sources registered by this change

None. The repository address is the project's own.

## Order against other active changes

- `backend-protocol` "Capability reports", `repo-layout` "Zero runtime dependencies in the core": no active change modifies them; the full text is copied from `openspec/specs/`.
- `cli-contract`, `repo-layout`, `residue-scan`: the ADDED requirement names are unique across the living specs and c0016, c0023, c0025, c0039–c0047.
- c0016 and c0023 edit `pyproject.toml` (entry points) and `docs/cli-contract.md` (new sections): textual merges only.
- c0025 moves the Unreleased entries and bumps the version; this change adds lines under Unreleased and leaves the version.

## Risks

- A reader may expect `CORPUS-VERIFIED` from `capabilities`. The contract page now explains the level; raising it is a maintainer decision that would also need "Board reading evidence" changed.
- A user of `fenolite[route]`: pip warns that the extra is unknown and installs the core.

## Open Questions

- To confirm: the KiCad capability level stays `INFERRED` (Decision 1).
- To confirm: `route` is removed rather than kept as a reserved name (Decision 3).
- To confirm: the sdist ships `tests/` and `tools/` and no `openspec/` (Decision 4).
- To confirm: `3 - Alpha` for 0.1.0 (Decision 2).
