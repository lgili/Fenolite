## 0. Establish scope

- [x] 0.1 Read the exact `613b6f1b` strict census and c0277/c0278/c0281 contracts; record the six
  observations, the single omission class, file ownership and bounded decision before code.
  Proof: `npx -y @fission-ai/openspec validate c0317-import-edge-fields --strict`.
  Done 2026-11-01: the actual log and SHA-declared cache confirm one uniform-width omission class
  across six rows; the scope and ownership are recorded in design.md. Strict validation passed.

## 1. Represent and write the width

- [x] 1.1 Add optional validated DSL/model outline width and KiCad writing while retaining default
  bytes. Prove zero/nonnegative lengths, invalid inputs, line/arc/cut-out output and model defaults.
  Proof: `uv run pytest tests/unit/dsl/test_outline_width.py tests/unit/dsl/test_outline_paths.py -q`.
  Done 2026-11-01: 35 passed, including target-9/10 lines, arcs, cut-outs, slots and explicit zero;
  default canonical metadata is absent and invalid inputs leave the declaration unchanged.
- [x] 1.2 Make explicit width changes participate in the existing outline rebuild decision without
  changing the default or hand-edited geometry policy.
  Proof: `uv run pytest tests/unit/dsl/test_outline_width.py tests/unit/backends/kicad/test_outline_merge.py tests/unit/lens/test_preserve_outline.py -q`.
  Done 2026-11-01: 34 passed, including an actual build-change-build round trip with exact stable
  bytes afterward; existing signed/locked/hand-edited outline policy cases remain green.

## 2. Emit supported source strokes

- [x] 2.1 Emit a uniform supported root width; preserve mixed/invalid and unrelated refusal accounting.
  Add authored strict import/build/verify, footprint-edge and determinism regressions.
  Proof: `uv run pytest tests/unit/importer/test_outline_width.py tests/unit/importer/test_unexpressed_c0281.py tests/unit/importer/test_notched.py -q`.
  Done 2026-11-01: 9 passed. The authored native line/arc project is equal at all 1–8+S levels with
  no accepted differences; mixed/negative widths refuse without writes, imports are deterministic,
  and the original opaque footprint-edge stroke is retained exactly.
- [x] 2.2 Run focused existing import coverage/default-byte compatibility and cached six-row measurement;
  record current outcomes with the exact source while retaining historical census/ratchets.
  Proof: `uv run pytest tests/unit/importer/test_coverage.py tests/unit/importer/test_import_coverage_measurement.py tests/unit/test_build_bytes.py -q`.
  Local compatibility proof passed (83); all pinned example bytes remain unchanged. The cached
  measurements follow the signed source checkpoint so their source binding is exact.
  Done 2026-11-01: strict six-row measurement on signed `888ca838fa41b1b9bc16e4039ec55e233400b1e5`
  failed all six in 232.69s: no width refusal remains, one import self-check rejects repeated-sheet
  footprint variants, five comparisons differ. Actual counts/statuses are recorded in
  docs/evidence/fidelity.md; no acceptance, ratchet change or passing corpus claim follows.
- [x] 2.3 Refresh all 18 current raw-board emission observations on that signed source using the existing
  tool, including heavy rows; retain the historical full-conversion table and verify an affected raw row.
  Proof: `uv run python tools/measure_import_coverage.py --cache <cache> --date 2026-11-01 --write`;
  `uv run pytest tests/unit/importer/test_import_coverage_measurement.py 'tests/corpus/test_import_corpus.py::test_demo_board_imports_equivalent[08]' -q`.
  Done 2026-11-01: the existing tool completed all 18 rows, including heavy 06/18, on signed
  `888ca838fa41b1b9bc16e4039ec55e233400b1e5`. Metadata and the unchanged raw-row import test pass
  (6). Every input SHA and item count is unchanged; 12 rows remove only represented `outline-width`
  findings. Generated collection digest is `9dd2b6855dcefd29d769dbf003ea6ec218183f5f95a403b78dbb02feb12e6ea1`.
  This verifies current emission accounting and the existing raw import assertion, not all-level
  fidelity. The historical full-conversion table and strict six-row failure verdict remain intact.

## 3. Teach the field

- [x] 3.1 Document uniform width preservation and the strict mixed-width limit; add a tested guide line
  and regenerate command/DSL/model schema references.
  Proof: `uv run pytest tests/unit/agent/test_pages.py tests/unit/test_schema_drift.py -q`; `uv run python tools/gen_agent_guide.py --check`; `uv run python tools/gen_schemas.py --check`.
  Done 2026-11-01: 113 passed; generated guide/schema checks pass. The written design-script page
  is 11973 bytes/243 lines, including the executed `outline_width=` example and tested term.

## 4. Closing proofs

- [ ] 4.1 Run focused tests, lint, format, source types and residue; leave whole-batch and exact CI open
  until the coordinator's actual proof.
  Proof: `uv run ruff check .`; `uv run ruff format --check .`; `uv run pyright src`; `uv run python tools/residue/scan.py`; `make check-fast`; exact-head CI unit/KiCad 9.0.9/10.0.6 jobs green.
  Local portion passed: ruff, format (3174 files), source types (0 errors/warnings), residue (0 hits;
  16 existing waivers, none added), focused import/DSL/rebuild/default-byte/guide/schema proofs above.
  The literal whole-batch and exact CI clauses remain coordinator-owned and unproved here.
- [x] 4.2 Record source-bound results and retain truthful evidence labels and native/full-CI limitations.
  Proof: `uv run pytest tests/unit/test_fidelity_docs.py tests/fidelity/test_corpus_contract.py -q`; `npx -y @fission-ai/openspec validate c0317-import-edge-fields --strict`.
  Done 2026-11-01: metadata/contract tests pass (12) and strict validation passes. The scoped actual
  six-row failure table names the exact signed source, all raw counts/statuses and skipped levels;
  historical observations/ratchets remain unchanged. No accepted or native/CI verdict is promoted.
- [x] 4.3 Add one Unreleased changelog entry and review the final diff.
  Proof: `git diff --check`; `npx -y @fission-ai/openspec validate c0317-import-edge-fields --strict`.
  Done 2026-11-01: one c0317 entry is present; source and proof diffs preserve the old defaults,
  historical evidence, remaining refusals and unaccepted corpus failures. Diff and strict checks pass.
