## 1. Focused repair
- [x] 1.1 Reproduce the direct nested-device failure with authored records; add bounded manifest-based support discovery, prove acceptance and stale dependency detection, and retain invalid-manifest refusal.
- [x] 1.2 Run focused library review/check tests, lint/types and the private residue gate. Update the changelog.
## 2. Combined gates
- [x] 2.1 Pass the accumulated local fast gate and exact-commit CI before closing this change.

Proof: the authored nested direct-device test failed with exit5 before the
repair. After the repair, `uv run pytest tests/unit/cli/test_library_review.py
tests/unit/cli/test_library_check.py -q` passed33 tests, including repository
and vendored layouts, exact review, dependency staleness, missing/malformed/
mismatched/unlisted manifests and bounded ascent. Ruff check and format check
passed; pyright for the changed module reported zero errors/warnings.
The complete residue scan covered6478 files with zero hits and private gate on.
Combined fast/CI remain pending.

Closed 2026-11-04: `make check-fast` passed on the batch (22620 passed, 51 skipped); every
required job of CI 41853235387 passed on the exact commit 0bce63e2 (unit on Linux 3.11/3.12/3.13, macOS
after a rerun of a runner-capacity cancellation, Windows; kicad-9, kicad-10, drawn-floor, routing
9/10, viewer, mcp, wheel, dco).
