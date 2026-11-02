## 0. Entry

- [x] 0.1 Record the public Windows failure and bounded cleanup decision.
  Proof: `npx -y @fission-ai/openspec validate c0321-block-temp-cleanup --strict`.

## 1. Cleanup lifetime

- [x] 1.1 Reproduce both cleanup paths with an actual temporary tree and a
  Windows-style active-directory deletion guard, then fix context exit order.
  Proof: `uv run pytest tests/unit/blocks/test_runner.py -q`.
- [x] 1.2 Prove the actual shipped block command and neighboring test APIs,
  retaining golden/native outputs and isolation guarantees.
  Proof: `uv run fenolite blocks test --json`;
  `uv run pytest tests/unit/cli/test_blocks_test.py tests/unit/blocks/test_starter.py tests/unit/testing/test_load.py -q`.

## 2. Validation

- [x] 2.1 Update the single Unreleased entry; run styles, types, residue and strict.
  Proof: `uv run ruff check .`; `uv run ruff format --check .`;
  `uv run pyright src`; `uv run python tools/residue/scan.py`;
  `npx -y @fission-ai/openspec validate c0321-block-temp-cleanup --strict`.
- [ ] 2.2 Publish the repaired batch and confirm the Windows shipped-block step
  and required jobs on the exact commit.
  Proof: exact published-head Windows and required GitHub CI jobs pass.
