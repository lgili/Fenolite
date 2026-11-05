## 1. Non-plated holes in the model-only pad geometry

- [x] 1.1 Authored regression: a design with an `np_thru_hole` pad of size 0 on `*.Cu` makes `check`
      fail with `FEN-1001` before the fix. `model_pads` gives that pad no copper and keeps the pad;
      a zero-size plated pad drops only the refused entry. Proof: `uv run pytest tests/unit/checks/test_padpath.py -q`.

## 2. Conversion without a PCB design

- [x] 2.1 Authored regression: an Altium project that declares a missing PcbDoc makes `convert --to kicad`
      exit 3 with `FEN-3001` naming the missing document, not `FEN-1001`. Proof: focused convert test.

## 3. Document names under a subfolder

- [x] 3.1 Authored regression: `parity` on an Altium project whose PcbDoc is in `PCB/` returns exit 0 or 5
      with `input.path` `PCB/<name>.PcbDoc` and its SHA-256. Proof: focused parity/documents test.

## 4. Explicitly empty part values

- [x] 4.1 `Part.value_empty`, `empty_value_ids`, `build_design(empty_values=)` from `fenolite build`; the
      KiCad build keeps the empty value; `value=None` still takes the symbol's Value; model unchanged.
      Proof: `uv run pytest tests/unit/dsl/test_value_empty.py -q`.
- [x] 4.2 The import emitter writes `value=""` for an empty source value (not for a board-only part); the
      import self-check of an authored board with such a part reports no `import.unequal`. Proof:
      focused importer test.

## 5. Close

- [x] 5.1 Docs (`docs/dsl.md`), `CHANGELOG.md`, generated surface and guide,
      `openspec validate c0364-import-board-failures --strict`, `make check-fast`.
      Done 2026-11-05. `make check-fast` scope: CI 41947475460 on 515ddc6a, `quality` and the five `unit`
      jobs passed; later commits of `cac/c0364-lote16`: focused tests passed and `openspec validate
      --strict` passed.
- [x] 5.2 Re-run the failing commands on the maintainer's private boards outside the repository and
      record the outcome per item (no private data in the repository). Outcome 2026-11-04: the 41 internal
      failures of the batch are gone (38 `check` runs complete, 24 with exit 0 and 14 with findings; 3
      conversions without their PcbDoc exit 3 with `FEN-3001` naming it); the board in progress gives
      `parity` and `check` results instead of `FEN-1001`, and its rebuilt empty values stay empty. Its full
      `import` self-check is blocked by the unrelated c0363 TAB refusal (proposed as c0379).

Status of 5.1: the first `make check-fast` run found 5 failures caused by this change (surface, part
attributes, field-order and approved model-shape tests); the design moved the flag out of the model and
the 5 tests, the touched areas on Python 3.11 (6 841 tests) and the openspec/residue/consistency tests
(1 112) pass. Closed on 2026-11-05 by CI 41947475460 (task 5.1).
