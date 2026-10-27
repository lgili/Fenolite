## 0. Entry check

- [x] 0.1 Move package 2 from c0175 (its decision 2, its two ADDED requirements and its tasks 2.1 to 2.3) into this change, and note the move in c0175's `tasks.md`. Proof: `openspec validate c0198-ground-ties --strict --no-interactive` and `openspec validate c0175-board-engineering-tools --strict --no-interactive`.

## 1. Ground ties

- [x] 1.1 Add `analysis/ties.py`: the copper graph, removal by ids, the groups, `analysis.tie-parallel`, `analysis.tie-extra`, `analysis.tie-dangling` and `analysis.tie-unmatched` (scenarios of "Ground ties"). Proof: `uv run pytest tests/unit/analysis/test_ties.py -q`.
  - 2026-10-26: proof passed (12 tests). The benches are authored in `tests/_groundties.py`. The dangling case uses a stub inside one pour: `t2` really is the only joint of `Q2-1`, so it splits.
- [x] 1.2 Add `--sense` and the kind `domains` (scenarios of "Sense nets and isolation islands"). Proof: `uv run pytest tests/unit/analysis/test_ties.py -k "sense or islands" -q`.
  - 2026-10-26: proof passed (3 tests: a sense track that starts on the pour, a sense pad through the shunt's net-tie group, the islands across `U5`).
- [x] 1.3 Add the five codes to the table (scenario "Tie codes in the table"). Proof: `uv run pytest tests/unit/analysis/test_findings.py -q`.
  - 2026-10-26: proof passed (14 tests). `fenolite explain` gains an entry per code (`tests/unit/cli/test_explain_cmd.py` requires one).
- [x] 1.4 Wire `--kinds ties,domains` and their options into `analyze`; document the kinds and the codes in `docs/analyses.md` and `docs/cli-contract.md`; regenerate the agent guide. Proof: `uv run pytest tests/unit/cli/test_analyze_ties.py tests/unit/cli/test_analyze_cmd.py tests/consistency tests/unit/agent -q`.
  - 2026-10-26: proof passed (534 passed, 24 skipped). The benches are written as KiCad boards and read back, and `--tie-item` takes the track's KiCad uuid. `board-grounds.md` of the agent guide teaches the kinds.
- [x] 1.5 `make check-fast`, CHANGELOG, and CI on the pushed commit. Proof: `make check-fast` and the required jobs green on the head of `c0198-ground-ties`.
  - 2026-10-26: `make check-fast` passed (14,008 passed, 34 skipped). CI run 40355527379 on `aaea7b4`: all 13 jobs green (unit on 5 combinations, kicad-9, kicad-10, both routing jobs, viewer, wheel, dco).
