## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `altium-build`, `altium-project-reader`, `sheet-templates` and `manufacturing-exports` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code. Proof: `openspec validate c0087-altium-outjob-sheet --strict --no-interactive` passes.

## 1. Facts and registers

- [ ] 1.1 Record in `docs/formats/altium/output-job.md` the type and category names of the six output kinds, the medium types and each configuration key the writer sets, and in `sheet-template.md` the fields the template writer sets and the special strings, each with a source and a label; register new sources; add the seven rows to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 2. Output job

- [ ] 2.1 Write `outjob.py` (scenarios of "Output job written"). Proof: `uv run pytest tests/unit/backends/altium/test_outjob_write.py tests/unit/backends/test_evidence_declared.py`; `uv run pyright src`.
- [ ] 2.2 Write the job in the build and list it in the project file (scenarios of "Output job in an Altium build"). Proof: `uv run pytest tests/unit/lens/test_altium_outjob.py tests/unit/lens -k altium`.

## 3. Sheet template

- [ ] 3.1 Write `schdot.py` (scenarios of "Altium sheet template writing"). Proof: `uv run pytest tests/unit/backends/altium/test_schdot_write.py tests/unit/backends/altium/read -k sheet`.
- [ ] 3.2 Draw the sheet in the build and add `--target altium` to `template build` (scenarios "Frame on the sheet" and "Both targets from one specification"). Proof: `uv run pytest tests/unit/lens/test_altium_sheet.py tests/unit/cli/test_template_altium.py tests/consistency`.

## 4. Samples, reports and docs

- [ ] 4.1 Commit the samples under `tests/data/altium/outjob/` and `tests/data/altium/sheet/` and declare them in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue`.
- [ ] 4.2 Build the files of Parts V and W into a folder outside the repository, write their SHA-256 beside the steps in `docs/evidence/altium-schematic.md`, and hand them to the maintainer with the steps of the design ("Author report"). Record his report in the "Reports" section of `docs/evidence/altium-schematic.md` (tool as `AD <major>.<minor>`, date, one generic outcome per step, no artefact) and in `docs/hypotheses.md`; fix any fault the report names, and give a refuted row a registered successor. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 4.3 Document the job and the sheet in `docs/altium.md` and `docs/sheet-templates.md`; update `explain.toml` (`altium.outjob-not-listed`). Proof: `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py tests/unit/test_repo_layout.py`.

## 5. Closing

- [ ] 5.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0087-altium-outjob-sheet --strict --no-interactive` passes; `gh pr checks` shows `unit` passing.
- [ ] 5.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 5.3 Add to `CHANGELOG.md` under Unreleased: "An Altium build writes an output job set up from the export preset and draws the script's drawing sheet on its schematics; `template build --target altium` writes a `.SchDot` from a sheet specification". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
