## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living `backend-protocol` and `cli-contract` specs, and c0158's delta. Write under this task, with the date: that c0158 is archived or its API is on the branch (else stop: the verification needs `fenolite.api.equivalent`); whether "Altium write of a model" changed since `f802b60` (then regenerate the MODIFIED block from the living text with only this change's edits); whether `tests/unit/test_import_graph.py` still holds the row `convert` → `model`, `geometry`, `backends*`; and the maintainer's answers to the open questions of the design (given on 2026-10-09: every recommended answer, `docs/roadmap.md` Open decisions row 40). Proof: `openspec validate c0159-convert-command --strict --no-interactive` passes.

## 1. Measure and register

- [ ] 1.1 Add the rows `H-G-CONV-LEDGER`, `H-K-CONV-TRIANGLE` and `H-K-CONV-RETARGET` to `docs/hypotheses.md` (level `INFERRED`, tests and criteria of the design, result `pending`; the first with the measurement of 2026-10-09 as its first record). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Write `tests/corpus/test_convert_census.py` from the design's measurement, first against today's writers through `lens.altium.write_model` (board and project files): per board the counts per kind, and the differences per kind; record the largest per-coordinate difference of the read-back, which sets `tolerance_nm` of the profile. Proof: `uv run pytest tests/corpus/test_convert_census.py -rA` with the corpus cached; the table and the tolerance written under this task.

## 2. Report

- [ ] 2.1 Keep every reason per item in `lower._Account` (`AltiumInputs.lost`), and count `dnp` (scenarios "Every reason kept", "Do-not-populate is reported"); every committed Altium sample keeps its bytes. Proof: `uv run pytest tests/unit/backends/altium tests/unit/lens -q`.
- [ ] 2.2 Write `convert/report.py`: `KINDS` with groups and loss classes, `ReportRow`, `ConversionReport`, `EXPLAINS` (scenarios "Reasons are counted apart", "Vocabulary is closed"). Proof: `uv run pytest tests/unit/convert/test_report.py -q`.

## 3. Package and directions

- [ ] 3.1 Write `convert/sources.py` (KiCad with `design_rules`, Altium) and `convert_project` with the registry of directions (scenarios "Net classes come from the project", "Nothing is written"). Proof: `uv run pytest tests/unit/convert/test_sources.py tests/unit/convert/test_package.py -q`.
- [ ] 3.2 Write the direction KiCad to Altium, `LossyConversionError` and `convert.lossy` (scenario "Exit 7 without consent", without the CLI). Proof: `uv run pytest tests/unit/convert/test_to_altium.py -q`.
- [ ] 3.3 Write the direction KiCad to KiCad for the same or a newer major (scenario "Older target refused", without the CLI). Second item of the cut order. Proof: `uv run pytest tests/unit/convert/test_to_kicad.py -q`.

## 4. Verification

- [ ] 4.1 Write `src/fenolite/convert/data/profiles.toml` and `fenolite.api.convert`: the temporary read-back, `equivalent`, the matching by `EXPLAINS`, `convert.unexplained`, `--no-verify` (scenarios "Lost pad explains its pin", "Undeclared change is caught"). Proof: `uv run pytest tests/unit/api/test_conversion_api.py -q`.
- [ ] 4.2 Run the census through `fenolite.api.convert` (scenario "Demo boards are explained"): every remaining unexplained difference is either a kind and reason of the report that was missing (added here) or a fault of a writer (a task of c0160, named here); write the table into `docs/evidence/conversion.md`. Proof: `uv run pytest tests/corpus/test_convert_census.py -rA` with the corpus cached.

## 5. Command

- [ ] 5.1 Write `cmd_convert.py`, `schemas/fenolite.convert.v0.json` and the codes in `explain` (scenarios "Plan of a conversion", "Output over the source refused", "Exit 7 without consent", "Consistency suite"). Proof: `uv run pytest tests/unit/cli/test_convert_cmd.py tests/consistency -q`.
- [ ] 5.2 Add `result.conversions` to `capabilities` (scenario "Directions listed"); add the command's `fenolite-cmd` line to the page `files` of the agent guide and run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/cli/test_capabilities.py tests/unit/agent -q`.

## 6. Oracles

- [ ] 6.1 Write `tests/kicad/convert/test_triangle.py` and record `convert-triangle` on 10.0.6 (scenario "KiCad reads the converted document as the source"). Proof: `uv run pytest tests/kicad/convert/test_triangle.py -rA` in the pinned 10.0.6 image; `uv run pytest tests/kicad/test_probe_results.py`.
- [ ] 6.2 Write `tests/kicad/convert/test_retarget.py` and record `convert-retarget` (scenario "Version 9 project to KiCad 10"). Proof: `uv run pytest tests/kicad/convert/test_retarget.py -rA` in the pinned 9.0.9 and 10.0.6 images; `uv run pytest tests/kicad/test_probe_results.py`.

## 7. Documentation and closing

- [ ] 7.1 Write `docs/conversion.md` (the command, the kinds table, the report, the verification, the profiles, the directions) and the section `convert` of `docs/cli-contract.md`; link them from `docs/altium.md`. Proof: `uv run pytest tests/consistency tests/unit/convert/test_docs.py -q`.
- [ ] 7.2 Update the evidence labels: the three rows hold their measured levels and results in `docs/hypotheses.md`; `convert.EVIDENCE` and the `evidence` of each direction name their rows; `uv run python tools/gen_evidence_matrix.py` if the matrix lists the directions (else write why not). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_capability_evidence.py tests/unit/test_evidence_matrix_page.py -q`.
- [ ] 7.3 Add to `CHANGELOG.md` under Unreleased: the command `fenolite convert` with its report and verification, the two directions, the schema `fenolite.convert.v0`, and the `altium.not-lowered` info of kind `dnp`. Proof: `grep -n "fenolite convert" CHANGELOG.md`.
- [ ] 7.4 Run the residue scan and the fast suite. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes; `openspec validate c0159-convert-command --strict --no-interactive` passes.
