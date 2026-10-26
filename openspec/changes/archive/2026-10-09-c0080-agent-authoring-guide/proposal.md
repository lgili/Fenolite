## Why

The guide teaches an agent to run Fenolite, not to design a board with it. Its 131 lines (`agent/SKILL.md` at `9aba2dff`) hold the rules of the command line, a loop over a script that already exists, and one line each for the reading commands. Nothing says how to write that script: which parts exist, how a pin is named, where the origin is, how copper is scripted, where a fab's limits go, what to do with a finding. That knowledge is in `docs/dsl.md` (54 kB) and `docs/cli-contract.md` (154 kB), written as specifications for contributors and absent from the wheel.

The gap grew while this proposal waited. On 2026-10-05 the public surface was 13 commands and 38 names in `fenolite.dsl.__all__`; at `9aba2dff` it is 30 commands and 58 names, and the guide's one tested block runs nine of the commands.

The one recorded agent session of v0.1 (`docs/release/v0.1.md`, "Manual checks") started from the finished example. Nothing shows an agent going from a requirement to a board.

Recovery is untested as well. On 2026-10-05, `check` on a board with shorts returned twelve issues, each with an empty `hint`. Since then `fenolite explain CODE` (c0066) gives every code a meaning and a fix, but `checks/copper.py` still builds a `copper.short` finding without a hint at `9aba2dff`, and the guide's advice per exit code is prose that no test runs.

A hand-written guide also rots here: agents land changes daily, and nothing fails when a page names a flag that no longer exists.

## What Changes

- **Eleven written pages** under `src/fenolite/agent/skill/references/`, each short enough to read whole: `design-script`, `parts`, `footprints`, `placement`, `routing`, `rules`, `checks`, `files`, `fabrication`, `altium`, `recovery`. `fenolite guide <topic>` prints them (c0079).
- **Two generated pages**, `commands` and `dsl-reference`, written by `tools/gen_agent_guide.py` from `cli.describe` and the signatures of `fenolite.dsl`; `--check` fails on drift.
- **Every example runs.** A fenced block is a `fenolite-cmd` (parsed by the real parser), a `fenolite-design` (a complete script that a test builds with the catalog alone) or a `fenolite-recipe` (commands with the exit code each must give, run in a prepared sandbox). An untested block fails the suite.
- **Recovery recipes** for the exit codes 2 to 7, each one a test: missing `--confirm`, unknown lib id, script error, shorted copper, missing router, lossy refusal.
- **Coverage is enforced.** Every public command appears in a tested block, and every public DSL name is taught or listed with a reason in `DSL_NOT_TAUGHT`. A change that adds one must extend the guide; `AGENTS.md` says so.
- **Every public command has a page** (design, Decision 1): the schematic and assembly outputs, the comparison commands and the Altium verification kit, which did not exist when the page list was first written, are placed.
- **Page budgets**: at most 250 lines and 12 000 bytes per written page.

Milestone: v0.4 (the agent track). Size: 11 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `agent-guide` (created by c0079, which must be archived first): ADDED "Guide pages", "Executable blocks", "Recovery recipes", "Guide covers the public surface", "Generated guide pages", "Page budgets and writing rules".

None of the six names is a requirement of c0079 or of a living spec at `9aba2dff`. No requirement is modified.

## Non-goals

- No design-rule value from a standard or a fabricator: the pages show where the user's values go, and a number in an example is marked as an example.
- No electronics course: the pages teach Fenolite and what it can check.
- No copy of `docs/dsl.md` or `docs/cli-contract.md`, which stay the full references.
- No new command and no change to the DSL.
- No lines for commands that are not on `dev` when this change is implemented: each later change adds its own.
- No statement of its own about how far the Altium target is verified: the page `altium` repeats what `capabilities` reports.

## Evidence level required

- Blocks, coverage, budgets and generated pages: mechanical, proved by `tests/unit/agent/`.
- Design blocks: built hermetically for KiCad 9 and 10, and for the Altium target on the `altium` page. That page gives, per write kind, the status and the evidence level that `fenolite capabilities` reports (c0092), and a test compares the two.
- Whether the pages help an agent is measured by c0081, before and after this change.

## Prerequisites

- `0.3.0` is released from `dev` first: c0092 decides which Altium write kinds leave `experimental`, and the page `altium` is written against that.
- c0079 is archived (the pages are data of its loader) and c0077 is archived (design blocks build from the catalog and must pass the copper check).
- c0081's harness and its first batch come before this change, and its second batch after, so that the effect of the pages is measured.
- c0078 is optional: `fetch` gets its lines here only when c0078 is archived first; otherwise c0078 adds them.
- c0096, c0097 and c0099 (board authoring, implemented on their own branches): whichever side lands second pays. On `dev` before this change, this change covers them at task 0.1: `MechanicalIntent` (c0096) is a name of `fenolite.dsl.__all__` and needs a design block or a `DSL_NOT_TAUGHT` row; `place --strategy constrained|manual` (c0096) needs a line in `placement`; the recipe `crossed` is re-measured on the `copper.short` finding as c0097 reports it. Landing after this change, each of the three adds its own line, and the coverage test tells it so.
- The other proposals of v0.4 land in their own order; c0108, c0111 and c0120 already carry a guide task "if c0080 is archived".

## Impact

- New: thirteen files under `src/fenolite/agent/skill/references/`, `tools/gen_agent_guide.py`, `tests/unit/agent/test_pages.py`, `test_recipes.py`, `_sandbox.py`.
- Changed: `src/fenolite/agent/skill/SKILL.md` (the index of pages; the section on small questions becomes tested blocks), `src/fenolite/agent/guide.py`, `AGENTS.md`, `CONTRIBUTING.md`, `Makefile`.
- Every later change that adds a public command, a public DSL name or a `FEN-` code gains one obligation: a tested line in a page.
- No error code, no issue code, no model key, no source id and no hypothesis is new. Nothing changes in a build, for KiCad or for Altium.
