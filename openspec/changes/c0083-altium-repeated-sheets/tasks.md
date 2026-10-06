## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `altium-import`, `altium-project-reader` and `altium-verification` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code. Proof: `openspec validate c0083-altium-repeated-sheets --strict --no-interactive` passes.

## 1. Facts and registers

- [ ] 1.1 Add the six rows of the design to `docs/hypotheses.md` (backend `altium`, level `INFERRED`, result `pending`), register the new sources, and write the facts of repeats, naming formats and the annotation file to `docs/formats/altium/connectivity.md` and `project.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_format_facts.py`.
- [ ] 1.2 Author `tests/data/altium/channels/two/` with Fenolite's record writers from a committed script, and declare every file in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue`.

## 2. Annotation reader

- [ ] 2.1 Write `read/annotation.py` and return the file from `load_project` (scenario "Authored annotation file"). Proof: `uv run pytest tests/unit/backends/altium/read/test_annotation.py tests/unit/backends/altium/read`.

## 3. Channels

- [ ] 3.1 Write `parse_repeat` and the instantiation (scenarios of "Repeated sheets as channels"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py -k "instances or repeat"`; `uv run pyright src`.
- [ ] 3.2 Resolve designators from the board, the annotation file and the naming format (scenarios of "Channel designators"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py -k designator`.
- [ ] 3.3 Resolve the nets per channel (scenarios of "Channel nets"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py -k nets tests/unit/backends/altium/adapter`.
- [ ] 3.4 Apply the pin-to-pad map (scenario "Mapped pins"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channels.py -k pin_map tests/unit/checks/equivalence`.

## 4. Corpus and evidence

- [ ] 4.1 Write `tests/corpus/test_altium_channels.py` and measure the five sets again; update the table and the notes of `docs/evidence/altium-roundtrip.md` ("Repeated-sheet projects in the corpus run"). Proof: `uv run pytest tests/corpus/test_altium_channels.py -rA` with the corpus cached; `uv run pytest tests/unit/test_provenance.py`.
- [ ] 4.2 Build the files of Part R into a folder outside the repository, write their SHA-256 beside the steps in `docs/evidence/altium-schematic.md`, and hand them to the maintainer with the steps of the design ("Author report"). Record his report in the "Reports" section of `docs/evidence/altium-schematic.md` (tool as `AD <major>.<minor>`, date, one generic outcome per step, no artefact) and in `docs/hypotheses.md`; fix any fault the report names, and give a refuted row a registered successor. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 4.3 Document channels in `docs/altium.md` ("Hierarchy") and add the two codes to `src/fenolite/cli/data/explain.toml`. Proof: `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py`.

## 5. Closing

- [ ] 5.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0083-altium-repeated-sheets --strict --no-interactive` passes; `gh pr checks` shows `unit` passing.
- [ ] 5.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 5.3 Add to `CHANGELOG.md` under Unreleased: "The Altium import instantiates repeated sheets: each channel has its own components, nets and designators". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
