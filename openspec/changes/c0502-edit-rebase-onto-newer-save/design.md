# Design: c0502

The PCB edit session already has most of what a rebase needs. Its items name records by content
(`ops.View.find`: kind, geometry within `REACH`, net, layer, width; a component by designator, a polygon by
name). Its operations state old values (`old=`, `expect=`). Its commit re-reads the result and guards
connectivity and integrity (`session.verify`). The CLI already stages a reviewed write and refuses it when
an input changed (`cli/main._replay`, `FEN-4002`). This change adds the missing piece: the session's
operations recorded as data, with the base state of each target, so that the same edits can be run
again on a newer save and judged three-way.

## D1 Operations as data

c0497 (D1) gives the operations a JSON form for its `--ops-file`: one entry per operation,
`{"op": <Session method>, "item": <tagged item>, ...keyword arguments}`, read by a function that queues
them on a `Session`. This change uses that form for the plan and does not make a second one. What it adds
is the other direction. `session._Queued` keeps the entry it was queued from, `(gate, label, entry, run)`.
Each public `Session` method records its entry as it queues its closure, with values normalised to the
plan's form:

- lengths in integer nanometres (c0497 also reads text with a unit; the plan always holds integers);
- angles in integer microdegrees (`rotate`, `add_arc`, `add_fill`), converted once from today's float
  degrees, so the plan holds no float (AGENTS.md);
- `add_component`'s source as a path relative to the plan file plus its SHA-256. A session given source
  bytes cannot make a plan: `Session.plan()` raises `ValueError` naming the operation.

Alternative rejected: pickling the closures. It is not readable, not reviewable and not stable across
versions.

## D2 Identity and fingerprint

Identity of a target, in order:

1. a `Component`: the `UNIQUEID` of its `Components6` record, then its designator;
2. a `Polygon`: its `UNIQUEID` where `Polygons6` holds one, then its name;
3. every other item: its content key, the item as stated, found by `View.find`.

`UNIQUEID` comes first because the user may rename a component or a polygon in Altium, and Altium keeps the
unique id through a save (`pcb-document.md`, `Components6` keys; `H-A-EDIT-IDS`). Records with no unique id
(tracks, arcs, vias, fills, texts, regions) have only their content. `PrimitiveGuids`, which two documents
of the corpus hold (`pcb-document.md`), is not read: its form is not documented. It is an open question.

The **fingerprint** of a target covers only the fields its operation reads or writes:

| operation | fields |
|---|---|
| `move` | position (ends, centre, corners or vertices), layer, net, and the `expect` keys |
| `rotate`, `flip` | position, rotation, side |
| `set_property` | the key |
| `set_outline` | the outline |
| `set_rule` | the key and its paired key |
| `delete`, `clone`, `remap_layer` | the content key's fields |
| `create`, `add_component` | none (no target) |

Each field is held as the document holds it (integer units, mil text, names in place of indices), so the
comparison is exact. Fields an operation does not touch are left out on purpose. Altium may change them
on a save (a repour changes a polygon's pour keys), and they must not raise a conflict.

## D3 The plan

`Session.plan() -> EditPlan` runs the queued operations on a copy of the base, whatever the gates, and
writes nothing. The gates are still checked by `commit`. For each operation it records the target's
identity, its `base` fingerprint before the operation and its `result` fingerprint after it. A creation
records the fingerprint of the record it made. Each operation is fingerprinted on the state that the
earlier operations of the plan left, so an operation on a record that an earlier one made or moved
replays in order.

```json
{
  "schema": "fenolite.altium-edit-plan.v0",
  "document": "board.PcbDoc",
  "base_sha256": "…",
  "declared_nets": ["…"],
  "operations": [
    {"entry": {"op": "move", "item": {"kind": "track", …}, "dx": 0, "dy": 1000000},
     "gate": "move", "label": "…",
     "target": {"unique_id": null, "key": {…}}, "base": {…}, "result": {…}}
  ]
}
```

Canonical JSON (`canonical-serialization`), no date, no absolute path. `entry` is c0497's ops-file entry, read by
the same function. `EditPlan.read(text)` validates the schema and every entry, and raises `FormatError`
otherwise.

## D4 Replay and rebase

`edit.replay(plan, path, *, gates=None) -> Session` opens `path` and queues the plan's operations with a
rebase step before each. On the state the earlier operations left:

1. Find the target by identity (D2). A unique id that is gone falls back to the content key.
2. Not found: if a record matches the plan's `result`, the operation is skipped with
   `altium.edit.rebase-applied` (info). Otherwise `altium.edit.rebase-missing` (error).
3. Found: fingerprint it. If it equals `base`, the operation runs as recorded. If it equals `result`, the
   operation is skipped (`rebase-applied`). Otherwise `altium.edit.rebase-conflict` (error), naming each
   field with its base and current value.
4. A creation is skipped as applied when a record equal to its `result` exists, and runs otherwise.

Any error refuses the commit before an edit is made, with every conflict listed, not only the first.
Nothing is applied in part. To keep the rest, the user deletes the conflicting operation from the plan
file, or edits it to the current value. Applying the non-conflicting operations alone is not offered: the
remaining operations may depend on the one dropped.

When `path`'s bytes equal `base_sha256`, every step 3 succeeds by construction. Replaying a plan on the
document it wrote skips every operation, so a replay is idempotent.

This is the three-way rule of `lens.edits.merge_property` (`edit-merge`, "Three-way property merge"),
with base, ours (`result`) and theirs (the newer save). It is written again in `edit/plan.py`, about 40
lines, rather than imported: `package-layering` forbids `backends` to import `lens`, and the merge there is
keyed by component paths and model properties, not by records.

## D5 The CLI: c0497's `--ops-file` takes a plan

c0497 makes `fenolite edit PATH.PcbDoc --ops-file FILE [--gate NAME]...` run a JSON list of entries. This
change adds two things to that command and no new option:

1. **The plan as output.** The result of a run on a plain list gains `edit_plan`, the `EditPlan` of the run
   made on the board as read (D3). An agent saves it as it reviews the dry run, with no Python.
2. **The plan as input.** When the file is an object with `"schema": "fenolite.altium-edit-plan.v0"`, the
   command calls `replay(plan, PATH, gates=<--gate>)`, then `apply` and `verify`, as `commit` does, writing
   nothing. A plan that does not read is `FEN-3004`.

Rebase issues join the session's issues. With an error, no write is planned (exit 5), as for every
command. Otherwise there is one `PlannedWrite` of the new bytes, with `depends` on `PATH`, the plan file
and every `add_component` source. `result` also holds `base_sha256`, `document_sha256`, `rebased` (whether
the two differ) and `operations`: one row per operation with `label` and `status` (`applied`,
`already-applied`, `conflict`, `missing`) and, for a conflict, `fields`.

`--confirm --plan ID` writes the staged bytes through `cli/main._replay`, unchanged. A save in Altium
between the dry run and the confirmation changes `PATH`'s digest, so the confirmation fails with
`FEN-4002` as today. The next `--dry-run` rebases the same plan file onto the newer save. No new FEN code
and no new option are needed. Gates are c0497's: closed ones are `altium.edit.gate` errors, and `--gate`
opens one for the run with its warning.

`edit-merge` is the nearest existing mechanism. Its edits file (`lens.edits`, `edits.toml`) records property
edits of a design script's parts, not records of a native document, so the plan is not stored there.
The rule it applies is reused (D4).

## Risks

- A content key that matches a different record after a save (two equal tracks, one deleted): `View.find`
  already refuses two matches within `TOLERANCE`. A single wrong match is caught by the fingerprint only
  when a fingerprinted field differs. A track that is the same in content is the same edit target for the
  user too.
- Altium may round coordinates on save. Fingerprints compare exactly, so a rounded target becomes a
  conflict, never a silent edit. If kit runs show such rounding, `REACH` is the place to widen it, not the
  fingerprint.

## Format evidence needed

None new: identity uses `UNIQUEID` keys that are already documented and the content keys that the items
use. Whether a component's and a polygon's `UNIQUEID` survives Altium's save is `H-A-EDIT-IDS`. The unit
tests stand in for a save with a copy that the test makes: records reordered, a component renamed, one
track moved. The kit's re-saved board of case J1 (`J01-resave.PcbDoc`, kept outside the repository) is
replayed by hand once, and the result goes in `docs/evidence/altium-edit.md`.
