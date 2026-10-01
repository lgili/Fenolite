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

## Library definitions

`fenolite.model.library` holds reference data shared by many designs, outside `Design` and outside
the `.fenolite/` layer files (normative text: requirement "Library definitions" of the
`design-model` capability, change c0008):

| Class | Contents |
|---|---|
| `FootprintDef` | entity: `name`, `library`, `description`, `keywords`, `kind`, `flags`, `properties`, `pads` (board `Pad`, `net_id = None`, positions relative to the definition), `graphics` (board `Graphic`), `models` |
| `SymbolDef` | entity: `name`, `library`, `extends`, `power`, `properties`, `in_bom`, `on_board`, `exclude_from_sim`, pin-name settings, `units`, `pins` |
| `SymbolPin`, `SymbolUnit`, `PinAlternate` | value objects without the entity header; a pin is identified by `(unit, body_style, number)` |
| `Library` | `name`, `footprints`, `symbols`; schema `fenolite.library.v0` (`schemas/fenolite.model.v0/library.json`) |

- Every field other than `name` has a default. `keywords`, `flags`, `pads`, `graphics`, `models`,
  `units`, `pins` and `alternates` are ordered; `properties` is sorted by key.
- **Ids.** Definitions use the prefixes `fpd` and `sym`, with the native id `"<library>:<name>"`
  (or `"<name>"` for the library `""`) stored in `native_ids[<backend>]`.
- Pads, padstacks and graphics are scoped to their definition:
  - with a native uuid `U`, the id is `derived_id(prefix, backend, "<native id>:<U>")`, and `U` is
    stored in `native_ids[<backend>]`; a uuid repeated inside one definition keeps that form for its
    first occurrence, and its k-th repetition uses `"<native id>:<U>:<k>"`;
  - without one, it is a content id whose document is the definition's native id, whose section is
    `pad` or `gfx`, and whose digest includes an occurrence counter among identical contents.

  Ids are therefore unique within a `Library`. A consumer that places a definition twice derives new
  ids for the placed copies.

## Boards read from a backend

Normative text: requirements "Board entities read from file backends" and "Components synthesised
from a board" of the `design-model` capability (change c0009); KiCad facts in
`docs/formats/kicad/board.md`.

| Field | Meaning |
|---|---|
| `FootprintInstance.attributes` | ordered footprint flags: `smd`, `through_hole`, `board_only`, `exclude_from_pos_files`, `exclude_from_bom`, `dnp`, `allow_missing_courtyard`, `allow_soldermask_bridges` |
| `Via.via_type` | `through` (default), `blind`, `buried` or `micro` |
| `ZoneFill.island` | the fill is an island; a zone may have several fills per layer, in file order |
| `Zone.name` | the zone's name, `""` when it has none |

- **Pad frame.** `Pad.position` is footprint-local: absolute = `instance.position +
  R(instance.rotation)·pad.position`, with no further mirror, so a bottom footprint keeps its stored,
  mirrored coordinates. `Pad.rotation` is relative to the footprint, and `Pad.layers` are real board
  layers without wildcards.
- **Outlines.** An empty `Zone.outline` or `Keepout.outline` means the backend keeps the outline as
  an opaque slot. `Board.outline` is `None` for an imported board; its edge graphics are authoritative.
- **Layers.** `Layer.ordinal` is the stack position; the backend's own number, type and user name
  are in `Layer.ext[<backend>]`.
- **Synthesised circuit.** A board read without a schematic gets one `Component` per footprint, one
  `Pin` per distinct non-empty pad number and net members from the numbered pads. `validate()`
  reports `model.duplicate-ref` as a warning (not an error) when the shared reference ends in `**`,
  or when every component sharing it is placed only by `board_only` footprints.

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
