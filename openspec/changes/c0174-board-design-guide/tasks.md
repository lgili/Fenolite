## 0. Entry check

- [x] 0.1 Read the living `agent-guide` spec and `tests/unit/agent/test_pages.py`. Write under this task the folder size, the page budgets in force, and whether another open change holds a delta of "Guide pages", "Start page" or "Page budgets and writing rules". Proof: `openspec validate c0174-board-design-guide --strict --no-interactive` passes.
  - 2026-10-24:
    - On `release-0.5.0` at `a979b412`, the skill folder holds 148 420 bytes against a budget of 150 000.
    - The budgets are 250 lines and 12 000 bytes for a written page, 600 lines for a generated page, and fewer than 200 lines for the start page (182 lines).
    - No open change (c0092, c0105, c0146, c0160, c0166, c0168, c0170 to c0173) holds a delta of those three requirements.

## 1. Pages

- [x] 1.1 Write `board-practice` and the start page's section "Designing a good board", and regenerate the index. Proof: `uv run python tools/gen_agent_guide.py --check`; `uv run pytest tests/unit/agent/test_pages.py -k "practice or index" -q`.
- [x] 1.2 Write `board-schematic`, `board-floorplan`, `board-power` and `board-grounds`. Proof: `uv run pytest tests/unit/agent/test_pages.py -k "topics or cmd or writing or budget" -q`.
- [x] 1.3 Write `board-insulation`, `board-emc` and `board-routing`. Proof: as 1.2.
- [x] 1.4 Write `board-assembly`, `board-review` and `board-workflow`. Proof: as 1.2.
- [x] 1.5 Split `WRITTEN` into `TOOLS` and `PRACTICE`, give the practice topics their `TEACHES` words and no `HOME` command, raise `FOLDER_BYTES` to 260 000, and add the scenarios "The start page sends the agent to the practice pages" and "A practice page through the command line". Proof: `uv run pytest tests/unit/agent/ tests/unit/test_agent_skill.py -q`.
- [x] 1.6 Name the practice pages in `README.md`, beside the loop. Proof: `uv run pytest tests/unit/test_agent_skill.py tests/unit/test_examples.py tests/unit/test_repo_layout.py -q` (the tests that read `README.md`).
  - 2026-10-24: proof passed (37 tests).

## 2. Closing

- [x] 2.1 Run the fast gate and the residue scan. Proof: `make check-fast`.
  - 2026-10-24, macOS: lint, format, pyright and residue clean (0 hits in 3 774 files); tests 13 769 passed, 73 skipped, 1 failed. The failure, `tests/unit/lens/test_altium_pcb_complete.py::test_altium_samples_of_earlier_changes_keep_their_bytes`, fails the same way on a clean worktree of `origin/release-0.5.0` (`a979b412`) without this change; it is not caused by it. The full gate is left to CI, as `AGENTS.md` asks.
- [x] 2.2 Evidence labels: none changes. The pages are prose, and their blocks are proved by the suites named in the design. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-24: proof passed.
- [ ] 2.3 Add an entry under `## [Unreleased]` in `CHANGELOG.md`. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-24: WAITS on the maintainer. The package version is still `0.5.0`, and the guard of the release record (`test_release_record_v05.py`, "Versions agree") keeps `[Unreleased]` empty at that version. This change is not part of 0.5.0. The entry is written when the maintainer opens the next version. Its text is ready:
    `- **Practice pages in the agent guide** (c0174): eleven written pages, from `board-practice` to `board-workflow`, teach the order of work, what no check sees, the schematic and part ratings, power paths, grounds and ties, clearance and creepage, EMC and protection, routing style, assembly marks, the review, and working on files a person also edits; the start page sends an agent to them before placement, and the skill folder's budget is 260 000 bytes.`
