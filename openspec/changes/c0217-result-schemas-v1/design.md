## Context

- `fenolite.api.schema` holds the wire classes of `equivalent` (`EquivalentReply`) and `convert`; nothing
  builds a reply from them, they only describe it, and `tools/gen_schemas.py` writes the files.
- `tests/consistency/test_cli_consistency.py`: `result_schema(name)` finds
  `schemas/fenolite.<name>.v0.json`; `RESULT_SCHEMAS` are the commands that have one (two today), and each
  example's result is validated against it.
- Measured on 2026-10-28: 46 visible commands, every example runs (`restore` and `publish` exit 3 by
  design).
- Schema ids in the code: about thirty `fenolite.<name>.v0`; files under `schemas/` for `envelope`, `error`,
  `artifacts`, `convert`, `equivalent`, `placement-request`, `review` and the model layers.

## Goals / Non-Goals

**Goals:** a schema for each command's result, written from the code, tested on every example; a schema
for each public file format; a stated rule for what a `1.x` schema may change.

**Non-Goals:** the model (c0218); new result content.

## Decisions

1. **Wire classes, not hand-written JSON.** One module per family under `src/fenolite/cli/results/`
   (`discovery.py`, `writers.py`, `checks.py`, `analyses.py`, `outputs.py`, `edits.py`, `inspection.py`),
   each a set of frozen dataclasses that describe a result, the way `fenolite.api.schema` does; a registry
   `fenolite.cli.results.RESULTS: Mapping[str, type]` maps a command to its class. A result whose part is
   free by nature (`inspect`'s stream tree, `guide`'s page) is typed to the level that is fixed and is an
   open map below it, with the reason in the field's `description`.
2. **Generation.** `tools/gen_schemas.py` writes `schemas/fenolite.<command>.<CONTRACT_VERSION>.json` for
   every entry of `RESULTS`; the `v0` files of `equivalent` and `convert` stay as they are.
3. **Open published, closed tested.** The generator writes `additionalProperties: true` on every object of
   a result schema (the published form); `tests/_schema.py` gains `closed(schema)`, which sets it to `false`
   everywhere, and the consistency suite validates with the closed form, so an undocumented key fails here
   and a consumer of `1.0` still reads `1.3`.
4. **Inconsistencies are fixed in the open.** Where one key holds two types today (measured on the
   examples and on the unit tests' replies), the change keeps the more general form, says so in
   `CHANGELOG.md` and lists it under task 1.2; nothing else of a result changes.
5. **File formats.** `tools/gen_schemas.py --formats` lists every `fenolite.<name>.v0` id in `src/` with the
   module that reads or writes it. Each is classified `public` (a user writes it, or an agent reads it as the
   output of a command) or `internal`; the classification is the maintainer's (task 1.3). A public format
   gets `schemas/fenolite.<name>.v1.json` from its dataclass, and its reader accepts both ids; an internal
   one keeps its id and is named internal in `schemas/README.md`.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/cli/results/__init__.py` (new) | `RESULTS`, the registry |
| `src/fenolite/cli/results/<family>.py` (new) | the wire classes of each family's results |
| `tools/gen_schemas.py` | result schemas from `RESULTS`; `--formats` |
| `tests/_schema.py` | `closed(schema)` |
| `tests/consistency/test_cli_consistency.py` | a schema for every visible command; closed validation |
| `schemas/fenolite.<command>.v0.json` (new, then `v1` at the switch) | generated |

## Evidence level per behaviour (before merge)

| behaviour | level |
|---|---|
| each command's example result validates (closed form) | mechanical (consistency suite) |
| schemas current | mechanical (`gen_schemas.py --check`) |
| a public format read in `v0` and `v1` | mechanical (unit tests of each reader) |

## Risks / Trade-offs

- An example covers one path of a command; a key that only another path writes is caught by the unit
  tests that validate their replies (task 1.1 adds the helper they call).
- Open published schemas cannot tell a consumer that a key is gone; c0216's surface judge does not see
  result keys either, so the drift check of the schema files is the guard: a removed field changes a
  committed file, and the review of that diff is the gate.

## Open questions

The maintainer accepted every recommended answer below on 2026-10-27 (roadmap, "Open decisions", row 49).

1. Which file formats are public? Recommended: the inputs a user writes (`requirements`, `drawing-spec`,
   `placement-request`, `export-preset`, `assembly-template`, `review`) and the outputs an agent reads
   (`artifacts`, `build-record`, the panel model, the kit's `kit.json` and run record); the viewer's
   documents and the kit's form internal. Decided by the maintainer on 2026-10-27: as recommended. An id that the inventory of task 1.3 finds
   beyond these lists is classified there.
2. Should a removed result key be refused by a test after 1.0, as c0216 refuses a removed option?
   Recommended: yes, by comparing each schema's property names with the last release tag's, in this
   change's drift test. Decided by the maintainer on 2026-10-27: as recommended.
