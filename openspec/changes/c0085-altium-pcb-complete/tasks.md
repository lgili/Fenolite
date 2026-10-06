## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `altium-pcb-writer`, `altium-build` and `altium-pcb-reader` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code. Proof: `openspec validate c0085-altium-pcb-complete --strict --no-interactive` passes.

## 1. Facts and registers

- [ ] 1.1 For each new record kind, mark in `docs/formats/altium/pcb-records.md`, `pcb-copper.md` and `pcb-bodies.md` the fields the writer sets, each with its source and label (the reader's field evidence table is the base); register new sources; add the nine rows to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Author `tests/data/altium/board6/` (the design script and the built files) and declare its files in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue`.

## 2. Stack and vias

- [ ] 2.1 Write the stack and the extended layer map (scenarios of "Layer stacks of any even count"). Proof: `uv run pytest tests/unit/backends/altium/test_pcb_stack.py`; `uv run pyright src`.
- [ ] 2.2 Write via spans and drill pairs (scenario "Three spans"). Proof: `uv run pytest tests/unit/backends/altium/test_pcb_vias.py`.

## 3. Board items

- [ ] 3.1 Write text records (scenario "Accented text"). Proof: `uv run pytest tests/unit/backends/altium/test_pcb_text.py`.
- [ ] 3.2 Write graphics and keep-outs (scenario "Keep-out with two restrictions"). Proof: `uv run pytest tests/unit/backends/altium/test_pcb_graphics.py`.
- [ ] 3.3 Write non-plated holes and slots (scenario "Mounting hole"). Proof: `uv run pytest tests/unit/backends/altium/test_pcb_holes.py`.
- [ ] 3.4 Write component bodies (scenario "Body height"). Proof: `uv run pytest tests/unit/backends/altium/test_pcb_bodies.py`.

## 4. Build

- [ ] 4.1 Write the polygon contract and the accounting, and wire everything into the build (scenarios of "Unpoured polygons are a contract", "Written items are accounted" and "Complete board in an Altium build"). Proof: `uv run pytest tests/unit/lens/test_altium_pcb_complete.py tests/unit/lens -k altium`.

## 5. Oracle, report and docs

- [ ] 5.1 Write `tests/kicad/altium/test_pcb_complete_oracle.py` and record the `altium-pcbx-*` probes for KiCad 10.0.6 (the importer of 9.0.9 is run when it reads the document). Proof: `uv run pytest tests/kicad/altium/test_pcb_complete_oracle.py tests/kicad/test_probe_results.py -rA`.
- [ ] 5.2 Build the files of Part X into a folder outside the repository, write their SHA-256 beside the steps in `docs/evidence/altium-pcb.md`, and hand them to the maintainer with the steps of the design ("Author report"). Record his report in the "Reports" section of `docs/evidence/altium-pcb.md` (tool as `AD <major>.<minor>`, date, one generic outcome per step, no artefact) and in `docs/hypotheses.md`; fix any fault the report names, and give a refuted row a registered successor. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 5.3 Document the new items, the stack limits and the repour contract in `docs/altium.md`; update `explain.toml`. Proof: `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py tests/unit/test_repo_layout.py`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0085-altium-pcb-complete --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "The Altium PCB document holds stacks of up to 16 signal layers, blind and buried vias, board texts, graphics, keep-outs, non-plated holes and component bodies; polygons are written unpoured and repoured in Altium". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
