# c0502: replay an Altium edit session onto a newer save of the same board

Found on: editing a private two-layer power board with `fenolite.backends.altium.edit` on 2026-11-11
(codes only; nothing from the board is in this change).

## Why

**F42.** While the edits were being prepared, the user saved a newer version of the same board in Altium
twice. Each save made the prepared edits useless, and they were re-applied by hand:

- A `Session` holds its operations as closures (`session._Queued.run`). Nothing records them, so a session
  cannot be saved, read back or run again on other bytes.
- The scripts named some targets by record index (`state.get(storage)[i]`, `s._queue`). Altium's save
  renumbers and reorders records, so those indices named other records. The workaround matched primitives
  by geometry, net and layer instead. The public items (`Track`, `Via`, `Component`, …) already do that
  (`ops.View.find`), but nothing replays them.
- Re-running a script on the newer save would apply every edit blindly. An edit whose target the user had
  changed in Altium would overwrite the user's change, or would fail on a stale `old=` with no
  explanation of what changed.

The CLI already refuses a reviewed plan whose input changed (`FEN-4002`) and asks for a new dry run. c0497
adds `fenolite edit PATH.PcbDoc --ops-file FILE`, a JSON list of session operations. A new dry run of the
same ops file after a save applies every entry again with no check that its target is still what the
user reviewed.

## What Changes

- **An edit plan.** `Session.plan() -> EditPlan` records the queued operations as data, in canonical JSON
  (`fenolite.altium-edit-plan.v0`): the operation, its item, its arguments and stated old values, and per
  target its identity and its *base* fingerprint, the target's fields in the document the plan was made on.
  `edit.replay(plan, path) -> Session` queues the same operations on another document.
- **Stable identity.** A component or a polygon is found by its `UNIQUEID` where the document holds one.
  Everything else is found by the content key the items already use (kind, geometry, net, layer, width),
  never by record index.
- **Rebase, three-way.** On replay each target's fingerprint now is compared with the base and with the
  plan's result, as `lens.edits.merge_property` does for properties (`edit-merge`, "Three-way property
  merge"):
  - now equals base: the edit is applied;
  - now equals the plan's result: it is already applied and skipped (`altium.edit.rebase-applied`, info);
  - the target changed otherwise: `altium.edit.rebase-conflict` (error), naming the fields and their base
    and current values;
  - no target: `altium.edit.rebase-missing` (error).

  A conflict refuses the whole commit: nothing is applied silently.
- **The CLI, through the existing plan mechanism.** c0497's `--ops-file` also takes an edit plan. An
  edit plan is c0497's list of entries with each entry's `target`, `base` and `result` added. The dry run
  of an ops file reports the plan in `result.edit_plan`, so an agent saves it with no Python. `--dry-run`
  with a plan replays it on the board as it is now and stages the written bytes. `--confirm --plan ID`
  writes them. A newer save between the two gives `FEN-4002` as today, and the next `--dry-run` rebases
  the same plan file onto the newer save. Conflicts are error findings (exit 5), so no write is planned.

## Impact

- New `src/fenolite/backends/altium/edit/plan.py`. `edit/session.py`: `_Queued` keeps the c0497 ops-file entry
  it was queued from. `edit/ops.py`: `fingerprint(view, item)` and identity lookup.
  `edit/__init__.py` exports `EditPlan` and `replay`.
- `src/fenolite/cli/cmd_edit.py`: c0497's `--ops-file` reads an edit plan too, and the result gains
  `edit_plan`, `rebased` and per-operation statuses. Schemas regenerated for the plan file and the result.
- Depends on c0497: its ops-file entries are the operation form of the plan, and its `--gate` is how the CLI
  runs an operation whose gate is off.
- `docs/cli-contract.md` ("edit"), agent guide `altium.md`, `explain.toml` for the three new codes,
  `CHANGELOG.md`.
- Schematic sessions are out of scope: their operations name parts by designator, which a save keeps, and
  the reported failure was on the board.
