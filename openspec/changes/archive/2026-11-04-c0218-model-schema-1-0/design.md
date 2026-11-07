## Context

- `fenolite.model.design.SCHEMA_VERSION = "0"`; `meta.json` holds `schema_version` and `fenolite_version`
  (`DesignHeader`). `canonical.load_dir` reads each layer file, validates it against its schema, and raises
  `FormatError` for a `schema_version` other than `"0"` (`model/canonical.py`).
- The layer schemas `schemas/fenolite.model.v0/*.json` (10 files: board, circuit, drawing_sheet, findings,
  library, manufacturing, meta, panel, rules, schematic) close their objects: `board.json` holds 34
  `"additionalProperties": false`.
- Writers of model folders: the KiCad build and the Altium build store the model in the output's
  `.fenolite/` (`lens/build.py`, `lens/altium.py`); the panel writes `<name>.panel.json`. Readers:
  `cli/_documents.py`, `cli/cmd_diff.py`, `cli/cmd_place.py`, `cli/_assembly.py`, `api/sides.py`.
- `docs/design-model.md` records, per change, that a field was added and that `schema_version` stays `"0"`,
  and for most that an earlier release cannot read the newer form.
- Fixtures today: `tests/data/model/v0.2.0` and `v0.2.1` (board layers only). The release tags `v0.1.0` to
  `v0.5.0` exist.

## Goals / Non-Goals

**Goals:** a version that says what a reader can read; every folder of `0.1.0` to `0.5.0` read by `1.0`; a
command that rewrites a folder; the model cleaned once, before it is frozen.

**Non-Goals:** downgrades; backend file versions; new model content.

## Decisions

1. **`MAJOR.MINOR`.** `"1.0"`. A minor release of the model adds optional fields with a default, no other
   change; a major changes a field's type, meaning or name, or removes it. A reader of `1.m` reads `0`, and
   `1.n` for `n <= m`; it refuses `1.n` for `n > m` and any major above 1 with `FEN-3002`, because writing
   back what it read would drop fields it does not know.
2. **One migrator per step** (`fenolite.model.migrate`):
   - `Step(from_version, to_version, apply: Callable[[dict[str, Any]], dict[str, Any]], notes)`, applied to
     the JSON of a whole folder (`{layer_file: object}`) before validation;
   - `STEPS` is the chain; `migrate(folder_json, version) -> tuple[dict, tuple[str, ...]]` returns the
     migrated JSON and the steps taken;
   - the step `"0" -> "1.0"` sets defaults that a later release added (none is needed for loading today,
     which is measured on the fixtures), and applies the renames and removals of the review.
3. **`canonical.load_dir` migrates in memory**: it reads the folder's JSON, finds the version in
   `meta.json`, runs `migrate`, validates against the `v1` schemas and builds the design; the result
   carries one `model.migrated` info (`where` the folder) naming the steps. Nothing is written.
4. **`fenolite migrate DIR`** (mutating): plans the migrated layer files, written under `--confirm` with a
   `.bak` of each; `result.steps` and `result.from` / `result.to`. A folder already at `1.0` plans nothing.
5. **Fixtures from the tags.** `tools/model_fixtures.py` builds `examples/blink_2layer` with each release
   tag in a temporary `git worktree` (`uv run --project <worktree>`), copies its `.fenolite/` model folder to
   `tests/data/model/<tag>/`, and records the tag's commit. The fixtures are committed once; the tool is
   kept to show where they came from.
6. **The review** (`tools/model_review.py`): every dataclass of `fenolite.model` with its fields, types,
   defaults and the `ext` keys of each backend (`adapter.ids.EXT_KEYS`), with where each is read; the
   maintainer decides, item by item.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/migrate.py` (new) | `Step`, `STEPS`, `migrate`, `MigrationError` |
| `src/fenolite/model/canonical.py` | `load_dir` migrates; `model.migrated` |
| `src/fenolite/model/design.py` | `SCHEMA_VERSION = "1.0"`, `parse_version`, `readable(version)` |
| `src/fenolite/cli/cmd_migrate.py` (new) | `fenolite migrate DIR` |
| `tools/model_fixtures.py`, `tools/model_review.py` (new) | fixtures from tags; the review list |
| `schemas/fenolite.model.v1/` (new) | generated layer schemas |
| `tests/unit/model/test_migrate.py` (new) | each fixture migrates and loads; future versions refused |

## Evidence level per behaviour (before merge)

| behaviour | level |
|---|---|
| every release's fixture folder loads in `1.0` | mechanical (fixtures built from the tags) |
| a migrated folder equals a fresh build's (same board, same release of the example) | mechanical |
| a future version refused with `FEN-3002` | mechanical |

## Risks / Trade-offs

- A fixture of one example board does not hold every field; the migrator's step is also run on the model
  folders that the unit tests and the examples build today, and on each test of `tests/data/model/`.
- A user's folder from a development build between two releases may hold a form no tag holds; `migrate`
  names the field that fails validation, and `fenolite build` rewrites the folder anyway.

## Open questions

The maintainer accepted the recommended answers of questions 1 and 2 on 2026-10-27 (roadmap, "Open decisions",
row 49); question 3 is decided in task 1.2.

1. `"1.0"` or `"1"`? Recommended: `"1.0"`, so that a minor can say an addition without a new major. Decided by the maintainer on 2026-10-27: as recommended.
2. Should a reader of `1.0` read a `1.1` folder by ignoring unknown fields? Recommended: no (Decision 1): a
   later command would write the folder back without them. Decided by the maintainer on 2026-10-27: as recommended.
3. Which items does the review rename or drop? For the maintainer, from the list of task 1.1: it has no
   recommended answer and stays open until task 1.2.

## Actual current-source preparation, before activation

The candidate is based on cbd1e085 (actual typed d5ae37b0 plus reviewed c0217 descriptors), not the
historical bf6532a4/695 snapshots. Clean model0/CLI0 source was captured mechanically before any
migration code:174 dataclasses,1247 fields,40 fixed extension keys and76 version0 schema files
(including ten model0 layers). Human KEEP/RENAME/DROP review is still pending. Capturing original
bytes is not human approval and must not mark task1.2 complete.

Preserve all current entities, defaults, validators and opaque data; in particular BOM-only restrictions,
max_curve_error, font presence and DrawnLabel.intersheet_refs. Patch version plumbing/canonical loading
only. The migration Step adds four internal helper fields separately from the model0 domain inventory.
The implementation is a reviewable model1 candidate; CLI remainsv0 and package0.7.0.dev0. Final
integration/publication and archival require actual review and root exact-head gates.

Model-review tooling must default every decision to PENDING with no historical hardcoded date or
reviewer. KEEP-all may be recorded only explicitly with a real reviewer/date; no invocation of that
mode is authorized by the implementation agent. Retain the independent pending source0 preview and
compare every actual field/type/default against it before accepting a later candidate.

Actual2026-11-03 maintainer review approves KEEP of the source-bound original
174/1247/40 inventory. model0-approved.json records each reviewed shape and
source report hash. No type/default/identifier change is authorized. The
previously prepared Step helper remains separate migration machinery; do not
pretend its addition changed or was present in the original reviewed inventory.

Fast7 revealed older canonical aggregate/unused-key/default-byte guards that
correctly include metadata but still pin schema0. Keep those historic digests
unchanged and explicitly require actual schema1.0. A test-only compatibility
view may restore the one exact schema literal in a copied meta.json body for
comparison against that legacy reference; every other raw byte remains exact.
The active version assertion and full75-plan before/after proof separately
certify the intentional change. No broad exclusion, pin regeneration, runtime
writer change, evidence-warning omission or acceptance flag is authorized.
