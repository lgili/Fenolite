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
| placed copy of a library definition | from the caller's key, never from the seed (see "Placed copies") |
| created from a design script | `derived_id(prefix, "dsl", "<kind>:<key>")`, never from the seed (see "Ids of design scripts") |

A file hash never enters an id. Ids of objects without a native id are stable when *other*
objects change; the diff matches such objects by content.

## Layers (v0.1 subset)

| File | Class | Contents |
|---|---|---|
| `meta.json` | `DesignHeader` | id, name, `schema_version` (`"0"`), `fenolite_version` |
| `circuit.json` | `Circuit` | components (pins), nets (pin members), net classes, interfaces, modules, no-connect marks |
| `board.json` | `Board` | outline, layers, stack-up, footprints (pads), tracks, arcs, vias, zones, keep-outs, texts, graphics, holes |
| `rules.json` | `RuleSet` | rules: kind, selectors, layers, min/opt/max, severity, priority (1 = highest) |
| `manufacturing.json` | `Manifest` | generated artefacts with tool, version, revision, variant, evidence, state |
| `findings.json` | `Findings` | issues |

`Design` aggregates them and offers read-only indexes (`by_id`, `by_ref`, `by_net`, `by_layer`)
and `validate()` (duplicate ids and references, dangling references, empty and single-pin nets, and
no-connect marks on unknown or connected pins).

### No-connect marks

`Circuit.no_connects: tuple[PinRef, ...]` (the last field of `Circuit`, `()` by default) lists the pins
that the design leaves unconnected on purpose (`no_connect` of `docs/dsl.md`).

- A mark is a `PinRef(component_id, pin)`, the form of a net member. `pin` has two forms: the
  designator as written (a pin number or a pin name) in the model that `to_model` gives, and a pin
  number after a build has resolved it. Marks are stored in `PinRef` order without duplicates.
- A mark is a fact of the connection, not of the library pin. `Pin` and `PinType` are unchanged, and
  `Pin.etype == "no_connect"` still means the pin type that the symbol declares. A mark has no id.
- The field is additive: `canonical` omits the default, so a design without marks gives the
  `circuit.json` bytes it gave before, and a file without the key `no_connects` loads with `()`.
  `SCHEMA_VERSION` stays `"0"`; `schemas/fenolite.model.v0/circuit.json` lists `no_connects` as an
  optional array of pin references.
- `Design.validate()` reports three findings for a mark, each with `where` set to `<ref>-<pin>` (or
  `<component id>-<pin>` when the component is unknown):
  - `model.no-connect-on-net` (error): a net lists the same pin reference; the message names the net.
  - `model.unknown-component` (error): no component has the id.
  - `model.unknown-pin` (error): the component holds pins and none has the number.
- A marked pin is no member of any net: `by_net`, `model.single-pin-net` and `model.dangling-net` are
  unchanged.

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

## Presentation

`fenolite.model.presentation` (change c0012) holds what a sheet draws around a board:

- `Board.sheet: SheetFrameRef | None`: the paper (`A0` … `A5`, `Letter`, `Legal`, `Tabloid`, or `custom`
  with `width` and `height` in nm), `portrait`, and `drawing_sheet`, the project-relative path of the
  drawing-sheet file the project names (or `${KIPRJMOD}/…`).
- `Board.title_block: TitleBlock | None`: `title`, `date`, `revision`, `organization`, `doc_id`,
  `responsible`, `approver`, and `params`, user parameters a sheet may show.
- `DrawingSheet(name, setup, items)`: a definition outside `Design`, like a library definition, with
  prefix `wks` and its own schema `drawing_sheet.json`. One sheet serves many boards and sizes, so it is
  never written to the six layer files. Its id is `derived_id("wks", "template", <sheet.name>)` for a
  sheet built from a `*.sheet.toml` specification and `derived_id("wks", "kicad", <name>)` for one read
  from a KiCad file.
- Items are value objects in drawing order: `SheetShape` (`kind` `line` or `rect`), `SheetText` and
  `SheetBitmap`. Every point is a `SheetPoint(corner, x, y)`, an offset from a corner of the margin box
  (the page minus the setup margins), positive toward the interior, so one sheet fits every page size.
- Texts hold neutral tokens only: `{title}`, `{doc_id}`, `{revision}`, `{sheet}`, `{sheets}`, `{date}`,
  `{organization}`, `{responsible}`, `{approver}`, `{filename}`, `{paper}`, `{param:NAME}`, and `{{`/`}}`
  for literal braces. `split_tokens` is the only parser; each backend maps the tokens to its own
  variables.
- `Design.validate()` reports `model.sheet-path` (an absolute path or a `..` segment), `model.sheet-size`
  (an inconsistent custom or named size) and `model.param-name` (a parameter name outside
  `[A-Za-z_][A-Za-z0-9_]*`).

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
| `Zone.settings` | how the zone is filled (section "Zone settings") |
| `Zone.filled` | the board's own fill flag, kept apart from `Zone.fills`: a zone may be filled with an empty result |
| `Zone.locked` | the zone is locked against edits in the board editor |
| `Pad.zone_connection` | how zones connect to the pad: `solid`, `thermal`, `none` or `thru_hole_only`; `None` means that the pad follows its footprint and the zone |

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

## Zone settings

Normative text: requirement "Zone settings in the board model" of the `design-model` capability (change
c0031); KiCad facts in `docs/formats/kicad/board.md`, "Zone settings".

`ZoneSettings` and `ZoneHatch` are frozen value objects without the entity header. Every `Zone` has a
`settings` value; the defaults are the values KiCad gives a new zone, so a zone created with
`ZoneSettings()` behaves like one drawn in KiCad with the default dialog.

| `ZoneSettings` field | Meaning | Default |
|---|---|---|
| `clearance` | the smallest distance the fill keeps from copper of other nets; a larger net-class or rule clearance still wins | 500 000 nm |
| `min_thickness` | the smallest width of copper that a fill keeps | 250 000 nm |
| `connection` | how the fill meets pads of its own net: `solid`, `thermal` (reliefs with spokes), `none`, or `thru_hole_only` (reliefs on through-hole pads, solid on the others) | `thermal` |
| `thermal_gap` | the gap of a thermal relief | 500 000 nm |
| `thermal_spoke_width` | the width of a relief's spokes | 500 000 nm |
| `island_removal` | `always` removes copper that no pad connects, `never` keeps it, `below_area` keeps islands of at least `min_island_area` | `always` |
| `min_island_area` | square nanometres | 10 000 000 000 000 (10 mm²) |
| `smoothing`, `smoothing_radius` | `none`, `chamfer` or `fillet` at the corners of the fill, and its size | `none`, 0 |
| `fill_mode` | `solid` or `hatched` | `solid` |
| `hatch` | a `ZoneHatch`: `thickness` (1 mm), `gap` (1.5 mm), `orientation` (0), `smoothing_level` (0), `smoothing_value` (`"0.1"`), `border` (`hatch_thickness` or `min_thickness`) and `min_hole_area` (`"0.15"`) | `ZoneHatch()` |

- **Ratios are strings.** `smoothing_value` and `min_hole_area` are decimal strings: the model holds no
  float.
- **Effective settings.** `settings.effective()` returns a copy in which every value that cannot change
  the fill is at its default: `hatch` of a solid fill, `smoothing_radius` without smoothing, and
  `min_island_area` unless `island_removal` is `below_area`. Comparisons and digests use it, so a value
  without effect never counts as a change.
- **`filled` is state, not a setting.** It says that the board holds the result of a fill, which may be
  empty. It does not enter `effective()`.
- **Pads.** `Pad.zone_connection` overrides the zone for one pad. Board pads and library pads carry it
  alike, so a library footprint can make its exposed pad solid in a thermal pour.
- **Old documents.** The four fields have defaults, so a `board.json` written before them still loads.

## Placed copies

Normative text: requirement "Placed copies of library definitions" of the `design-model` capability
and the third case of "Identifier derivation" (change c0017); KiCad facts in
`docs/formats/kicad/board.md` ("Placed footprints").

A backend that places a library definition into a design derives every id of the copy from a key the
caller passes (c0011 passes the component path), never from the seeded generator and never from the
definition's own ids. For KiCad each native id is `uuid5(FENOLITE_NS, "kicad-place:<key>:<locator>")`,
the locator being the node's place in the emitted definition, and the Fenolite ids follow from those
native ids as for any imported object, so a design read back from the written file has the same ids.
Placing again with the same key gives the same ids; two keys share none; adding or removing another
placement changes no id of a copy. The copy records the definition in `FootprintInstance.lib_ref`,
belongs to the caller's component, and its pads have no net until the caller assigns one. The
definition stays unchanged.

## Ids of design scripts

Normative text: the fourth case of requirement "Identifier derivation" of the `design-model`
capability (change c0011); the key table is in `docs/dsl.md` ("Ids: the key table").

Every object that `fenolite.dsl.to_model` or `fenolite build` creates gets
`derived_id(prefix, "dsl", "<kind>:<key>")`, where the key is a name or a path from the script
(`component:<path>`, `net:<name>`, `pin:<path>:<number>`, `rule:<kind>`, …) from the closed table
`dsl.KEYS`.
Footprints and pads are placed copies keyed by the component path (see "Placed copies"), and the
board layers are keyed by their KiCad names. These ids are not generated: they do not depend on
`--seed`, on `PYTHONHASHSEED` or on the order in which the script creates objects, so inserting a part
changes no id of another object, and two builds of one script give byte-identical files.

## Ids of script copper

Normative text: the fifth case of requirement "Identifier derivation" (change c0028); the uuid layout
is in `docs/copper.md` ("Ids and markers").

A track or via created from a copper intent takes the KiCad uuid `copper_uuid(key, locator)` as its
native id, and the id that an imported object with that native id gets:
`derived_id("trk" | "via", "kicad", uuid)`. A design read back from the written board therefore has
the same ids. The key is the intent's key and the locator numbers the item inside that intent, so
adding, removing or reordering intents changes no id, and neither do `--seed` and `PYTHONHASHSEED`.

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
formatter byte for byte. The first backend to implement it is the KiCad board backend. On a write, a
backend changes an opaque child only where one of its requirements says so; the KiCad writer's list
is in the `kicad-slots` requirement "Slot source for model entities" (net references in the target's
form, rows the target no longer writes, slots dropped under `--allow-lossy`, the Reference and Value
atoms, and respelled fields written from changed model values).

## Layout authority

For a design authored in Fenolite, the exported tool project is the source of truth for layout;
`.fenolite/` is a regenerable, git-ignored cache; imported third-party files are kept immutable by
SHA-256 under `native/`.
