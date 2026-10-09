## Why

The pages name two milestones for the second backend: v0.3 for reading (c0039–c0047) and v0.4 for writing (the experimental writers c0032–c0038, c0083–c0092 and their follow-ups). No release was ever numbered 0.3: the read work shipped inside the `0.2.0` package, and the release record of v0.2 claims no acceptance for it. So the next release, which carries the write side, would be called 0.4.0 after a 0.2.x, and a reader would look for a 0.3 that does not exist.

Meanwhile three groups of proposals were written on other branches and have no milestone name on `dev`: the agent track (c0077–c0081), board authoring (c0096, c0097, c0099) and the complex board (c0100–c0120, called v0.2c on its branch).

The maintainer decided on 2026-10-07:

- The write side of the second backend is renamed v0.3 and is released as `0.3.0`. v0.3 is then the whole second backend: its read part (c0039–c0047, already in the `0.2.0` package, no acceptance claimed for it there) and its write part.
- The name v0.4 belongs to the three groups of proposals on other branches. They come to `dev` after `0.3.0` is released and are reconciled then.
- v0.5a, v0.5b, v0.6 and v1.0 keep their names.

## What Changes

- **`docs/roadmap.md`.** The status lines; a section "Milestone names" with the decision and its date; one row for v0.3 with both parts and one row for v0.4 in the milestone table; Phase 4 as "v0.3 read" and "v0.3 write", with the acceptance block named "v0.3 acceptance"; a new section for v0.4 with the ids, slugs, branches and commits of the three groups, read from the branches; the cuts, the week table and the open decisions relabelled, with one row for this decision and one open row for c0098.
- **Every other page that is still open.** `CHANGELOG.md` under Unreleased, `openspec/README.md` (the id table and the prose above it), two ADRs, `docs/sheet-templates.md`, `docs/evidence/altium-roundtrip.md`, the eight rows `kit request (…)` of `docs/hypotheses.md`, and the proposals, designs and tasks of the open changes c0083 to c0131. Each mention is judged: "v0.3", "the write part of v0.3", "the read part of v0.3" or the version `0.3.0`, whichever the sentence needs.
- **One help text.** `fenolite build --help` said of `--altium-symbols generic` "the output before v0.4"; it says "the output of 0.2.0 and earlier". No test, golden file or page pins that sentence.
- **One test's sample text.** `tests/unit/test_hypotheses_register.py` uses "kit request (v0.3): open", as the register rows now read.
- **`docs/release/v0.2.md`.** One dated note at the end of its introduction. No sentence and no table cell of the record changes.
- **One requirement.** `release-gate`, "Version 0.2.0": the roadmap rule names the changes it is about (v0.2a, v0.2b and the read part of v0.3, c0039–c0047), which is what its guard has always checked.

Nothing a user runs changes: no command, option, output, issue code, schema or evidence level.

Size: half a design-day.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: MODIFIED "Version 0.2.0" (one bullet: which changes the milestone row of the roadmap must name).

## Non-goals

- No edit of anything under `openspec/changes/archive/`, of the `[0.2.0]` and `[0.1.0]` sections of the changelog, or of `docs/release/v0.1.md`. They keep the names of their day; the roadmap says how to read them.
- No rewording of the release record of v0.2 beyond the one note.
- No proposal of v0.4 is brought to `dev`, described beyond one scope line per group, sized or reconciled here. No decision about c0098.
- No row for c0133 or c0135 (the patch release `0.2.1`); they reach `dev` by a merge.
- No change of the guard `tests/unit/test_release_record_v02.py`.
- No second delta on a requirement that an open change already modifies (design, "Living specs").

## Evidence level required

None moves. No format fact, hypothesis level, claim or capability changes; the eight register rows change the words of their test column only, and the generated evidence matrix is byte-equal.

## Impact

- Changed: `docs/roadmap.md`, `openspec/README.md`, `CHANGELOG.md`, `docs/release/v0.2.md` (one note), `docs/hypotheses.md`, `docs/adr/0001-neutral-model.md`, `docs/adr/0005-sheet-templates.md`, `docs/sheet-templates.md`, `docs/evidence/altium-roundtrip.md`, `src/fenolite/cli/cmd_build.py` (one help string), `tests/unit/test_hypotheses_register.py` (three sample strings), and files of the open changes c0083–c0087, c0090–c0092, c0121, c0124–c0128 and c0130.
- Output that changes: the help text of `fenolite build --altium-symbols`.
- Other branches: a branch that still says "v0.4" for the write side is renamed when it is rebased; the roadmap's "Milestone names" says how to read it until then.
