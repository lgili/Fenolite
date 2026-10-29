## Why

Package 12 of c0175 (`openspec/changes/c0175-board-engineering-tools/`), moved here on 2026-10-29. A board
whose owner keeps editing it in Altium Designer can only be changed offline through the saved document. In
the maintainer's work about one hundred and fifty scripts made record-level edits of such documents, and six
kinds of offline edit made the tool crash on open or save. Fenolite reads these documents losslessly and
writes compound files, but it has no edit session: no typed, asserted edit that keeps the document's index
tables consistent, and no check of the faults that make the tool fail.

Nothing public says what Altium Designer changes in a document when it makes one edit. So the facts come
first, by observation: the maintainer edits documents authored for Fenolite, one change at a time, and
Fenolite reads what was saved. Only then is write code written, each operation behind its own gate.

## What Changes

- **Hypotheses first.** `docs/hypotheses.md` gets the rows `H-A-EDIT-*` (what each edit changes) and
  `H-A-INTEG-*` (the integrity rules), each `INFERRED` with its kit case.
- **Kit Part J** (`docs/evidence/altium-edit.md`). Phase A: an authored project and twenty-one cases that
  the maintainer opens, edits once, saves and sends back. Phase B: the documents the session writes and
  copies with one planted fault each, opened, saved and reopened in Altium.
- **Integrity check.** `fenolite check DOC --stages altium.integrity`, read-only: gaps in polygon
  sub-indices, duplicate pour indices and ids, parameter groups and orphans, the model store, two layer
  fields that disagree. A rule whose row is not confirmed reports `warning`.
- **Edit session.** `fenolite.backends.altium.edit.open(path) -> Session` with `delete`, `move`, `rotate`,
  `flip`, `set_property`, `clone`, `add_component`, `remap_layer`, `set_rule` (PCB) and `set_property`,
  `move`, `delete` (schematic); asserted old values; records cloned from the document; every index kept;
  `commit(out)` with strict read-back, an unexpected-change gate and a connectivity gate. Every operation is
  behind a gate that is off by default until its phase B case passes.

## Capabilities

### New Capabilities

- `altium-edit`: the edit session, its assertions, cloning and index upkeep, the commit gates, the
  integrity check and the kit cases of Part J (moved from c0175, where its "Integrity check" and "Edit
  session" requirements were each over 500 characters; they are split here).

### Modified Capabilities

None.

## Non-goals

- No change of a document that the user names as a master (`--master`) until the kit graduates the
  operation.
- No decompiling, tracing or scripting of vendor software to learn the format; observation of saved files
  only. Altium Designer is never started by Fenolite.
- No PCB library session beyond what phase A observes; no Draftsman or output-job repointing (package 9
  of c0175 takes it once the drawing writer of c0172 graduates).
- No organisation's documents, names or values; the kit's board is authored for Fenolite.

## Evidence level required

- Hypotheses and kit phase A: `INFERRED`, until the maintainer's report (task 1.2).
- The integrity check: `INFERRED`; a rule reports `error` only once its row is confirmed by phase B.
- Each write operation: experimental and gated off until its phase B case passes
  (`ALTIUM-VERIFIED(kit)` through c0092's graduation rule).

## Impact

- New: `src/fenolite/backends/altium/edit/` (session, operations, indices, commit, integrity), the check
  stage `altium.integrity`, `docs/evidence/altium-edit.md`, `tests/data/altium_edit/`,
  `tests/unit/backends/altium/test_part_j.py`, `tests/unit/backends/altium/edit/`.
- Changed: `docs/hypotheses.md`, `fenolite check` stages, the agent guide.
- Size: about 10 design-days, gated by two kit runs.
