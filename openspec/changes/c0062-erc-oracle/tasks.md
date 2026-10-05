## 0. Entry check

- [ ] 0.1 c0060 and c0061 are archived: `sch.sheet_files` exists and `build` writes a schematic. Read the living text of every requirement this change modifies. If c0044 was implemented first, re-base the deltas of "Check command input" and "ERC lite stage" on the text it left, and note it under this task. Proof: `openspec list` shows c0060 and c0061 archived; `openspec validate c0062-erc-oracle --strict --no-interactive` passes after the re-base.

## 1. Registers and fact rows

- [ ] 1.1 Register the hypotheses and the sources. This is the first commit of the implementation.
  - Add the rows `H-K-ERC-JSON`, `H-K-ERC-POS`, `H-K-ERC-TYPES`, `H-K-ERC-COPYSET`, `H-K-ERC-REPEAT`, `H-K-ERC-RT2` and `H-K-PARITY-RUN` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed at proposal time (2026-10-04)` with the observation of design "Context", per major.
  - Add S-0330 and S-0331 to `docs/evidence/sources.md` with the licence of the repository and key names only. Widen the "used for" cells of S-0020, S-0022, S-0037 and S-0046.
  - Re-check every name consumed from c0060, c0061 and archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -cE '^\| H-K-(ERC|PARITY)-' docs/hypotheses.md` prints `7`.
- [ ] 1.2 Write `docs/formats/kicad/erc.md`: the report keys per major, the position scale, the exit codes, the types of the controls, the copy set and the parity flag, each row with a source, a label and a hypothesis. Add rows to `src/fenolite/backends/kicad/PROVENANCE.md` and a `LEGAL-ANNEX.md` session row. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

## 2. Probes first (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [ ] 2.1 Add `ErcItem`, `ErcViolation`, `ErcReport`, `ErcOutcome`, `ErcRt2Outcome`, `ErcOracle` and `DrcOutcome.parity_judged` to `src/fenolite/backends/base.py`; write `src/fenolite/backends/kicad/erc.py` with `read_erc_report` and the two authored reports under `tests/data/kicad/erc/`; write `tests/unit/backends/kicad/test_erc.py` and extend `tests/unit/backends/test_base_types.py` (scenarios of "Neutral ERC report", "ERC oracle protocol", "Oracle protocol" and "ERC report reading"). Proof: `uv run pytest tests/unit/backends/kicad/test_erc.py tests/unit/backends/test_base_types.py tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 2.2 Add `KicadCli.erc` and the `schematic_parity` keyword of `KicadCli.drc`; teach `tests/_fakecli.py` `sch erc` and the flag; extend `tests/unit/backends/kicad/test_cli_runner.py` (scenarios of "ERC runs through the package runner"). Proof: `uv run pytest tests/unit/backends/kicad/test_cli_runner.py`.
- [ ] 2.3 Write `tests/kicad/check/_erccases.py` and `test_erc_facts.py` (shape, positions, types and severities); add the probes to `PROBES` and regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Set `POSITION_SCALE` from the outcomes. Note under this task each outcome that differs from design "Context" and the fallback applied. Proof: `uv run pytest tests/kicad/check/test_erc_facts.py tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
- [ ] 2.4 Write `tests/kicad/check/test_parity.py` with the four parity probes, holding its own argument lists until group 4 exists. Proof: `uv run pytest tests/kicad/check/test_parity.py tests/kicad/test_probe_results.py -rA` on both majors.

## 3. Copy set and oracle

- [ ] 3.1 Extend `projectset.project_set` with the schematic files (MODIFIED "Check project copy set") and `tests/unit/backends/kicad/test_projectset.py`. Proof: `uv run pytest tests/unit/backends/kicad/test_projectset.py tests/unit/cli/test_check_readonly.py`.
- [ ] 3.2 Write `erc.item_locations` and `KicadOracle.erc`; extend `tests/unit/backends/kicad/test_oracle.py` (scenarios of "ERC oracle"). Proof: `uv run pytest tests/unit/backends/kicad/test_oracle.py -k erc`; `uv run pyright src`.
- [ ] 3.3 Write `tests/kicad/check/test_erc_oracle.py::test_copy_set` and run `tests/kicad/check/test_copy_set.py` again with a schematic in the folder. Proof: `uv run pytest tests/kicad/check/test_erc_oracle.py -k copy_set tests/kicad/check/test_copy_set.py -rA` on both majors.

## 4. Stage, findings and parity

- [ ] 4.1 Write `checks/erc_json.py` and `checks.codes.type_suffix`, switch `drc_json.type_code` to it, and add the code rows; write `tests/unit/checks/test_erc_json.py` (scenarios of "ERC findings as issues" and "ERC stage issue codes"). Proof: `uv run pytest tests/unit/checks/test_erc_json.py tests/unit/checks/test_drc_json.py tests/unit/checks/test_codes.py`.
- [ ] 4.2 Write `checks/erc.py`, put `erc.kicad` in `STAGE_ORDER` and `ORACLE_STAGES` in the place of `erc.lite`, add the skip reason `no-schematic`, pass the oracle from `cmd_check`, and add an `ErcOracle` fake to `tests/unit/checks/fakes.py`; write `tests/unit/checks/test_erc_stage.py` (scenarios of "ERC stage"). Proof: `uv run pytest tests/unit/checks tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 4.3 Map parity entries in `drc_json.finding_issues`, add `parity`, `parity_judged` and `parity-unchecked` to the DRC stage, and pass the flag from `KicadOracle.drc` (requirements "Parity findings", "Parity in the DRC run", MODIFIED "DRC findings as issues" and "DRC stage and the rules canary"). Switch `test_parity.py` to the product path. Proof: `uv run pytest tests/unit/checks/test_drc_json.py tests/unit/checks/test_drc_stage.py tests/unit/backends/kicad/test_oracle.py`; `uv run pytest tests/kicad/check/test_parity.py -rA` on both majors.

## 5. `erc.lite` out of the KiCad pipeline

- [ ] 5.1 Remove `REMOVE_IN` and `check_removal` from `checks/erc_lite.py` with their test, and take `erc_stage` out of `run_checks` (MODIFIED "ERC lite stage"). List the files that name `erc.lite` with `grep -rl "erc\.lite" src tests docs examples agent README.md AGENTS.md` and update each: the hermetic stage list becomes `model.validate,roundtrip` in `cmd_check` (`example_args`, the missing-tool hint), in the tests and in the docs. Proof: `uv run pytest tests/unit/checks tests/unit/cli tests/consistency`; `grep -rn "model.validate,erc.lite" src docs tests agent README.md AGENTS.md` prints nothing.
- [ ] 5.2 Write `tests/kicad/check/test_erc_oracle.py` for the stage on both majors (scenarios "Clean built project", "Unconnected pin reported" and "Native project" of "ERC stage"), and extend the determinism and read-only tests of `check` to `erc.kicad`. Proof: `uv run pytest tests/kicad/check/test_erc_oracle.py tests/kicad/check/test_check_built.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

## 6. RT2 for schematics

- [ ] 6.1 Write `KicadOracle.rt2_erc` and its hermetic test (scenario "Three runs and no write"). Proof: `uv run pytest tests/unit/backends/kicad/test_oracle.py -k rt2_erc`.
- [ ] 6.2 Write `tests/kicad/schematic/test_corpus_rt2.py` and copy its census into `docs/evidence/kicad-schematic.md`, the acceptance list apart. A judged difference is a reader or printer defect: report it to c0060's code and do not work around it; note each under this task. Proof: `FENOLITE_REQUIRE=kicad,corpus FENOLITE_CENSUS_OUT=<file> uv run pytest tests/kicad/schematic/test_corpus_rt2.py -rA` on the local KiCad 10.0.6, and inside the pinned 9.0.9 image with the rows of tag 9.0.9.1.

## 7. Documentation

- [ ] 7.1 Update `docs/cli-contract.md`: the stage list, the `erc.kicad` stage and its summary, the `kicad.erc.*` and parity codes, the copy set with the schematic files, and why an isolated run reports global symbol libraries as missing. Update `docs/dsl.md` and `docs/evidence/kicad-check.md`. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `make check` passes; `openspec validate c0062-erc-oracle --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
- [ ] 8.2 Update the evidence labels: each of the seven hypotheses becomes `KICAD-VERIFIED` for the majors that proved it, or is refuted with a successor and the fallback applied; `H-K-ERC-REPEAT` and `H-K-ERC-RT2` name the projects that were not judged; `H-K-CHECK-COPYSET` records its second proof. Raise `erc.EVIDENCE` only if `H-K-ERC-JSON`, `H-K-ERC-POS` and `H-K-ERC-COPYSET` hold on both majors. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`.
- [ ] 8.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite check` runs KiCad's ERC (`erc.kicad`) on the project's schematic and reports schematic parity findings of the DRC run; the `erc.lite` stage is removed from KiCad checks (`--stages erc.lite` is now a usage error)". Update `docs/roadmap.md`. After archiving, correct the Purpose line of `openspec/specs/verification-loop/spec.md`, which names "ERC lite". Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
