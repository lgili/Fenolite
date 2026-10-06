## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `altium-schematic-writer`, `altium-build`, `altium-schematic-reader` and `kicad-schematic` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code; and whether c0070's sheet-tree rule is archived (else the tree task waits). Proof: `openspec validate c0086-altium-schematic-complete --strict --no-interactive` passes.

## 1. Facts and registers

- [ ] 1.1 Record in `docs/formats/altium/schematic-records.md` and `schematic-ascii.md` the fields the writer sets for graphics, buses, bus entries, port and sheet-entry I/O types, parameters and the text encodings, each with its source and label; register new sources; add the seven rows to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Author `tests/data/altium/tree/` (script and built files) and declare its files in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue`.

## 2. Symbols

- [ ] 2.1 Map symbol graphics in `altsym.py` and write them in libraries and bodies (scenarios of "Symbol graphics in libraries and bodies"). Proof: `uv run pytest tests/unit/backends/altium/test_symbol_graphics.py tests/unit/backends/altium -k "schlib or symbol"`; `uv run pyright src`.

## 3. Hierarchy

- [ ] 3.1 Write the sheet tree (scenario "Two levels"). Proof: `uv run pytest tests/unit/backends/altium/test_sheet_tree.py tests/unit/lens -k "altium and hierarchy"`.
- [ ] 3.2 Write directions (scenarios of "Port and sheet-entry directions"). Proof: `uv run pytest tests/unit/backends/altium/test_directions.py`.
- [ ] 3.3 Write buses (scenario "Four-bit bus"). Proof: `uv run pytest tests/unit/backends/altium/test_bus_records.py`.

## 4. Text and parameters

- [ ] 4.1 Widen `text_problem` per form and write the companion fields (scenario "Accented value in the binary form"). Proof: `uv run pytest tests/unit/backends/altium/test_text_forms.py`.
- [ ] 4.2 Write component parameters (scenario "Manufacturer part number"). Proof: `uv run pytest tests/unit/backends/altium/test_parameters.py`.

## 5. Build, oracle, report and docs

- [ ] 5.1 Wire the build, regenerate the samples whose symbols change and list them under this task (scenarios of "Readable schematic in an Altium build"). Proof: `uv run pytest tests/unit/lens/test_altium_schematic_complete.py tests/unit/lens -k altium tests/corpus/test_manifest.py`.
- [ ] 5.2 Write `tests/kicad/altium/test_schematic_complete_oracle.py`: KiCad's import of the built project gives the model's netlist, sheet tree and bus members. Proof: `uv run pytest tests/kicad/altium/test_schematic_complete_oracle.py -rA` on KiCad 10.0.6.
- [ ] 5.3 Build the files of Part Y into a folder outside the repository, write their SHA-256 beside the steps in `docs/evidence/altium-schematic.md`, and hand them to the maintainer with the steps of the design ("Author report"). Record his report in the "Reports" section of `docs/evidence/altium-schematic.md` (tool as `AD <major>.<minor>`, date, one generic outcome per step, no artefact) and in `docs/hypotheses.md`; fix any fault the report names, and give a refuted row a registered successor. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 5.4 Rewrite "Limits" and the schematic sections of `docs/altium.md`; update `explain.toml` (`altium.bus-flattened`, `altium.text-unsupported`). Proof: `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py tests/unit/test_repo_layout.py`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0086-altium-schematic-complete --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "The Altium schematic draws each symbol's own graphics, follows the module tree at any depth, and carries port directions, buses, parameters and text outside ASCII". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
