## 1. Generated page

- [x] 1.1 Measure the folder, each page and each section of `commands.md`. Proof: the figures in `design.md`.
  - 2026-10-25: 148 731 bytes on `c0184-visual-diff`; `commands.md` 34 056, of which 5 417 in usage lines.
- [x] 1.2 Short usage lines, placeholders on the argument lines, no repeated facts (scenario "The page
  commands is compact"). Proof: `uv run python tools/gen_agent_guide.py && uv run pytest tests/unit/agent -q`.
  - 2026-10-25: proof passed; `commands.md` holds 29 433 bytes and the folder 144 108 (5 892 under the budget).

## 2. Closing

- [x] 2.1 `make check-fast`. Proof: `make check-fast`.
  - 2026-10-25: proof passed. No `CHANGELOG.md` entry: at version 0.5.0 `tests/unit/test_release_record_v05.py`
    requires `[Unreleased]` to be empty, as for c0176 to c0184; the entry goes in with the next release record.
