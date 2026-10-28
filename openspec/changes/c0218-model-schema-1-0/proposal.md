## Why

The roadmap's v1.0 freeze names "model schema version 1.0 with migrators" (`docs/roadmap.md`, "Phase 5: to
1.0"). The model's `SCHEMA_VERSION` has been `"0"` since change c0004 (`model/design.py`). Every change since
then added fields that a document written before loads without (`docs/design-model.md` says so about thirty
times). The other direction does not hold: a document written by a later release may hold fields an earlier
reader refuses or reads wrongly, and the version in `meta.json` does not tell them apart. Every build stores
its model in the output folder's `.fenolite/` (`canonical.dump_texts`), and `fenolite diff`, `place`, the
assembly outputs and `fenolite.api` read it back with `canonical.load_dir`. That reader refuses any version
but `"0"`, and each layer schema closes its objects (`additionalProperties: false`). So the first release
that writes `"1.0"` must also read every folder that `0.1.0` to `0.5.0` left, or the users' projects stop
working.

This is the third of the five changes of the freeze (c0216 to c0220). It is independent of the other four.

## What Changes

- **A pre-freeze review of the model**: a generated list of every entity, field, default and `ext` key, for
  the maintainer to decide what is renamed or dropped before the version is frozen. Each decision becomes a
  step of the migrator.
- **`SCHEMA_VERSION = "1.0"`** as `MAJOR.MINOR`: within `1.x` a minor adds optional fields only; a new major
  changes or removes them.
- **Migrators** (`fenolite.model.migrate`): a chain of steps from `"0"` to `"1.0"`. `canonical.load_dir`
  migrates a `"0"` folder in memory and gives one `model.migrated` info; a folder of a newer minor or major
  is refused with exit 3 (`FEN-3002`, "from a future format version"), naming the version it needs.
- **`fenolite migrate DIR`**: writes a migrated folder under the mutation protocol (`--dry-run`,
  `--confirm`, a `.bak` per file).
- **Fixtures of every release**: the model folders that `0.1.0` to `0.5.0` write for one example board, built
  from their tags, read by the migrator in a test.
- **Schemas** `schemas/fenolite.model.v1/<layer>.json`; the `v0` files stay.

## Capabilities

### New Capabilities

- `model-versions`: the version form, the migrators, the refusal of a future version, `fenolite migrate`.

### Modified Capabilities

- `canonical-serialization`: MODIFIED "Schema generation and drift control"; ADDED "Versioned schemas".

## Non-goals

- A migrator from `1.x` to `0.x`: a downgrade of the model is not offered.
- Files of backends (`.kicad_pcb`, `.PcbDoc`): their versions are the backends' (`kicad-version-gating`).
- New model content: the review renames or drops, it adds nothing.

## Evidence level required

- Mechanical: the fixture folders of each release migrate and load, and a migrated folder dumps as a fresh
  build of the same board does, but for the fields later releases added. No format claim.

## Impact

- New: `src/fenolite/model/migrate.py`, `src/fenolite/cli/cmd_migrate.py`,
  `schemas/fenolite.model.v1/`, `tests/data/model/v0.1.0` to `v0.5.0`, `tests/unit/model/test_migrate.py`.
- Changed: `model/design.py`, `model/canonical.py`, `tools/gen_schemas.py`, `docs/design-model.md`,
  `docs/cli-contract.md`, the agent guide.
- Size: about 5 days.
