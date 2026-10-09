## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living `altium-compound-reader`, `altium-pcb-writer` and `altium-schematic-writer` specs, and c0159's delta. Write under this task, with the date: that c0159 is archived or its report and census are on the branch (else stop: the baseline needs them); whether c0126, c0123 and c0146, which write footprint items and schematic fonts, are archived; whether another open change adds a requirement of the same name to one of the three specs; the maintainer's answers to the open questions (given on 2026-10-09: every recommended answer, `docs/roadmap.md` Open decisions row 40). Proof: `openspec validate c0160-convert-to-altium --strict --no-interactive` passes.

## 1. Baseline, facts and register

- [ ] 1.1 Run c0159's census and write the baseline into `docs/evidence/conversion.md` under "KiCad to Altium, before c0160": per board, the counts per kind and reason. Proof: `uv run pytest tests/corpus/test_convert_census.py -rA` with the corpus cached.
- [ ] 1.2 Write the DIFAT write rows into `docs/formats/altium/compound-file.md` (S-0145) and check whether `read/cfb.py` follows the DIFAT chain (write the answer here). Proof: `uv run pytest tests/unit/test_format_facts.py -q`.
- [ ] 1.3 Write the pad rows into `docs/formats/altium/pcb-library.md`: stack modes 1 and 2 and their tables, the paste and mask expansions of a connector pad, from S-0160 and S-0302; search a public page for an empty pad designator and register it as S-0740, or write that none was found (then free pads). Register S-0741 if the expansions need it. Add the rows `H-A-CONV-DIFAT`, `H-A-CONV-PADSTACK`, `H-A-CONV-LIBRARY`, `H-A-CONV-SCHEMATIC` to `docs/hypotheses.md`. No writer code before this task is ticked. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`.

## 2. DIFAT and pads

- [ ] 2.1 Write DIFAT sectors in `cfb.write_compound` and the reader's chain (scenario "Large file written and read"); every committed Altium sample keeps its bytes. Proof: `uv run pytest tests/unit/backends/altium/test_cfb_difat.py tests/unit/backends/altium -q`.
- [ ] 2.2 Write full-stack pad records (scenario "Per-layer stack read back"). Proof: `uv run pytest tests/unit/backends/altium/test_pcblib_stacks.py -q`.
- [ ] 2.3 Write connector pads and pads without a number (scenario "Connector pad"). Second item of the cut order. Proof: `uv run pytest tests/unit/backends/altium/test_pcblib_stacks.py -k "connect or unnamed" -q`.
- [ ] 2.4 Write `tests/kicad/convert/test_triangle_large.py` and record `convert-difat` and `convert-padstack` on 10.0.6 (scenario "KiCad imports a large document"). Proof: `uv run pytest tests/kicad/convert/test_triangle_large.py -rA` in the pinned 10.0.6 image with the corpus cached; `uv run pytest tests/kicad/test_probe_results.py`.

## 3. Layers and library

- [ ] 3.1 Write `lower.KICAD_MECHANICAL` and copper texts (scenario "Drawing on Dwgs.User"). Third item of the cut order for the layers beyond the fabrication layers. Proof: `uv run pytest tests/unit/backends/altium/test_lower_layers.py -q`.
- [ ] 3.2 Write the derived `<name>.PcbLib` and the `changed` count of edited instances (scenario "Two instances, one edited"). Proof: `uv run pytest tests/unit/backends/altium/test_derived_library.py tests/unit/convert -q`.

## 4. Schematic

- [ ] 4.1 Take the circuit and the symbol graphics of a KiCad source's schematic and write one Altium sheet per KiCad sheet (scenario "Netlist kept"). First item of the cut order. Proof: `uv run pytest tests/unit/convert/test_to_altium_schematic.py -q`; `uv run pytest tests/corpus/test_convert_census.py -k complex_hierarchy -rA`.
- [ ] 4.2 Write the tolerant texts and nets (scenario "Text outside the code page"). Proof: `uv run pytest tests/unit/backends/altium/test_schematic_tolerant.py -q`.
- [ ] 4.3 Run RT-A3 over the public project sets (scenario "Public project sets judged") and write the table again in `docs/evidence/altium-roundtrip.md`, "Project sets", with `H-A-VER-RTA3-PRJ` measured again. Proof: `uv run pytest tests/corpus/test_altium_rta3.py -k sets -rA` with the corpus cached.

## 5. Census and Part T

- [ ] 5.1 Run the census (scenario "Census after the change") and write "KiCad to Altium, after c0160" into `docs/evidence/conversion.md`. Proof: `uv run pytest tests/corpus/test_convert_census.py -rA` with the corpus cached.
- [ ] 5.2 Build the three projects of Part T into `~/fenolite-altium-checks/session-3/T-convert/` with a `README.md` and their SHA-256, and write Part T (steps T1 to T6) into `docs/evidence/altium-pcb.md`. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -q`.
- [ ] 5.3 **Maintainer, in Altium Designer.** Run Part T and give the report; record it under "Reports" of `docs/evidence/altium-pcb.md` (tool `AD <major>.<minor>`, date, one generic outcome per step, no artefact), register its source, and set the four rows' results (scenario "Part T recorded"). OPEN until Altium was run; nothing is marked `ALTIUM-VERIFIED` before. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 6. Closing

- [ ] 6.1 Document the closed losses, the layer map, the derived library, the converted schematic and the tolerant write in `docs/conversion.md` and `docs/altium.md`. Proof: `uv run pytest tests/unit/convert/test_docs.py -q`.
- [ ] 6.2 Update the evidence labels: the four rows and `H-A-VER-RTA3-PRJ` hold their measured levels and results; `pcbdoc.EVIDENCE`, `pcblib.EVIDENCE`, `cfb` and `schdoc` name the rows they rest on; `uv run python tools/gen_evidence_matrix.py`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_evidence_matrix_page.py -q`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: DIFAT sectors, full-stack, connector and free pads, the layer map, the derived PCB library, the converted schematic and the tolerant write, with the census counts. Proof: `grep -n "DIFAT" CHANGELOG.md`.
- [ ] 6.4 Run the residue scan and the fast suite. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes; `openspec validate c0160-convert-to-altium --strict --no-interactive` passes.
