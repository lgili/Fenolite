# tests/unit

Hermetic unit tests: no network, no external tools, no corpus. Mirror the package layout
(`tests/unit/core/`, `tests/unit/model/`, `tests/unit/cli/`) and keep repository-invariant tests
(`test_pyproject_invariants.py`, `test_spdx_headers.py`, …) at this level.
