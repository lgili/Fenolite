## ADDED Requirements

### Requirement: Graphics and texts of a footprint instance
`FootprintInstance` SHALL hold `graphics: tuple[Graphic, ...]` and `texts: tuple[Text, ...]`, both ordered and `()` by default: the drawings and the free texts that belong to one placed footprint. They are the board's own `Graphic` and `Text` entities; no class, id prefix or literal is added.
- **Frame.** A point of a footprint's graphic or text MUST be in the pad frame of "Board entities read from file backends": its place on the board is `instance.position + R(instance.rotation)·p`, with no further mirror, so a bottom footprint holds mirrored coordinates. `Text.rotation` is relative to the footprint.
- **Layers.** `layer` MUST be the board layer the item lies on: an item of a bottom footprint names the bottom layer.
- **Order.** Both tuples keep the order of their source (file order, record order, definition order), and a writer writes in that order.
- **Reference and Value.** The places of the reference and of the value stay `FootprintInstance.fields` ("Footprint fields"); `texts` holds only texts that are no field, with the string as the source stores it.
- A graphic MAY be of any `GraphicKind` and on any layer, a copper layer included. A consumer that cannot use one MUST count it and say so; it MUST NOT drop it silently.
- **Ids.** An item with a native id has the id that an imported object with that native id gets; an item without one has a content id whose section names its footprint and whose content is in the footprint frame, so moving the footprint changes no id of its items.
- `Design.entities()` and `Design.validate()` MUST cover the items (duplicate ids), and `Design.by_layer` MUST list them under their layer.
- The change MUST be additive. `canonical` omits the defaults, so a design whose footprints hold no item gives the `board.json` bytes it gave before, and a `board.json` without the keys `graphics` and `texts` MUST load with `()`. `SCHEMA_VERSION` stays `"0"`, and `schemas/fenolite.model.v0/board.json` MUST be regenerated with `tools/gen_schemas.py`, with both keys as optional arrays.
- The other direction does not hold, and MUST be said: release 0.2.0 cannot read a model document that carries one of the new keys (`graphics`, `texts`, `corner_ratio`), because its reader refuses an unknown key. `docs/design-model.md` and the changelog MUST hold that sentence.
- A `board.json` that release 0.2.0 wrote MUST be committed as a fixture, `tests/data/model/v0.2.0/blink_2layer.board.json`: built by the code of the tag `v0.2.0` from `examples/blink_2layer/design.py` at that tag, with a fixed seed and timestamp, copied byte for byte, and declared in `tests/data/MANIFEST.toml` with its origin, its command and its SHA-256. It MUST load unchanged and serialise again to its own bytes.

#### Scenario: A design without footprint items keeps its bytes
- **WHEN** `uv run pytest tests/unit/model/test_footprint_items.py -k bytes` dumps the built blink and the board read from `tests/data/kicad/board/two_layer.kicad_pcb` with `canonical.dump_texts`
- **THEN** every text equals the text that the commit before this change gave (digests pinned in the test), and `uv run python tools/gen_schemas.py --check` exits 0

#### Scenario: A document of 0.2.0 loads unchanged
- **GIVEN** `tests/data/model/v0.2.0/blink_2layer.board.json`, the `board.json` that the code of the tag `v0.2.0` wrote for `examples/blink_2layer/design.py`, which holds none of the new keys
- **WHEN** `uv run pytest tests/unit/model/test_footprint_items.py -k v020` loads it with `canonical.loads(text, Board)` and serialises it with `canonical.dumps`
- **THEN** it loads without an error, every footprint has `graphics == ()` and `texts == ()`, every pad has `corner_ratio is None`, and the serialised bytes equal the bytes of the file

#### Scenario: The fixture is declared
- **WHEN** `uv run pytest tests/corpus/test_manifest.py -q` runs
- **THEN** `tests/data/MANIFEST.toml` holds one entry for the fixture, with the tag `v0.2.0`, the build command and the file's SHA-256

#### Scenario: 0.2.0 and the new keys are documented
- **WHEN** `docs/design-model.md` and the `[Unreleased]` section of `CHANGELOG.md` are read after the change is implemented
- **THEN** each holds the sentence that release 0.2.0 cannot read a model document that carries the new keys

#### Scenario: A line of a bottom footprint
- **GIVEN** a footprint at (10 mm, 20 mm), rotated by 90 degrees, on the bottom side, with one `line` graphic from (0, 0) to (1 mm, 0) on `B.SilkS`
- **WHEN** the line is placed with `Transform.placement(position, rotation)`, without a mirror
- **THEN** its ends on the board are (10 mm, 20 mm) and (10 mm, 19 mm), the points at which a pad at the same local points would lie

### Requirement: Corner ratio of a rounded-rectangle pad
`Pad` SHALL hold `corner_ratio: int | None`, `None` by default: the corner radius of a pad of shape `roundrect` in parts per million of the shorter side of `Pad.size`. 250 000 is a quarter of the shorter side.
- The value MUST be an integer from 0 to 500 000. `None` means that the ratio is not known to the model; a pad of another shape MUST have `None`.
- One Altium corner percentage is 5 000 ppm, and a KiCad ratio `r` is `r · 1 000 000`, rounded half to even when `r` has more than six decimals. No float and no decimal string is stored.
- `Design.validate()` MUST report `model.corner-ratio` (error), with `where` set to the pad's id, for a value outside the range and for a value on a pad whose shape is not `roundrect`. The code MUST have an entry in `src/fenolite/cli/data/explain.toml`.
- A library pad (`FootprintDef.pads`) carries the field alike; `schemas/fenolite.model.v0/library.json` MUST be regenerated.
- The field is additive as "Graphics and texts of a footprint instance" says: omitted at its default, and a document without the key loads with `None`.

#### Scenario: Percentages are exact
- **WHEN** `uv run pytest tests/unit/model/test_footprint_items.py -k corner` converts every percentage from 0 to 100 to ppm and back
- **THEN** each comes back unchanged, and the KiCad ratios `0.25`, `0.1` and `0.208333` give 250 000, 100 000 and 208 333

#### Scenario: A ratio on a rectangle
- **GIVEN** a design with one pad of shape `rect` and `corner_ratio == 250_000`, and one `roundrect` pad with `corner_ratio == 600_000`
- **WHEN** `Design.validate()` runs
- **THEN** it reports two `model.corner-ratio` errors, each with the id of its pad

### Requirement: Models without footprint items
A consumer of a design whose footprints hold no graphic and no text, and whose rounded pads hold no ratio, SHALL do what it did before the fields existed. Such a design is every model document written before change c0126 and every design read from a KiCad file without the projection of `kicad-file-backend`, "Footprint items projected on request".
- The library of a footprint needs no field of its own: `FootprintInstance.lib_ref` MUST stay the one reference, `<library>:<name>` or the bare name. A backend that needs a library definition (the Altium build, for the footprints of a PCB library) takes it from its caller.
- The KiCad readers and writers MUST NOT fill or read the three fields except through that projection: `read_board`, `read_footprint`, `place_footprint` and `write_board` give the designs and the texts they gave in release 0.2.0.
- The Altium build falls back to the library definition for what an instance does not hold (`altium-build`, "Altium build through the lowering").

#### Scenario: A KiCad read is unchanged
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fpitems.py -k unchanged` reads every board under `tests/data/kicad/board/` with `read_board`
- **THEN** no footprint holds a graphic or a text, no pad holds a ratio, and `canonical.dumps` of each design is the text that the commit before this change gave (digests pinned in the test)
