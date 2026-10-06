## 0. Entry check

- [x] 0.1 Read `openspec list` and the living `altium-import`, `altium-project-reader` and `altium-verification` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code. Proof: `openspec validate c0083-altium-repeated-sheets --strict --no-interactive` passes.
  - 2026-10-06: none of the other v0.4 changes is needed. No other change modified the superseded requirements. The proposal's premise was wrong in part: see the design, "Found on 2026-10-06". The annotation file of `altium-set:02` is listed by its project and is no corpus row.

## 1. Facts and registers

- [ ] 1.1 Add the six rows of the design to `docs/hypotheses.md` (backend `altium`, level `INFERRED`, result `pending`), register the new sources, and write the facts of repeats, naming formats and the annotation file to `docs/formats/altium/connectivity.md` and `project.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_format_facts.py`.
  - 2026-10-06: partly done: `H-A-IMP-RPT-BOARD` (`CORPUS-VERIFIED`) and `H-A-IMP-RPT-FORMAT` (`INFERRED`) are registered with S-0452, and the facts are in `docs/formats/altium/connectivity.md`, "Channels". The rows `-COUNT`, `-NETS`, `-ANNOT` and `H-A-IMP-PINMAP` are added with their tasks.
- [ ] 1.2 Author `tests/data/altium/channels/two/` with Fenolite's record writers from a committed script, and declare every file in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue`.
  - 2026-10-06: not started; the unit tests of the first part author their sheets record by record in `tests/unit/backends/altium/adapter/test_channels.py`, which needs no committed data file.

## 2. Annotation reader

- [ ] 2.1 Write `read/annotation.py` and return the file from `load_project` (scenario "Authored annotation file"). Proof: `uv run pytest tests/unit/backends/altium/read/test_annotation.py tests/unit/backends/altium/read`.
  - 2026-10-06: waits. No public annotation file is in the corpus, and no public source describes its form well enough to write a reader clean-room. Needed from the maintainer: consent to add one corpus row for the annotation file that the project of `altium-set:02` lists (same repository and commit as S-0188), so that its form can be recorded from a public file.
  - 2026-10-06, later: the maintainer consented and the coordinator fetched it. The file is empty upstream: HTTP 200, 0 bytes, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (the digest of no bytes), at `https://raw.githubusercontent.com/raphaelchang/battman-hardware/db5ae48d09e9ec9523387e2190fd14671a0646ca/BMS/Battman.Annotation`. It shows nothing of the form, so no corpus row is added. The task stays open: the form of a non-empty annotation file is `UNKNOWN` until a public file or the maintainer's Part R (step R4) shows one. What holds meanwhile: an absent or empty annotation file changes nothing in the import.

## 3. Channels

- [ ] 3.1 Write `parse_repeat` and the instantiation (scenarios of "Repeated sheets as channels"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py -k "instances or repeat"`; `uv run pyright src`.
- [ ] 3.2 Resolve designators from the board, the annotation file and the naming format (scenarios of "Channel designators"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py -k designator`.
  - 2026-10-06: done for sources 1 and 3 (`adapter/channels.py`, `circuit.build_circuit`, `project.link`); source 2 waits for task 2.1. Proof run: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py` (17 passed) and `tests/corpus/test_altium_channels.py` (84 channel components of `altium-set:02`, none named otherwise by the board).
- [ ] 3.3 Resolve the nets per channel (scenarios of "Channel nets"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py -k nets tests/unit/backends/altium/adapter`.
- [ ] 3.4 Apply the pin-to-pad map (scenario "Mapped pins"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py -k pin_map tests/unit/checks/equivalence`.

## 4. Corpus and evidence

- [ ] 4.1 Write `tests/corpus/test_altium_channels.py` and measure the five sets again; update the table and the notes of `docs/evidence/altium-roundtrip.md` ("Repeated-sheet projects in the corpus run"). Proof: `uv run pytest tests/corpus/test_altium_channels.py -rA` with the corpus cached; `uv run pytest tests/unit/test_provenance.py`.
  - 2026-10-06: `tests/corpus/test_altium_channels.py` written; the sets measured again: `altium-set:02` 688 common, 13 only schematic, 37 only PCB, 2 differences (was 508, 26, 217, 4); sets 03, 04, 05 unchanged; set 01 is heavy and was not run. The page is updated. The task stays open until the remaining tasks change the counts again.
- [ ] 4.2 Build the files of Part R into a folder outside the repository, write their SHA-256 beside the steps in `docs/evidence/altium-schematic.md`, and hand them to the maintainer with the steps of the design ("Author report"). Record his report in the "Reports" section of `docs/evidence/altium-schematic.md` (tool as `AD <major>.<minor>`, date, one generic outcome per step, no artefact) and in `docs/hypotheses.md`; fix any fault the report names, and give a refuted row a registered successor. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 4.3 Document channels in `docs/altium.md` ("Hierarchy") and add the two codes to `src/fenolite/cli/data/explain.toml`. Proof: `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py`.
  - 2026-10-06: done for what exists: `docs/altium.md` ("Channels"), `explain.toml` and `docs/cli-contract.md` for the two codes.

## 5. Closing

- [ ] 5.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0083-altium-repeated-sheets --strict --no-interactive` passes; `gh pr checks` shows `unit` passing.
- [ ] 5.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 5.3 Add to `CHANGELOG.md` under Unreleased: "The Altium import instantiates repeated sheets: each channel has its own components, nets and designators". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
