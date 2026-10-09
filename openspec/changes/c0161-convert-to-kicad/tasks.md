## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living `kicad-file-backend` spec and the deltas of c0159 and c0160. Write under this task, with the date: that c0159 is archived or its package and verification are on the branch (else stop); whether c0160 is archived (its derived library is the model of this change's; its `KICAD_MECHANICAL` is the inverse map and must not contradict this one); whether another open change adds a requirement on layers to `kicad-file-backend`; the maintainer's answers to the open questions (given on 2026-10-09: every recommended answer, `docs/roadmap.md` Open decisions row 40). Proof: `openspec validate c0161-convert-to-kicad --strict --no-interactive` passes.

## 1. Measure, facts and register

- [ ] 1.1 Write `tests/corpus/test_convert_altium_census.py` from the design's measurement (the eight documents: the `KeyError` today, the undeclared layer names and counts, the two slot failures with the pad shapes of their slots). Proof: `uv run pytest tests/corpus/test_convert_altium_census.py -rA` with the corpus cached.
- [ ] 1.2 Run `kicad-cli` 9.0.9 and 10.0.6 on the six probe boards of measurement 2 (load, DRC) and write what KiCad does with the undeclared layer names under this task. Record the user layers of each major (names, numbers, the most a board holds) from KiCad-written files and a probe board: rows in `docs/formats/kicad/board.md` with `H-K-BOARD-USERLAYERS`, and `tests/kicad/board/test_user_layers.py` with the probe `pcb-user-layers`. Proof: `uv run pytest tests/kicad/board/test_user_layers.py -rA` in both pinned images; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`.
- [ ] 1.3 Register S-0742 (the public Altium page on the Keep-Out layer) in `docs/evidence/sources.md` and write its fact row into `docs/formats/altium/import.md`, or write here that no page states it (then keep-out drawings are lost, the second item of the cut order). Add the rows `H-K-CONV-A2K-LOAD`, `H-K-CONV-A2K-IMPORT`, `H-K-CONV-A2K-SCH`, `H-K-BOARD-USERLAYERS` and `H-A-IMP-KEEPOUT-LAYER` to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_format_facts.py -q`.
- [ ] 1.4 Census of committed boards: write every committed KiCad board, every example and every test script's board, and assert that none holds an item on an undeclared layer (the precondition of task 2.2). Proof: `uv run pytest tests/unit/backends/kicad/test_layer_undeclared.py -k census -q`.

## 2. Board

- [ ] 2.1 Write `layers.board_rows` for even counts 2 to 32 and the non-copper map, the user layers per target, odd counts (scenario "Mechanical and keep-out layers" without keep-outs). Third item of the cut order for odd counts. Proof: `uv run pytest tests/unit/backends/kicad/test_layers.py tests/unit/convert/test_to_kicad.py -k layers -q`.
- [ ] 2.2 Write the refusal `kicad.board.layer-undeclared` (scenarios "Line on an unknown layer", "Committed boards unchanged"). Proof: `uv run pytest tests/unit/backends/kicad/test_layer_undeclared.py tests/unit/backends/kicad -q`.
- [ ] 2.3 Write keep-out outlines as rule areas (scenario "Mechanical and keep-out layers"). Second item of the cut order. Proof: `uv run pytest tests/unit/convert/test_to_kicad.py -k keepout -q`.
- [ ] 2.4 Write slots turned with a round or aligned pad (scenario "Round pad with a turned slot"); names, net names, the derived `<project>.pretty`. Proof: `uv run pytest tests/unit/backends/kicad/test_fpmap_slots.py tests/unit/convert/test_to_kicad.py -k "slot or names or library" -q`.

## 3. Schematic and project

- [ ] 3.1 Write the symbols from `.SchLib` and generic symbols, `<project>.kicad_sym` and its table, and the generated schematic (`readable`). First item of the cut order for the `.SchLib` symbols. Proof: `uv run pytest tests/unit/convert/test_to_kicad.py -k schematic -q`.
- [ ] 3.2 Write the project, rules and stack-up through `write_triad` for targets 9 and 10, register the direction and its profile `altium-to-kicad` (scenarios "Plan of an Altium sample", "Public documents converted"). Proof: `uv run pytest tests/unit/cli/test_convert_cmd.py -k altium_to_kicad -q`; `uv run pytest tests/corpus/test_convert_altium_census.py -rA` with the corpus cached.

## 4. Oracles

- [ ] 4.1 Write `tests/kicad/convert/test_a2k_load.py` and record `convert-a2k-load` (scenario "KiCad loads the converted board"). Proof: `uv run pytest tests/kicad/convert/test_a2k_load.py -rA` in the pinned 9.0.9 and 10.0.6 images with the corpus cached; `uv run pytest tests/kicad/test_probe_results.py`.
- [ ] 4.2 Write `tests/kicad/convert/test_a2k_import.py` and record `convert-a2k-import` (scenario "Two converters agree"); a disagreement is fixed, or becomes a rule of the profile `kicad-import` with its hypothesis, written here. Proof: `uv run pytest tests/kicad/convert/test_a2k_import.py -rA` in the pinned 10.0.6 image; `uv run pytest tests/kicad/test_probe_results.py`.
- [ ] 4.3 Write `tests/kicad/convert/test_a2k_schematic.py` and record `convert-a2k-sch` for the public sets the generator takes. Proof: `uv run pytest tests/kicad/convert/test_a2k_schematic.py -rA` in both pinned images; `uv run pytest tests/kicad/test_probe_results.py`.

## 5. Closing

- [ ] 5.1 Document the direction, the layer map, the refusal and the census in `docs/conversion.md`, `docs/formats/kicad/board.md` ("The writer") and `docs/evidence/conversion.md`; add a `fenolite-cmd` line of `convert --to kicad` to the agent guide's page `altium` and run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/convert/test_docs.py tests/unit/agent -q`.
- [ ] 5.2 Update the evidence labels: the five rows hold their measured levels and results; the direction's evidence names them; `uv run python tools/gen_evidence_matrix.py`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_evidence_matrix_page.py -q`.
- [ ] 5.3 Add to `CHANGELOG.md` under Unreleased: `fenolite convert --to kicad` for Altium projects, the census, and the refusal of items on undeclared layers (a change of behaviour of `write_board`). Proof: `grep -n "layer-undeclared" CHANGELOG.md`.
- [ ] 5.4 Run the residue scan and the fast suite. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes; `openspec validate c0161-convert-to-kicad --strict --no-interactive` passes.
