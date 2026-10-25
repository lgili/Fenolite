## Why

The maintainer's request of 2026-10-24: the agent guide teaches an agent to drive Fenolite, not to design a board that a reviewer accepts. An agent that runs the loop until `fenolite check` exits 0 can still hand over a bad board, because no rule check sees the faults that matter most: a power loop drawn around half the board, a ground tied in three places, a sense pair that carries the power current, high-voltage copper hidden under a part, a silkscreen that no one can read, or a CAD file overwritten while a person had it open. The maintainer's own board work showed that these faults recur whenever an agent places and routes "until it passes".

## What Changes

- **Eleven practice pages in the agent guide** (`src/fenolite/agent/skill/references/`):
  - `board-practice`: the hub, with the order of work and what a check cannot see;
  - `board-schematic`, `board-floorplan`, `board-power`, `board-grounds`, `board-insulation`, `board-emc`, `board-routing`, `board-assembly`: one area of design each;
  - `board-review`: the self-review before a board is handed over;
  - `board-workflow`: how to work on CAD files that a person also edits.
- **What each page holds:**
  - rules, the failure that each rule prevents, and a typical case written without any design's values;
  - how to check the rule, with the Fenolite command that answers when one exists (`analyze`, `net`, `neighbors`, `region`, `pads`, `testpoints`, `ready`, `check`).
- **The start page** gains a short section, "Designing a good board", that sends an agent to `board-practice` before it places a part.
- **README** names the practice pages beside the loop.

## Capabilities

### Modified Capabilities

- `agent-guide`:
  - MODIFIED "Guide pages": eleven more written topics, with what each must teach;
  - MODIFIED "Start page": the pointer to `board-practice`;
  - MODIFIED "Page budgets and writing rules":
    - a practice page states practice, not features;
    - a number on it is marked as an example or named as an input of a public standard;
    - the folder budget rises from 150 000 to 260 000 bytes;
    - the per-page budgets do not change.

## Non-goals

- **No new command, DSL name or check.** The tools that the pages show to be missing are proposed in c0175.
- **No limit values.** No clearance, creepage, current, width or spacing figure is given as a requirement. The user's standard, the product's insulation coordination and the fabricator decide those.
- **No compliance claim.** The pages teach how to measure and review. They never say that a board complies, and never call a board verified without an evidence label.
- **No organisation named.** No company, product, internal standard, standard table, template, library house style or person is named.

## Evidence level required

- **The pages are prose.** No behaviour of Fenolite changes, so no evidence label changes.
- **Every fenced block on the new pages is proved by the existing suites** (`tests/unit/agent/test_pages.py`, `test_recipes.py`):
  - each `fenolite-cmd` line parses with the real parser;
  - each `fenolite explain` code exists;
  - each `fenolite-design` block builds with no tool.
- **Where a page states what Fenolite measures, it names the evidence level that the command reports.** It never claims more than that level.

## Impact

- **New:** `src/fenolite/agent/skill/references/board-*.md` (eleven pages).
- **Changed:**
  - `src/fenolite/agent/skill/SKILL.md` (the section and the index);
  - `tests/unit/agent/test_pages.py` (the topic lists, the words each page teaches, the folder budget);
  - `README.md`;
  - `CHANGELOG.md`.
- **Size:** 3 design-days. The change depends on no open change.
