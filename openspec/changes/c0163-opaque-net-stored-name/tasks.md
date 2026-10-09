## 0. Investigation

- [x] 0.1 Reproduce the refusal on the cached `kicad-demo-10-0-6-pcb-13` (`uv run python tools/corpus_fetch.py --only kicad-demo-10-0-6-pcb-13`), with its codes, constructs and locators, and find the root cause. Proof: `design.md`, Context.
  - **2026-10-09.** On `origin/dev` 833eefa: four `kicad.board.opaque-net-ref` errors for target 9 on teardrop zones 179, 180, 181 and 192; the source map of `write_board` gives model names, the target-9 numbering stored names.
- [ ] 0.2 Census: `write_board` for the own major and for 10 over every cached `.kicad_pcb` row of major 9 or 10, before and after the fix; the target-10 texts of the other rows compared byte for byte. Proof: the counts in this task's note.

## 1. Facts first

- [ ] 1.1 A fact row in `docs/formats/kicad/board.md` (the teardrops of the demo board reference nets stored with `{slash}` by number, `CORPUS-VERIFIED`, S-0058) and the writer's "Net forms" bullet (the stored spelling). Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py -q`.

## 2. Writer

- [ ] 2.1 `_Writer.source_table` maps a number to `stored_net_name(net)`; the unit test of the new scenario in `tests/unit/backends/kicad/test_pcb_write_nets.py`. Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_write_nets.py tests/kicad/board/test_net_forms.py -q`; `uv run pyright src`.
- [ ] 2.2 `tests/corpus/test_board_write_own.py`: every readable non-heavy major-9 demo board is written for target 9, and the re-read model equals the source's apart from net numbers and opaque texts. Proof: `uv run pytest tests/corpus/test_board_write_own.py -q -n 2`.

## 3. Oracle

- [ ] 3.1 `tests/kicad/board/test_written_own_target.py`: the RoyalBlue board written for target 9 loads, and its DRC counts per type equal the source's. Proof: `FENOLITE_KICAD_CLI=docker:kicad/kicad:9.0.9 uv run pytest tests/kicad/board/test_written_own_target.py -q`.

## 4. Closing

- [ ] 4.1 Run tests/residue. Proof: `uv run pytest tests/residue -q`.
- [ ] 4.2 Generators in check mode. Proof: `uv run python tools/gen_evidence_matrix.py --check` and the other generators of `make check-fast`.
- [ ] 4.3 `CHANGELOG.md` under `[Unreleased]`, `### Fixed`; `openspec/README.md` row. Proof: `make check-fast PYTEST_WORKERS=2`; `openspec validate --all --strict`.
