## 0. Scope and reproduce

- [x] 0.1 Record the exact CI failure and all test-shaped example/data roles; choose the minimal boundary.
  Proof: `npx -y @fission-ai/openspec validate c0322-fixture-collection --strict`.
  Done 2026-11-01: all three files and their manifest/runner roles reviewed. Only the one exact
  test-data payload belongs in collect_ignore; example files remain unchanged. Strict validation passes.
- [x] 0.2 Add the real subprocess collection/bytecode, explicit runner and manifest controls; record the
  collection regression failing before the policy fix with bytecode genuinely enabled.
  Proof: `uv run pytest tests/unit/test_fixture_collection.py -q` on the old policy, then the fixed policy.
  Before policy fix, Python 3.12.14: 1 failed, 2 passed in 6.19s. The failure records actual collection
  and fixture-local pytest bytecode, while ordinary neighboring bytecode controls, runner execution
  and unchanged manifest rejection are active. No bytecode-suppression flag is used in subprocesses.
  The frozen old policy is also reproduced on Python 3.13.5 / pytest 9.1.1 with bytecode enabled:
  it creates `test_divider.cpython-313-pytest-9.1.1.pyc` and fails the collection control.

## 1. Preserve the collection and execution contracts

- [x] 1.1 Exclude only the fixture self-test file through the repository conftest. Prove real Python
  3.12/3.13 collection, ordinary bytecode generation, explicit runner execution and strict cache rejection.
  Proof: `env -u PYTHONDONTWRITEBYTECODE -u PYTHONPYCACHEPREFIX .venv/bin/pytest tests/unit/test_fixture_collection.py tests/unit/blocks/test_runner.py tests/corpus/test_manifest.py::test_committed_data_files_are_declared_and_embeddable tests/unit/testing/test_example.py -q`, then the same command with `.venv313/bin/pytest`.
  Done 2026-11-01: 25 passed in 15.62s on Python 3.12.14 and 25 passed in 14.49s on Python 3.13.5.
  Ordinary/neighbor caches are required positive controls. Payload collection/cache creation stops,
  actual block self-tests still pass and observe a planted failure, and the unmodified validator
  still rejects a separately injected `.pyc`. The original two failing CI assertions are included.

## 2. Close the local proof

- [x] 2.1 Run focused checks, lint, format, types, residue and strict validation; retain complete-gate/CI scope.
  Proof: `uv run ruff check .`; `uv run ruff format --check .`; `uv run pyright src`; `uv run python tools/residue/scan.py`; `npx -y @fission-ai/openspec validate c0322-fixture-collection --strict`.
- [x] 2.2 Record exact Python versions, bytecode-enabled witnesses and the remaining CI/native limits.
  Proof: the two focused receipts of task 1.1 and strict validation.
  Done 2026-11-01: both local interpreters and the enabled-bytecode negative/positive controls are
  recorded above. The 3.13 offline environment contains the required pytest/xdist/core packages;
  no Hypothesis-dependent case is selected. No full, native or exact-head CI pass is claimed.
- [x] 2.3 Add one Unreleased changelog entry and review the final diff.
  Proof: `git diff --check`; `npx -y @fission-ai/openspec validate c0322-fixture-collection --strict`.
- [ ] 2.4 Coordinator: repeat the complete gate and required CI on the exact published source.
  Proof: complete `make check-fast` and exact-head required GitHub CI jobs succeed.
