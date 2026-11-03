## 1. Registry companion
- [x] 1.1 Verify preservation of all old digests and unchanged non-text rules; mirror the approved registry and pass the focused licence tests with a real library checkout.
## 2. Combined gates
- [ ] 2.1 Pass accumulated local fast and exact-commit CI; retain the library release/audit gates until their independent proofs pass.

Proof: parsed non-text tables are identical and every old shipped text digest
is a subset of the synchronized registry. The library independently checks
the union against its older baseline. Registry bytes match exactly, SHA-256
5c7fb0314975e1bbfad5fa151a60b2fe1eb84623dcf657329b4b8d4b17190442.
`uv run pytest tests/unit/library/test_licences.py -q` with the real library
checkout selected passes13 tests, with no skipped copy-equality test.
