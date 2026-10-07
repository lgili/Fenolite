## Context

- **The decision** is the maintainer's, of 2026-10-07 (proposal). This change writes it into the pages that are still open. It is based on commit `17234727`.
- **What the tree holds on that base.** Archived: c0039–c0047 (the read part), c0032–c0038, c0048, c0053, c0055 and c0056 (writers pulled forward), c0089 and c0122. Open on `dev`: c0083 to c0088, c0090, c0091, c0092, c0121, c0124 to c0128, c0130 and c0131; of these c0092, c0121 and c0126 have no task ticked. Not a folder on `dev`: c0123 and c0132 (each a folder on its own branch, `c0123-multi-pad-pin-map` and `c0132-altium-via-inner-pads`), c0134 (its branch holds no folder and no commit after the base) and c0129 (reserved).
- **The three groups of v0.4**, read with `git ls-tree --name-only <branch> openspec/changes/` on 2026-10-07: c0077–c0081 on `claude/onde-paramos-40a5cd` at `d6ed3651`; c0096 on `codex/c0096-constrained-placement`, c0097 on `codex/c0097-copper-rule-explain` and c0099 on `codex/c0099-body-volumes`, with no hash; c0100–c0120 on `review-roadmap-complex-board` at `1a130741`. No branch read here holds a folder c0098. The scope line of each group in the roadmap is taken from the "Why" of its proposals. The two hashes are the tips of their branches as read on 2026-10-07; those two branches hold proposals only and did not move that day. The three branches of board authoring were rebased onto `17234727` and amended while this change was written: three readings of that day gave three tips for c0096 and for c0097 and two for c0099, and the first reading (`22211ac2`, `0469d171`) was of commits no longer on the branch. A hash written for them would be false by the next amend, so the roadmap gives none and names the command that reads the tip. On every reading the folder and the slug were the same, and the tip of each was one commit that implements its change with the proposal in it.
- **Census before the change** (the script of task 1.1, archive excluded): 137 lines with "v0.4" in 40 files, none with "v0.2c", and 50 lines with "v0.3" in 15 files.

## The mapping

| the text meant | it now says |
|---|---|
| the milestone of the write side, where no read change is in sight | v0.3 |
| the same, where the sentence also speaks of read changes, or says "nothing else of" the milestone beside read changes it depends on | the write part of v0.3 |
| the read milestone, where the sentence would now be false or unclear for the whole of v0.3 | the read part of v0.3 |
| a release, not a milestone | `0.3.0`, or "0.2.0 and earlier" |
| column cells and table labels | "v0.3 read", "v0.3 write" |
| the proposals on other branches | v0.4 |

## Decisions

1. **"Nothing else of v0.4" becomes "nothing else of the write part of v0.3".** The proposals of c0083 to c0087 list read changes they depend on (among c0040 to c0046) and then say that they need nothing of the milestone. With a bare "v0.3" the sentence would contradict its own list.
2. **The model is additive-only "at the end of the read part of v0.3".** ADR-0001, two lines of the roadmap and the design of c0083 said "at the end of v0.3". That moment has passed (the design of c0083 already says "since"), and v0.3 as a whole ends at `0.3.0`, so the bare name would move the rule into the future. c0126 changes the model inside the write part, additively; its own design says so.
3. **The help text names a version.** `--altium-symbols generic` gives "the output of 0.2.0 and earlier": the option keeps the bytes that the released packages wrote, so the release is what a user can check. `git grep "output before"` finds the sentence in `cmd_build.py` only: no test, golden file, schema, spec delta or page pins it. `docs/altium.md` describes the option in its own words and is unchanged.
4. **The release notes "of v0.4" in the design of c0092 become "of 0.3.0"**: the question there is about a release. Its "v0.4 acceptance" becomes "v0.3 acceptance", and the proof command of its open task 5.2 greps for the new heading of the roadmap, or the task could never pass.
5. **Ticked tasks and dated notes keep their substance.** In the tasks of c0083, c0090, c0124, c0125, c0127 and c0128 only the name changes ("the v0.3 write table of `docs/roadmap.md`"); every hash, count and date stays.
6. **The decision of c0083** asked "inside v0.4, or earlier as a v0.3 follow-up". Both names would now be v0.3, so it reads "inside the write part of v0.3, or earlier as a follow-up of the read part". Row 24 of the roadmap's open decisions follows it.
7. **The register rows say "kit request (v0.3)".** The register guard requires the prefix "kit request" only; the sample text of three tests follows the rows, and the two places in c0091 that quote the rows follow too. `tools/gen_evidence_matrix.py --check` passes without a regeneration: the matrix does not hold the test column.
8. **The id table gets "v0.3 read" and "v0.3 write"** in its milestone column, so that the column still tells the two parts apart. c0048 already said "v0.3 (Altium writer)" and is left.
9. **Open decisions, row 21**, said that c0077–c0081 "are free"; the agent track holds them now, so it says "were free then". Its default is unchanged.
10. **The roadmap's row of v0.3 names every open change by its id**, not by a range, so that the bullet of "Version 0.2.0" about changes that are not archived holds for it whichever way it is read. The word "proposed" is not used in that row; "with no task ticked" says the same of c0092, c0121 and c0126.
11. **The week table** keeps every number of the project plan: its two rows become the read and the write part of v0.3, and v0.4 gets a row that says "not estimated". The counts "about 70" and "about 61" are kept, with a sentence that they do not hold the proposals of v0.4.
12. **The section of v0.4 has no state and no size per change.** The folders are not on `dev`, so by the page's own rule their ids are estimates. It names the overlaps of the decision (c0113, c0103 and c0102 with c0096; c0100 and c0101 with c0085) and reconciles none.
13. **The identifiers of the acceptance run in c0092 follow the name.** The script, the test, the hypothesis and the probe that c0092 plans were spelled with the old number and no dot (`tools/acceptance_v04.py`, `test_v04_acceptance.py`, the probe `acceptance-v04`, and a hypothesis id that ended in `V04`). c0092 has no task ticked and none of the four exists in the tree, so they become `acceptance_v03.py`, `test_v03_acceptance.py`, `acceptance-v03` and `H-A-ACC-V03` in its design, its delta of `altium-build` and its task 2.1, beside "the v0.3 acceptance run" of its proposal. The census of task 1.1 looks for this spelling too.
14. **c0132 and c0134 are stated as the tree has them.** The row of v0.3 says that c0123 and c0132 are folders on their own branches and that the branch of c0134 holds no folder, and the "Total" line under the follow-up table no longer calls c0132 reserved. The row of c0132 in `openspec/README.md` keeps "reserved" in its slug cell, with only the milestone word changed: the id table gets slugs from the change that brings the folder, and the branch of c0132 rewrites that row whole.
15. **The scope line of the complex board claims what the proposals hold.** All 21 name the review of 2026-10-05; 19 record a measurement and the other two (c0100, c0103) a probe; `kicad-cli` is named in 10, and c0109 measures a router run. The line says "most with a measurement or a probe of that day recorded in the proposal" and names no tool.

## Left as it is, and why

- **"v0.3" for work of the read part that is still true of v0.3**: "buses (v0.3)", "the v0.3 reader", "second-backend reading starts with v0.3", "the v0.3 analysis change" (c0047), the guard's `MILESTONES` and the sentences of the release records.
- **`H-G-SHAPELY-GC`, "boolean-backends change, v0.3"**: a placeholder for a change that is not proposed. `verification-evidence` and `tests/unit/verify/test_register.py` pin the words; the rename makes them neither false nor less exact than they were.
- **The paragraph of the roadmap that begins "The ten changes that remain, all proposed and none implemented"** is older than the table under it and does not name a milestone. It is not a matter of names and is left to the next update of the page.
- **The quote in the proposal of c0090** ("Writing an imported model is not available before v0.4") is the living text of `altium-verification`, word for word; it is kept until that text changes (below).

## Living specs

`git grep -n "v0\.4" -- openspec/specs` finds one line, and `git grep -n "v0\.3" -- openspec/specs` four.

| living text | handling |
|---|---|
| `altium-verification`, "Round-trip level RT-A2": "writing an imported model is not available before v0.4" | **No delta here.** The open change c0090 holds a MODIFIED delta of this requirement, and its text for that bullet ("RT-A2 is not judged for a file that no Fenolite build wrote …") no longer has the phrase, so there is nothing to correct in it. The living line keeps the old name until c0090 is archived. |
| `release-gate`, "Version 0.2.0": the roadmap "MUST name every change of the three milestones that is not archived" | **MODIFIED by this change.** The three milestones were v0.2a, v0.2b and v0.3 as it was then, the read changes c0039–c0047, and the guard checks exactly those ranges. With v0.3 holding the write part too, the bullet would ask more than its guard. It now names them: "of v0.2a, of v0.2b and of the read part of v0.3 (c0039–c0047)". The requirement is copied whole from the living file, its four scenarios unchanged. No open change holds a delta of `release-gate`. |
| `altium-schematic-reader`: "no v0.3 change reads their content" (`.Harness` files) | Unchanged: true of the write part as well. `.Harness` appears in `read/project.py` as a document kind only. |
| `verification-evidence` (two lines): the test column of `H-G-SHAPELY-GC` names "the boolean-backends change (v0.3)" | Unchanged (above). |

## What still says "v0.4" afterwards

The census of task 1.1, run again at the end, archive excluded. The counts are lines.

| class | where | lines | why |
|---|---|---|---|
| the released record's own text | `docs/release/v0.2.md`, two lines | 2 | the record of a released version is not reworded; its new note says how to read them |
| sentences that state the rename, with the old name in them | `docs/release/v0.2.md` (the note), `CHANGELOG.md` (the entry of this change), `docs/roadmap.md` ("Milestone names", twice; "v0.3 write") | 5 | they are the mapping itself |
| the new v0.4 | `docs/roadmap.md` (status line, "Milestone names", the milestone row, the count, the section of v0.4, the cuts, the week table, the open decisions 34 and 35), `openspec/README.md` (the prose and the row of c0136) | 15 | they mean the proposals on other branches; two of them say "v0.2c" (the name on the branch) |
| living text that an open delta replaces | `openspec/specs/altium-verification/spec.md`, and its quotation in the proposal of c0090 | 2 | "Living specs", first row |
| this change's own folder | `openspec/changes/c0136-milestone-renumbering/` | see task 3.2 | it states the mapping |
| the number without its dot, as identifiers spell it (third list of the census) | `docs/roadmap.md`, the anchor of the section of v0.4 inside the milestone row; this folder, where decision 13 and the note of task 1.1 quote the spelling | see task 3.2 | the anchor comes from the heading of the new v0.4; the identifiers of c0092 no longer have it (decision 13) |

Nothing else remains. The archive is not counted and not edited.

## Risks

- **Other branches.** A branch written before this change says "v0.4" for the write side. A rebase gives no conflict where it adds new lines, so the old name can come back unnoticed. The census script of task 1.1 is the check to run after each such merge. The branches of c0123 and c0132 are two of them: the row and the "Total" line that this change words for c0132 are replaced by the branch's own when it lands.
- **The delta of `release-gate`.** The branch of the patch release also touches release pages. If it modifies "Version 0.2.0", the second to land re-bases its delta on the first.
- **A reader of an archived page** meets the old names. The roadmap's "Milestone names" and the note in the record of v0.2 are the two places that explain them.
