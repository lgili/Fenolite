## Context

- **Request.** The maintainer asked on 2026-10-24 that the agent guide teach an agent to build a sound board, not only to drive the commands. The material is the maintainer's design practice, written as general rules. The cases on the pages are described without any design's names or values.
- **What exists.** The guide has thirteen pages: the start page, eleven written tool pages, and two generated pages (capability `agent-guide`). The skill folder held 148 420 bytes on `release-0.5.0` at `a979b412`, against a budget of 150 000. There is no room for one more page.
- **What Fenolite already answers.** Several of the practice questions map onto existing commands:
  - `analyze` measures current capacity, power paths, clearance, creepage, grooves and insulation between layers;
  - `net` lists a net's copper and its open connections;
  - `neighbors`, `region` and `pads` show what is where;
  - `testpoints` reports test access and fiducials;
  - `ready` gives the electrical readiness;
  - `check` judges rules.

  The pages call these commands. They do not describe a command that does not exist. The missing tools are c0175.

## Goals / Non-Goals

**Goals**
- An agent that reads `board-practice` before placement knows the order of work, what no check sees, and where each number comes from.
- Each practice page gives rules, the failure each rule prevents, and a way to check the rule, preferably a Fenolite command.
- The pages pass the same tests as the tool pages: budgets, forbidden forms, tested command lines, and `Read next:`.

**Non-Goals**
- See the proposal. In particular, there are no limit values and no claims about compliance.

## Decisions

1. **Eleven pages, prefixed `board-`.** The prefix keeps the practice pages together in the index, and apart from the tool pages of the same subject (`placement` against `board-floorplan`, `routing` against `board-routing`). The topics are:
   - `board-practice`, the hub;
   - `board-schematic`, `board-floorplan`, `board-power`, `board-grounds`, `board-insulation`, `board-emc`, `board-routing` and `board-assembly`, the areas;
   - `board-review` and `board-workflow`, the process.

   One page per area keeps each page under the 12 000-byte budget and readable at once.
2. **Practice is stated as practice.** The tool pages state only what Fenolite does. A practice page states practice, and names a command only where the command answers the question. The requirement "Page budgets and writing rules" now says so, in place of "state only what Fenolite does" for every page.
3. **Numbers.**
   - A practice page names public methods (IEC 60664-1, IPC-2152, IPC-7351) and their inputs. It gives no value from their tables: the writing rule already forbids naming a standard's table.
   - The figures in command lines (a temperature rise, a groove width, a coverage) are marked as examples in the sentence that follows the block.
4. **Cases.**
   - Each page ends with "Typical failures": two to four short cases, each a fault that happened and how it was fixed, without any design's names, nets, values or coordinates.
   - The cases teach better than rules alone, because they show what the failure looks like when it happens.
   - The text names no organisation, no product and no person, and the residue scan guards that.
5. **The start page.** A section "Designing a good board", of two lines of prose, sends the agent to `board-practice` before placement. The page stays under 200 lines (198 after the index grows by eleven lines).
6. **The budget.**
   - The folder budget rises from 150 000 to 260 000 bytes. The eleven pages add about 85 000 bytes (the folder holds 235 473 bytes with them), and the rest is margin for the lines that c0175 will add.
   - A page is read on demand, so the folder size is not the size of an agent's context. The per-page budgets stay as they are: 250 lines and 12 000 bytes for a written page, 600 lines for a generated page, and fewer than 200 lines for the start page.
7. **Tests.**
   - `tests/unit/agent/test_pages.py` splits its written topics into `TOOLS` and `PRACTICE`. `HOME` gives the practice topics no home command, so none of them becomes the home of a public command.
   - `TEACHES` lists, for each practice page, the words that "Guide pages" requires of it.
   - Two scenarios are added: the start page's section, and a practice page through the command line.

## Risks / Trade-offs

- **The practice can become stale or wrong.** Mitigation: every rule says why it holds, so a reviewer can judge it. The pages give no limits, so a wrong page cannot set a wrong limit.
- **An agent may take an example figure as a limit.** Mitigation: each figure on a page is followed by "examples", and `board-practice` says where the numbers come from.
- **The folder grows.** Mitigation: the per-page budgets hold, and the folder budget is a test.

## Evidence

The pages are prose. Their fenced blocks are proved by the existing suites:
- each `fenolite-cmd` line parses with the real parser;
- the start page's index equals the generated one;
- the budgets hold.

No evidence label of any capability changes.
