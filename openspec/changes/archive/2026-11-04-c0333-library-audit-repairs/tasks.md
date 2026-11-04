## 1. Registry companion
- [x] 1.1 Verify preservation of all old digests and unchanged non-text rules; mirror the approved registry and pass the focused licence tests with a real library checkout.
## 2. Combined gates
- [x] 2.1 Pass accumulated local fast and exact-commit CI; retain the library release/audit gates until their independent proofs pass.

Proof: parsed non-text tables are identical and every old shipped text digest
is a subset of the synchronized registry. The library independently checks
the union against its older baseline. Registry bytes match exactly, SHA-256
5c7fb0314975e1bbfad5fa151a60b2fe1eb84623dcf657329b4b8d4b17190442.
`uv run pytest tests/unit/library/test_licences.py -q` with the real library
checkout selected passes13 tests, with no skipped copy-equality test.

Closed 2026-11-04: `make check-fast` passed on the batch (22620 passed, 51 skipped); every
required job of CI 41853235387 passed on the exact commit 0bce63e2 (unit on Linux 3.11/3.12/3.13, macOS
after a rerun of a runner-capacity cancellation, Windows; kicad-9, kicad-10, drawn-floor, routing
9/10, viewer, mcp, wheel, dco).
