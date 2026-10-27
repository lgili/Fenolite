## 1. File safety

- [x] 1.1 Add `fenolite snapshot` with the companions and the stable read (scenario "A file saved during the copy"). Proof: `uv run pytest tests/unit/safety/test_snapshot.py -q`.
  - 2026-10-26: proof passed (7 tests).
- [x] 1.2 Add `fenolite publish` (scenario "The owner saved one file"). Proof: `uv run pytest tests/unit/safety/test_publish.py -q`.
  - 2026-10-26: proof passed (3 tests: the scenario with and without `--skip-changed`, a write's envelope as the next receipt, a malformed receipt).
- [x] 1.3 Register KiCad's lock file with its public source; add `safety.open-session` in the dispatcher and `fenolite doctor --sessions` (scenario "A board open in KiCad"). Proof: `uv run pytest tests/unit/safety/test_sessions.py tests/unit/test_provenance.py -q`.
  - 2026-10-26: proof passed. The sources are S-0828 and S-0829; `H-K-PRO-LOCK` waits for a session of the maintainer.
- [x] 1.4 Recognise online-only files by their documented attributes, and add `FEN-3007` (scenario "A file kept only online"). Proof: `uv run pytest tests/unit/safety/test_placeholders.py -q`.
  - 2026-10-26: proof passed (7 tests, the macOS stdlib check skipped elsewhere).
- [x] 1.5 Add `fenolite refs` with `--repoint` for KiCad documents (scenario "A copied project still points at the old folder"). Proof: `uv run pytest tests/unit/safety/test_refs.py -q`.
  - 2026-10-26: proof passed (5 tests).
- [x] 1.6 Document and teach: `docs/file-safety.md`, `docs/cli-contract.md`, `explain.toml`, the guide's `files` and `recovery` pages; `make check-fast`, CHANGELOG, CI on the pushed commit. Proof: `uv run pytest tests/unit/agent tests/unit/cli/test_explain_cmd.py tests/consistency -q`, `make check-fast`, and the required jobs green on the head of `c0201-file-safety`.
  - 2026-10-27: the guide and contract tests passed (528 passed, 27 skipped); `make check-fast` passed (14,096 passed, 38 skipped). CI on the pushed head is recorded below.
  - 2026-10-27: CI run 40425171691 on `df13945`: every job green.
