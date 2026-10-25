## 1. Trigger

- [x] 1.1 Filter the push trigger of `ci.yml` and add the check (scenarios "Trigger checked" and "Tags run
  nothing"). Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`.
  - 2026-10-25: proof passed (40 tests).

## 2. Closing

- [x] 2.1 `CHANGELOG.md` under `### Changed` of `[0.5.0]` (the guard of v0.5 keeps `[Unreleased]` empty), the
  row in `docs/release/v0.5.md`, `openspec/README.md`. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-25: proof passed, with task 2.2 ticked after its proof.
- [x] 2.2 `make check-fast`. Proof: `make check-fast`.
  - 2026-10-25: 13 975 passed, 34 skipped; the one failure was the guard of v0.5 naming this open task, which
    passes once it is ticked (`uv run pytest tests/unit/test_release_record_v05.py -q`).
