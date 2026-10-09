One run on 2026-10-07 implemented every task. The proofs ran in the worktree of the change; the one full `make check` is the coordinator's, at the merge. What was run, with exit codes and counts, is in the design, "Implementation notes". Section 6 holds the corrections after the review of the same day; its proofs ran on the tree rebased onto `dev` at 6f6227eb.

## 1. The rule and its measure

- [x] 1.1 Write `tests/_pintext.py` (the two text sizes, `shown_texts`, `body_box`, `judge`, `repeats`, `findings`) and `tests/unit/catalog/test_pin_text_legibility.py` (every catalog symbol, every library under `examples/`, the mini library; `KNOWN`; the measure on symbols made for it). Run it on the base before any definition changes.

  Proof: on an export of the base commit 17234727 with these two files added, `uv run pytest tests/unit/catalog/test_pin_text_legibility.py` exits 1 with the five named symbols among its failures.
- [x] 1.2 Compare the KiCad-size boxes with what `kicad-cli` 10.0.6 draws: place every catalog symbol and every symbol of the example library alone, build, `sch export svg`, and compare the glyph strokes of each pin text with its box. Correct the estimate where a stroke leaves its box.

  Proof: every stroke lies inside its box (design, Decision 2); `uv run pytest tests/unit/catalog/test_pin_text_legibility.py -k "writers or boxes or overbar"`.

## 2. Definitions

- [x] 2.1 Catalog: `_NAMED_BLOCKS` and the flag; the strokes of the two amplifiers, the bridge and the optocoupler; the pins of `Schottky_Diode`. Update `test_catalog.py` and `test_symbol_expansion.py` for the strokes and the pins.

  Proof: `uv run pytest tests/unit/catalog/test_catalog.py tests/unit/catalog/test_symbol_expansion.py`; `uv run pyright src`.
- [x] 2.2 Catalog: the four rectangles that keep their names, sized on the 2.54 mm grid to pass the rule (design, Decision 5). Update `test_symbol_graphics.py::test_rectangle_symbol_keeps_its_size`; add the scenario of the regulator to `test_catalog.py`.

  Proof: `uv run pytest tests/unit/catalog/test_pin_text_legibility.py tests/unit/backends/altium/test_symbol_graphics.py`; `uv run pytest tests/unit/catalog/test_catalog.py -k linear_regulator`.
- [x] 2.3 Example library: `CONN2` hides its names; `DUAL_OPAMP` and `MCU8` get their larger bodies. Update the text edit of `test_altium_issues.py`.

  Proof: `uv run pytest tests/unit/catalog/test_pin_text_legibility.py -k FenoliteDemo`; `uv run pytest tests/unit/lens/test_altium_issues.py`.

## 3. What depends on the definitions

- [x] 3.1 Regenerate the seven symbol preview sheets with `tools/catalog/render_symbols.py`; the relay's stem labels are numbers now.

  Proof: `uv run pytest tests/unit/catalog/test_symbol_previews.py`.
- [x] 3.2 Regenerate the Altium samples `tree`, `kicad_example` and `no_connect` with `FENOLITE_GOLDEN_WRITE=1` on their three golden tests, and name their SHA-256 in Parts L, N and Y of `docs/evidence/altium-schematic.md`, each with one dated sentence.

  Proof: `uv run pytest tests/unit/lens/test_altium_schematic_complete.py tests/unit/lens/test_altium_schlib_golden.py tests/unit/lens/test_altium_no_connect_golden.py`.
- [x] 3.3 Keep the generic copies: add the example library of commit 6cdf0aea as `tests/data/altium/generic/library/FenoliteDemo.kicad_sym`, declare it in `tests/data/MANIFEST.toml`, and build the generic samples of `examples/altium_kicad` from it in the three tests that pin them.

  Proof: `uv run pytest tests/unit/lens/test_altium_schematic_complete.py tests/unit/lens/test_altium_pcb_complete.py tests/unit/cli/test_build_altium.py -k "generic or samples or symbols_option"`; `uv run pytest tests/corpus/test_manifest.py`.
- [x] 3.4 Show that nets and boards did not change: every example and sample script built for both targets before and after, with the nets KiCad and Fenolite's importer read and every file's SHA-256; every authored symbol with each pin on a net, read by `kicad-cli sch export netlist`.

  Proof: equal nets and equal board files (design, "Implementation notes"); `uv run pytest tests/unit/lens/test_altium_schematic_complete.py -k "nets_unchanged or readback"`; `git status --short` lists no `.kicad_pcb`, `.PcbDoc` or `.PcbLib`.
- [x] 3.5 Look at the changed symbols as KiCad 10.0.6 draws them (`sch export pdf` and `sch export svg`), before and after.

  Proof: the pictures; what they show is in the design, "Implementation notes".

## 4. Documents

- [x] 4.1 The spec delta: ADDED "Legible pin texts", MODIFIED "Connected, legible schematic symbol drawings".

  Proof: `openspec validate --all --strict --no-interactive`.
- [x] 4.2 `docs/catalog/README.md` (the rule) and `docs/catalog/sources.md` (the added strokes state no new fact).

  Proof: `uv run pytest tests/unit/catalog tests/unit/test_provenance.py tests/unit/test_repo_layout.py`.

## 5. Closing

- [x] 5.1 Run the residue and the fast suites, the unit suite on Python 3.11, and the KiCad suites that draw or read these symbols.

  Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue -q`; `make check-fast`; `uv run --isolated --python 3.11 --extra dev pytest tests/unit -q -n 4 -p no:cacheprovider`; `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/schematic tests/kicad/altium tests/kicad/check -q -n 4` on KiCad 10.0.6; `tests/kicad/schematic` inside the pinned 9.0.9 image.
- [x] 5.2 Evidence labels: none changes. Check that the registers and the generated pages still agree.

  Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run python tools/gen_schemas.py --check`; `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py tests/unit/test_format_facts.py`.
- [x] 5.3 Add the entry to `CHANGELOG.md` under Unreleased: which symbols look different and why, that a design gets a different schematic once, and that nets and boards stay.

  Proof: `git diff --stat CHANGELOG.md` lists the file.

## 6. After the review of 2026-10-07

- [x] 6.1 The measure: the marks of the nine pin shapes as `kicad-cli` 10.0.6 draws them (`pin_marks`, finding `MARK`); numbers judged against strokes as names are; a shown text with a character that was not compared is the finding `UNCHECKED`; the module says that all units' strokes are pooled and that only body style 1 is measured.

  Proof: `uv run pytest tests/unit/catalog/test_pin_text_legibility.py -k "mark or number or character"`; on an export of 6f6227eb the whole file exits 1 with `MCU8`, `R_V` and the two polarized capacitors among its failures.
- [x] 6.2 Definitions that the wider measure finds: `MCU8` (20 x 16 units, pins of 5.08 mm on a pitch of 5.08 mm, name offset 1.778 mm), `R_V` (pins of 2.54 mm), `Capacitor_Polarized` and `Capacitor_Electrolytic` (the plus below the lead). `Offline_Power_Controller` is 16 x 8 units.

  Proof: `uv run pytest tests/unit/catalog tests/unit/lens/test_altium_issues.py`.
- [x] 6.3 Regenerate by their tools: the preview sheets, and the five files of `kicad_example` and `no_connect`; name the new SHA-256 in Parts L, N and Y of `docs/evidence/altium-schematic.md`. The files of the tree sample keep the bytes of the first run.

  Proof: `uv run pytest tests/unit/catalog/test_symbol_previews.py tests/unit/lens/test_altium_schematic_complete.py tests/unit/lens/test_altium_schlib_golden.py tests/unit/lens/test_altium_no_connect_golden.py`; `git diff --stat HEAD -- tests/data/altium/tree` is empty.
- [x] 6.4 Look at the five named symbols and at every definition this section changed as KiCad 10.0.6 draws them (`sch export pdf`).

  Proof: the pictures; what they show is in the design, "Implementation notes", point 11.
- [x] 6.5 The change is a folder on `dev`: its register row in `openspec/README.md` and its place in the milestone row of `docs/roadmap.md`. One test is renamed for what it checks.

  Proof: `openspec validate --all --strict --no-interactive`; `uv run pytest tests/unit/test_altium_verification_docs.py tests/unit/test_release_record_v02.py`, the tests that read the roadmap and the register.
- [x] 6.6 Run again, each whole: the legibility test, `openspec validate --all --strict`, `make check-fast`, the unit suite on Python 3.11, the manifest and residue tests, the two generator checks, the KiCad 10.0.6 suites of the schematic, the Altium samples and the checks, and the sign-off check.

  Proof: the table of point 11 of the design's "Implementation notes".
