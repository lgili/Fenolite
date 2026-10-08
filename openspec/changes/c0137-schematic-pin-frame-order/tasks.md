## 0. Entry check

- [x] 0.1 Find every place that maps a pin's library offset to the sheet. Proof: `grep -rn "pin_point\|turned(\|label_angle(" src tests tools`; `design.md`, Context.
  - 2026-10-08: one transform, `schlayout.turned`, behind `pin_point` and `label_angle`; every caller (`schlayout` boxes, `schgen`, `sch._text_anchor`, `sch_netlist._pins`, the test helpers) goes through them. No copy.
- [x] 0.2 Look for the infra commit of the v0.4 notes. Proof: `git log origin/v04 --oneline | grep -i 39a3668`; `git log origin/v04 --oneline -S pin_point`.
  - 2026-10-08: no object `39a36681` in the clone; the infra commit near the schematic oracle on `origin/v04` is 7d8c0d0a (the docker form of `FENOLITE_KICAD_CLI` for the probe runner). It touches no pin point and is not needed here (`design.md`, Context).
- [x] 0.3 Measure the order on the corpus. Proof: `uv run python tools/corpus_fetch.py --uses sch` and `--uses sch-9`; a scratch script (not a product test) over the fetched sheets.
  - 2026-10-08: 132 and 92 items, 0 failed. 125 sheets read; 188 instances mirrored and turned by 90° or 270° (all `mirror x`): 142 touch more at the rotate-first points, 45 tie, 1 the other way (explained); 336 against 76 pin points; 20 sheets of both tags. Mirror axis at 0°: 1 943 against 336 (`design.md`, Measurement).

## 1. Facts and register

- [x] 1.1 The fact in `docs/formats/kicad/schematic.md` (`CORPUS-VERIFIED`, S-0058 with the corpus rows), the correction of the `H-K-SCH-PINFRAME` row there and in `docs/hypotheses.md`, the row `H-K-SCH-PINFRAME-ORDER`, the c0137 note of S-0058 in `docs/evidence/sources.md` and the probe table of `docs/evidence/kicad-schematic.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_evidence_register.py tests/unit/test_capability_evidence.py -q`.
  - 2026-10-08: passed with the gates of 4.1 (135 passed, 5 skipped).

## 2. The fix

- [x] 2.1 `schlayout.turned` rotates, then mirrors; docstrings of `turned`, `pin_point` and `PROVED_FRAMES`. Proof: `uv run pytest tests/unit/backends/kicad/test_pin_frame_order.py tests/unit/backends/kicad/test_schlayout.py -q`.
  - 2026-10-08: 50 passed after the one assertion of `test_schlayout.py` that held the old order (`pin_point(origin, left, 90, "y")`) was turned round.
- [x] 2.2 `sch_netlist.FRAME_ORDER_EVIDENCE`, `frame_evidence`, its use in `evidence_of` and in the build envelope. Proof: `uv run pytest tests/unit/backends/kicad/test_pin_frame_order.py -q`.
  - 2026-10-08: 34 passed: the twelve frames of `pin_point` and of `label_angle` by hand, the two orders differ only at the four mirrored quarter turns, the authored sheet of `tests/_pinframe.py` read back through the own netlist and its control, the evidence, and the blink with `U1` placed in five frames keeping its nets.
- [x] 2.3 Pinned builds and the KiCad backend tests unchanged. Proof: `uv run pytest tests/unit/backends/kicad tests/unit/lens/test_build_bytes_pinned.py tests/unit/lens/test_schplacements.py tests/unit/lens/test_build_schematic.py tests/unit/lens/test_build_netlist_guard.py -q -n 2 -m "not needs_kicad and not needs_corpus and not needs_libs"`; `git diff --stat origin/dev -- tests/data`.
  - 2026-10-08: 2442 passed, 1 skipped; `test_build_bytes_pinned.py` alone 83 passed; no pin moved and no file under `tests/data` changed (no pinned design and no golden places a unit mirrored).

## 3. Tests against KiCad

- [x] 3.1 `tests/kicad/schematic/test_stacked_corpus.py` without `left_out`. Proof: collected and skipped here (no `kicad-cli`); the candidates counted without `kicad-cli` with the test's own selection.
  - 2026-10-08: 49 skipped (`kicad-cli` not found) for 3.1 and 3.2 together. Candidates: `kicad-demo-10-0-6-sch-017` 10 before and 10 after, the same stacks; no other root project of 9 or 10 has one; `PINNED` unchanged.
- [x] 3.2 `tests/kicad/schematic/test_pin_frame_oracle.py` (`needs_kicad`) and the authored sheet `tests/_pinframe.py`. Proof: collected and skipped here; the sheet is read back by the unit tests of 2.2 for target 10.
- [ ] 3.3 `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/schematic/test_pin_frame_oracle.py -rA` on 9.0.9 and 10.0.6; then `H-K-SCH-PINFRAME-ORDER` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` and `FRAME_ORDER_EVIDENCE` follows. Owed: CI (kicad-9/kicad-10).
- [ ] 3.4 `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/schematic/test_stacked_corpus.py -rs` on 10.0.6 (and 9.0.9, where c0123's task 10.5 waits). Owed: CI (kicad-9/kicad-10).
- [ ] 3.5 `tests/kicad/schematic/test_naming_probes.py` and `tests/kicad/test_probe_results.py` on both majors: the `sch-pin-frame-*` outcomes stay `absent`. Owed: CI (kicad-9/kicad-10).

## 4. Documents and gates

- [x] 4.1 `docs/schematic.md` (placements file), `CHANGELOG.md`. Proof: `make check-fast`; every `uv run python tools/gen_*.py --check`; `uv run pytest tests/residue tests/corpus/test_manifest.py -q`; `openspec validate c0137-schematic-pin-frame-order --strict`.
  - 2026-10-08: `make check-fast` 9942 passed, 18 skipped (exit 0); the three `gen_*` tools exit 0 with `--check` (the matrix page regenerated for `FRAME_ORDER_EVIDENCE`); residue, manifest and the register tests 135 passed, 5 skipped; the change is valid (exit 0), its one note is that MODIFIED "Stacked pins of corpus sheets" waits for c0123's archive, and `validate --changes --strict` lists no error of it (its 5 known errors are those of c0084, c0085, c0086 and c0128).
- [ ] 4.2 `make check` on the rebased branch before the merge.
