## 0. Proposal

- [x] 0.1 Read the report of step R1 (S-0615) and the records of the sample; compare them with the corpus (38 schematic documents, 6 project files) with Fenolite's own reader and with Altium's public pages; rank the hypotheses; write the proposal, the design and the delta. Proof: `openspec validate c0151-repeat-bus-split --strict --no-interactive` passes.
  - **2026-10-08.** No corpus schematic document holds `Repeat`, a bus line or a sheet entry on a bus, so the record form of a working `Repeat` bus is not in any public file. What the corpus does show: no sheet entry (0 of 251) and no port (0 of 208) has a net label on its connection point, and the sample's bus label lay on the entry's point (2200 mil, 6500 mil), the point the warning names. Pages read again or for the first time: the multi-channel page (S-0520), the hierarchy page (S-0185, the sync dialog renames a matched port) and the violation pages of a project's validation (S-0707). Five hypotheses, ranked in the design. Validation: valid.

## 1. Facts first

- [x] 1.1 Record the facts: one row in `docs/formats/altium/connectivity.md` (no label on a connection point in the corpus), one in `docs/formats/altium/project.md` (the `[Design]` keys of all six corpus projects), `docs/evidence/sources.md` (S-0706, S-0707), `docs/hypotheses.md` (`H-A-SCHRPT-BUSLABEL`, `H-A-SCHRPT-ATTACH`), the messages of step R1 under Part R of `docs/evidence/altium-schematic.md`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_altium_rows.py -q`.
  - **2026-10-08.** The counts were measured before the code; the pages were written together with it, not before. Both rows `INFERRED`, "pending (author report)". The two format rows are `INFERRED` (an absence and a key census, counts only). The rows were first named `H-A-IMP-RPT-*`, but that family is the import's own claim (`test_package.py::test_evidence_is_the_lowest_level_of_the_registered_rows` failed in `make check-fast`), so they form the family `H-A-SCHRPT-*`, which `tests/unit/test_format_facts.py` now lists among the Altium families. 128 passed.

## 2. The writer and the sample

- [x] 2.1 `layout.BusBlock.label_point` and the bus label record of `schdoc` at it; the cell reaches the label's text. Tests: `test_bus_label_lies_beside_the_connection_point`, `test_four_bit_bus` updated; the tree golden written again with the reason. Proof: `uv run pytest tests/unit/backends/altium/test_bus_records.py tests/unit/lens/test_altium_schematic_complete.py -q`.
  - **2026-10-08.** 15 and 41 passed. Only `test_tree` failed before the golden was written again (`FENOLITE_GOLDEN_WRITE=1`): `tree.SchDoc`, `tree_io.SchDoc` and `tree_io.leds.SchDoc` changed, the other files of the folder did not. No other golden or pin of `tests/unit/lens`, `tests/unit/backends/altium`, `tests/unit/cli` and `tests/unit/verify` moved (4 250 and 426 passed on the changed code before the golden was written).
- [x] 2.2 The sample: `tests/_altium_channels.project_text` with `NETLIST_KEYS` in the corpus order; `author.py` run; `test_repeat_bus_and_project_forms`; the notes of `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/unit/backends/altium/adapter/test_channel_files.py tests/unit/backends/altium/adapter/test_repeat.py tests/unit/backends/altium/adapter/test_channels.py -q` with `test_repeat.py` unedited.
  - **2026-10-08.** 71 passed. `two.PrjPcb` `38384a5c…` to `b1b67bdf…`, `two.SchDoc` `42e8a026…` to `917fe6fb…`, `two_ch.SchDoc` unchanged (`cad7f566…`). The import reads the same channels, designators and nets (`test_folder_reads_as_two_channels`, unedited).
- [x] 2.3 The maintainer's check folder: `A-principal`, `B-projeto-antigo`, `C-rotulo-antigo`, `LEIA-ME.md` in Brazilian Portuguese, `SHA256SUMS.txt`; step R5 and its digests under Part R. Proof: the digests of `SHA256SUMS.txt` equal the table of step R5.
  - **2026-10-08.** Built in the session's scratch folder `c0151-check/` (outside the repository) from the committed sample and, for B and C, from the base's `two.PrjPcb` and `two.SchDoc`.

## 3. Altium

- [ ] 3.1 Step R5 of Part R in Altium Designer 26: the three folders opened without the sync dialog, compiled, the messages copied; the dialog read and cancelled only where the child is missing; what the dialog did in session 2. Proof: the report is recorded under Part R of `docs/evidence/altium-schematic.md`, and `H-A-SCHRPT-BUSLABEL`, `H-A-SCHRPT-ATTACH` and `H-A-IMP-RPT-NETS` are moved or kept with their reason.
  - owed: maintainer, AD26.
- [ ] 3.2 If step R5 shows that the project keys attach the child, a follow-up change moves them into `prjpcb.write_prjpcb`; if A fails, a follow-up tries the Altium bookkeeping of hypothesis A2. Proof: the follow-up is proposed with the report of 3.1.
  - owed: maintainer, AD26 (it waits for 3.1).

## 4. Closing

- [x] 4.1 `CHANGELOG.md` (the line at the end of `[Unreleased]`, the change of bytes in bold), `openspec/README.md`, `docs/roadmap.md`, `LEGAL-ANNEX.md`; the generators. Proof: `uv run python tools/gen_evidence_matrix.py --check`, `uv run python tools/gen_schemas.py --check`, `uv run python tools/gen_token_docs.py --check`.
  - **2026-10-08.** The three generators pass `--check` with nothing to write: no module's declared evidence changed. `openspec validate c0151-repeat-bus-split --strict --no-interactive`: valid.
- [x] 4.2 `make check-fast` once; the corpus tests of the Altium schematic and project readers; after `git add -A`, `uv run pytest tests/corpus/test_manifest.py tests/residue -q`. Proof: each exits 0.
  - **2026-10-08.** Linux, Python 3.13, three workers, while another session used the machine. `make check-fast PYTEST_WORKERS=3`: 9 909 passed, 18 skipped, 1 failed (`test_package.py::test_evidence_is_the_lowest_level_of_the_registered_rows`: the first names of the two rows, see 1.1); after the rename, lint, format, pyright (0 errors), the residue scan and the 128 tests of the registers, the fact pages and the evidence pass; the fast suite was not run a second time. Corpus, `tests/corpus -k "altium and (sch or text or channels or project)"`: 162 passed, 25 skipped (heavy items and items missing from the cache), exit 0. After staging every file: `tests/corpus/test_manifest.py tests/residue` 80 passed, 5 skipped. `tests/unit/lens/test_build_bytes_pinned.py`: 83 passed, no pin moved.
- [ ] 4.3 Run the full suite once on the rebased branch. Proof: `make check` passes.
  - Not run here: the coordinator runs it once at the merge.
