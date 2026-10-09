## 0. Investigation

- [x] 0.1 Reproduce the refusal on the cached `kicad-demo-10-0-6-pcb-13` (`uv run python tools/corpus_fetch.py --only kicad-demo-10-0-6-pcb-13`), with its codes, constructs and locators, and find the root cause. Proof: `design.md`, Context.
  - **2026-10-09.** On `origin/dev` 833eefa: four `kicad.board.opaque-net-ref` errors for target 9 on teardrop zones 179, 180, 181 and 192; the source map of `write_board` gives model names, the target-9 numbering stored names.
- [x] 0.2 Census: `write_board` for the own major and for 10 over every cached `.kicad_pcb` row of major 9 or 10, before and after the fix; the target-10 texts of the other rows compared byte for byte. Proof: the counts in this task's note.
  - **2026-10-09.** 23 boards read (21 of major 9, 2 of major 10), 44 writes. Before: one refused (`kicad-demo-10-0-6-pcb-13`, target 9). After: none; the 42 texts of the other boards have the same SHA-256 before and after. `design.md`, "Census of the corpus".

## 1. Facts first

- [x] 1.1 A fact row in `docs/formats/kicad/board.md` (the teardrops of the demo board reference nets stored with `{slash}` by number, `CORPUS-VERIFIED`, S-0058) and the writer's "Net forms" bullet (the stored spelling). Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py -q`.
  - **2026-10-09.** Passed; a second row records the oracle result of task 3.1 (`KICAD-VERIFIED (9.0.x, 10.0.x)`, S-0020).

## 2. Writer

- [x] 2.1 `_Writer.source_table` maps a number to `stored_net_name(net)`; the unit test of the new scenario in `tests/unit/backends/kicad/test_pcb_write_nets.py`. Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_write_nets.py tests/kicad/board/test_net_forms.py -q`; `uv run pyright src`.
  - **2026-10-09.** Passed (the new test fails without the fix).
- [x] 2.2 `tests/corpus/test_board_write_own.py`: every readable non-heavy major-9 demo board is written for target 9, and the re-read model equals the source's apart from net numbers and opaque texts. Proof: `uv run pytest tests/corpus/test_board_write_own.py -q -n 2`.
  - **2026-10-09.** 20 passed (19 boards and the RoyalBlue teardrop test), 2 skipped (the two boards of major 10).

## 3. Oracle

- [x] 3.1 `tests/kicad/board/test_written_own_target.py`: the RoyalBlue board written for target 9 loads, and its DRC report equals the source's on the keys three runs per side repeat (`checks.rt2.compare_runs`). Proof: `FENOLITE_KICAD_CLI=docker:kicad/kicad:9.0.9 uv run pytest tests/kicad/board/test_written_own_target.py -q`.
  - **2026-10-09.** Passed three times on 9.0.9 (84 and 54 unstable keys of about 1 100 left out in the two runs that printed the count) and once on 10.0.6 (67). One exact comparison of single reports failed first: two DRC runs of the unchanged source differ by 22 to 52 entries (counted both ways, three samples), all clearances, so the stage-style judgement is the test.

## 4. Closing

- [x] 4.1 Run tests/residue. Proof: `uv run pytest tests/residue -q`.
  - **2026-10-09.** 37 passed, 1 skipped.
- [x] 4.2 Generators in check mode. Proof: `uv run python tools/gen_agent_guide.py --check`, `tools/gen_evidence_matrix.py --check`, `tools/gen_schemas.py --check`, `tools/gen_token_docs.py --check`.
  - **2026-10-09.** All four exit 0.
- [x] 4.3 `CHANGELOG.md` under `[Unreleased]`, `### Fixed`; `openspec/README.md` row. Proof: `make check-fast PYTEST_WORKERS=2`; `openspec validate --all --strict`.
  - **2026-10-09.** `make check-fast PYTEST_WORKERS=2`: 12963 passed, 29 skipped; `openspec validate --all --strict`: no error.
