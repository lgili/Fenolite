# The Fenolite design model (v0)

Normative text: `openspec/specs/design-model/`, `openspec/specs/canonical-serialization/` and
`openspec/specs/core-primitives/`. Decision record: `docs/adr/0001-neutral-model.md`.

## Entity header

Every entity (`fenolite.model.base.Entity`) carries:

| Field | Meaning |
|---|---|
| `id` | `<prefix>_<uuid>` (prefixes in `fenolite.core.ids.PREFIXES`) |
| `native_ids` | the object's id in each backend, e.g. `{"kicad": "a81c…"}` |
| `provenance` | backend, file, file SHA-256, opaque locator, evidence |
| `ext` | per backend, what the model does not understand, verbatim, with the minimum format version it needs |

Entities are frozen dataclasses; change them with `dataclasses.replace` and
`Design.replace_entity`.

## Units

Lengths are `int` nanometres, angles `int` microdegrees; floats are rejected everywhere
(`docs/formats/units.md`). `fenolite.core.units.parse_length("0.25mm") == 250_000`.

## Ids

| Object | Id |
|---|---|
| imported, with a native id | `uuid5(FENOLITE_NS, "<backend>:<native id>")` |
| imported, without one | `uuid5(FENOLITE_NS, "<backend>:<document id>:<section>:<content hash>")` |
| created by Fenolite | `uuid4` from a seeded generator (`--seed`) |

A file hash never enters an id. Ids of objects without a native id are stable when *other*
objects change; the diff matches such objects by content.

## Layers (v0.1 subset)

| File | Class | Contents |
|---|---|---|
| `meta.json` | `DesignHeader` | id, name, `schema_version` (`"0"`), `fenolite_version` |
| `circuit.json` | `Circuit` | components (pins), nets (pin members), net classes, interfaces, modules |
| `board.json` | `Board` | outline, layers, stack-up, footprints (pads), tracks, arcs, vias, zones, keep-outs, texts, graphics, holes |
| `rules.json` | `RuleSet` | rules: kind, selectors, layers, min/opt/max, severity, priority (1 = highest) |
| `manufacturing.json` | `Manifest` | generated artefacts with tool, version, revision, variant, evidence, state |
| `findings.json` | `Findings` | issues |

`Design` aggregates them and offers read-only indexes (`by_id`, `by_ref`, `by_net`, `by_layer`)
and `validate()` (duplicate ids and references, dangling references, empty and single-pin nets).

## Canonical JSON

`fenolite.model.canonical`: UTF-8, LF, two-space indent, keys in field order, defaults omitted,
integers only, collections of entities sorted by `(kind, path | ref | name | number, id)` unless a
field is marked `ordered` (stack-up and board layers, polygon points), mappings sorted by key.
`dumps(loads(dumps(x))) == dumps(x)`; moving one footprint changes only its position lines.
Reading validates every value against the same annotations the JSON Schemas in
`schemas/fenolite.model.v0/` are generated from and reports the first problem with its JSON pointer.

## Slots (for backends)

A backend represents each node it reads as an ordered list of `Modeled(field)` and
`Opaque(fragment, min_version)` children and writes opaque children back verbatim in their original
position. This is what makes "read → write unchanged" lossless without matching the tool's own
formatter byte for byte. The first backend to implement it is the KiCad board backend.

## Layout authority

For a design authored in Fenolite, the exported tool project is the source of truth for layout;
`.fenolite/` is a regenerable, git-ignored cache; imported third-party files are kept immutable by
SHA-256 under `native/`.
