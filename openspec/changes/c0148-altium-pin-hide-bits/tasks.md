## 0. Investigation

- [x] 0.1 Find every place that writes or reads bits 0x08 and 0x10 of `PINCONGLOMERATE`, and measure the bits of the Altium-saved pins of the corpus. Proof: `design.md`, Context and "The evidence".
  - **2026-10-08.** One writer property (`altsym.AltiumPin.conglomerate`) and two reader properties (`records.Pin.name_shown`, `designator_shown`); the adapter maps neither into the model; the KiCad side and the catalog rule of c0134 read no bit. Corpus (S-0614): all 4 175 pins hold 0x20, which Fenolite never wrote, and the split by component size favours show flags, so a plain flip of the reader, as first proposed, would misread every Altium-saved file. Reported to the maintainer with two options; option B chosen.
- [x] 0.2 Build the check project `tests/data/altium/pinbits/` (author script, the writer's own `write_project`) for the maintainer's session. Proof: the three files read back with the four conglomerates 0x20, 0x30, 0x28 and 0x38 above the direction; `author.py` gives the same bytes twice.
  - **2026-10-08.** `pinbits.PrjPcb` `da8fcf56…`, `pinbits.SchDoc` `d0cc87c9…`, `pinbits.SchLib` `1211bea9…`; the maintainer opened them in Altium Designer 26.5.0 the same day: V1 neither, V2 numbers, V3 names, V4 both (S-0613).

## 1. Facts first

- [x] 1.1 Fact rows of `docs/formats/altium/schematic-library.md` and `schematic-ascii.md`, a note in `schematic-records.md`; `docs/evidence/sources.md` (S-0612, S-0613, S-0614); `docs/hypotheses.md` (`H-A-SCHLIB-PINBITS`, a note on `H-A-SCHLIB-PIN`); `docs/evidence/altium-schematic.md` ("Pin visibility bits"). Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_altium_rows.py tests/unit/backends/altium/read/test_sch_records_table.py -q`.
  - **2026-10-08.** Passed. The level of an author report takes the form `AD <major>.<minor or x>`: `AD 26.5` for S-0613 (26.5.0 in the text), `AD 26.x` for S-0612 (no minor version stated).

## 2. Writer and reader

- [x] 2.1 `altsym.SHOW_FLAGS` on every written pin; `records.Pin.name_shown` and `designator_shown` read show flags with 0x20 and hide flags without it. Tests: `tests/unit/backends/altium/test_pinbits.py` (name hidden and number shown gives 0x08 clear and 0x10 set, and the reverse; text pins with and without 0x20; the check project). Proof: `uv run pytest tests/unit/backends/altium -q`; `uv run pyright src`.
  - **2026-10-08.** Passed; pyright 0 errors. The first `make check-fast` failed one test, `tests/unit/lens/test_altium_build.py::test_evidence`: every `H-A-SCHLIB-` row is a claim of the build, so `schlib.EVIDENCE` names `H-A-SCHLIB-PINBITS`, and `docs/evidence/matrix.md` was generated again (the row and the module's list).

## 3. Samples and pins

- [x] 3.1 Write the committed samples again with their own tools (`FENOLITE_GOLDEN_WRITE=1` for the golden tests, `tests/data/altium/channels/two/author.py`, the generic copies by the build `test_generic` runs); compare each with its former bytes record by record (`tests/_pin_bits.py`); update the protocol tables of committed files. Proof: `uv run pytest tests/unit/lens tests/unit/backends/altium tests/unit/cli -q`.
  - **2026-10-08.** 38 schematic documents and libraries changed (812 pins), every one equal to its former bytes but for 0x20 on each pin. The tables of the maintainer's folders keep their digests (what he was given); the short set of Part X takes the new ones, with a line on the folder. `test_altium_samples_of_earlier_changes_keep_their_bytes` compares the schematic files of the earlier samples and the generic copies with the base through `pin_bits_only`.
- [x] 3.2 Move the ten Altium pins of `tests/unit/lens/test_build_bytes_pinned.py`, the reason beside each; no KiCad pin moves. Proof: `uv run pytest tests/unit/lens/test_build_bytes_pinned.py -q`; `git diff` shows the `ALTIUM` table alone.
  - **2026-10-08.** Measured against builds with the base code (`git archive` of `src` at the base): per design the schematic document and library change (pin bit alone, checked record by record) and `.fenolite/build.json` names their digests; no other file changes.

## 4. Closing

- [x] 4.1 `CHANGELOG.md` (the line at the end of `[Unreleased]`), `openspec/README.md`, `docs/roadmap.md`, `LEGAL-ANNEX.md`, `src/fenolite/backends/altium/PROVENANCE.md`, `tests/data/MANIFEST.toml`; generated pages last. Proof: `uv run python tools/gen_evidence_matrix.py --check`, `tools/gen_schemas.py --check`, `tools/gen_token_docs.py --check`; `uv run pytest tests/residue tests/corpus/test_manifest.py -q`.
- [x] 4.2 `make check-fast`; the corpus Altium tests (`uv run pytest tests/corpus -k altium -q`), with the new `tests/corpus/test_altium_pin_bits.py` (every saved pin holds 0x20; the split of the documents); `openspec validate c0148-altium-pin-hide-bits --strict`. Proof: each exits 0, counts in the commit message.
- [ ] 4.3 Open a rebuilt kit sample in Altium Designer 26 and look at the pin texts of the catalog LED. Proof: a report under "Pin visibility bits" of `docs/evidence/altium-schematic.md`.
  - Open (2026-10-08): only the check project was opened.
- [ ] 4.4 Run the full suite once on the rebased branch. Proof: `make check` passes.
  - Not run here: the coordinator runs it once at the merge.
