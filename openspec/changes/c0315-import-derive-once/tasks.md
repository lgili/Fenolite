## 0. Entry

- [x] 0.1 Inspect derive/vendor and record decisions. Proof:
  `npx -y @fission-ai/openspec validate c0315-import-derive-once --strict`.
  2026-11-01: implementation inspected, decisions recorded, strict validation valid without warnings.

## 1. Signature work

- [x] 1.1 Add the authored multi-variant bound regression, reuse each comparison
  signature, and preserve current derivation/vendor expectations. Proof:
  `uv run pytest tests/unit/library/test_derive.py tests/unit/importer/test_vendor.py -q`.
  Passed 2026-11-01: nine focused tests. The authored stress fixture failed before the
  change with 80 serializations for fourteen instances; its byte digests already matched.
  After reuse it meets the fourteen-call bound for both targets with the same native
  byte digests, thirteen variants, duplicate membership and eleven expected diagnostics.

## 2. Validation

- [x] 2.1 Update the one Unreleased entry and run static, residue and strict checks.
  Proof: `uv run ruff check .`; `uv run ruff format --check .`;
  `uv run pyright src`; `uv run pytest tests/residue -q`;
  `npx -y @fission-ai/openspec validate c0315-import-derive-once --strict`.
  Passed 2026-11-01: lint/format clean; source types zero errors/warnings; residue tests
  38 passed, five missing-corpus skips; strict OpenSpec valid without warnings.
- [ ] 2.2 Confirm the serialized larger-batch fast gate and exact-head required CI.
  Proof: `make check-fast` and required jobs green on the published batch commit.
