## ADDED Requirements

### Requirement: Schematic sheet definitions
`fenolite.model.schematic` SHALL provide the schematic-sheet definition `SchematicSheet`, an entity with the common header, and the entities and value objects it holds:
- `SchematicSheet(name, paper, title_block, lib_symbols, symbols, labels, no_connects, sheets, pages)`: `paper` is a `SheetFrameRef` (default `SheetFrameRef("A4")`), `title_block` a `TitleBlock` or `None`, `lib_symbols` a tuple of `SymbolDef`, and the other collections tuples of the types below;
- `SymbolInstance(lib_ref, position, rotation=0, mirror="", unit=1, body_style=1, ref="", value="", footprint="", properties={}, dnp=False, in_bom=True, on_board=True, exclude_from_sim=False, lib_name="", uses=())`, an entity: `mirror` in `"" | "x" | "y"`, and `uses` a tuple of `SymbolUse(project, path, ref, unit=1)`;
- `NetLabel(kind, name, position, rotation=0, shape="")`, an entity: `kind` in `local | global | hierarchical`, `shape` in `"" | input | output | bidirectional | tri_state | passive`;
- `NoConnectFlag(position)`, an entity;
- `SheetRef(name, file, position, size, uses=())`, an entity, with `uses` a tuple of `SheetUse(project, path, page)`;
- `SheetPage(path, page)`.

These rules MUST hold:
- Every entity and value object MUST be immutable. Positions MUST be `Point` in integer nm and rotations integer µdeg; no field MAY be a float.
- `SymbolInstance.rotation` MUST be 0, 90 000 000, 180 000 000 or 270 000 000.
- `NetLabel.kind` MUST have no default, so the canonical form always writes it.
- `lib_symbols`, `symbols`, `labels`, `no_connects`, `sheets`, `pages` and `uses` MUST be marked ordered, so the canonical form keeps file order. `properties` MUST be sorted by key in the canonical form.
- A `SchematicSheet` MUST NOT be part of `Design` or of the `.fenolite/` layer files: a generated sheet is derived from the circuit, and a sheet read from a file is checked and compared, not imported.
- `fenolite.model.schematic` MUST import only `core` and `model`.

#### Scenario: Canonical round trip keeps order
- **GIVEN** a `SchematicSheet` built in the test with two symbol instances, three labels of the three kinds and one no-connect flag, each with only its required fields set
- **WHEN** it is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the loaded sheet equals the original, and every collection keeps its order

#### Scenario: Label kind is always written
- **WHEN** a `NetLabel("local", "N1", Point(0, 0))` is dumped with `canonical.dumps`
- **THEN** the text holds `"kind": "local"`

#### Scenario: Sheets are not layer content
- **GIVEN** a design built for the blink example
- **WHEN** `canonical.dump_dir` writes it
- **THEN** the same six layer files are written, and none of them contains a `SchematicSheet`

#### Scenario: Model stays backend-free
- **GIVEN** a version of `src/fenolite/model/schematic.py` that imports `fenolite.backends`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it fails naming `model → backends`

### Requirement: Identifiers of schematic entities
The closed prefix table SHALL include `sch` (schematic sheet), `sci` (symbol instance), `lbl` (label), `ncf` (no-connect flag) and `shr` (sheet reference).
- An entity read from a file MUST have the id `derived_id(<prefix>, <backend>, <native id>)`, the native id being the one its backend names (`kicad-schematic`, "Identifiers of schematic items").
- An entity that Fenolite creates for a design MUST have an id derived from the design, so two builds of one design give equal ids: the sheet `derived_id("sch", "fenolite", "<design name>")`, and each entity `derived_id(<prefix>, "fenolite", "<design name>:<key>")`, where `<key>` is stated by the change that creates it.
- `SymbolUse`, `SheetUse` and `SheetPage` MUST carry no ids.

#### Scenario: Prefixes accepted
- **WHEN** `new_id` is called with each of `sch`, `sci`, `lbl`, `ncf` and `shr` and `random.Random(1)`
- **THEN** each returns an id that starts with its prefix, and `new_id("scx", random.Random(1))` raises `ValueError`

#### Scenario: Same uuid, same id
- **WHEN** `tests/data/kicad/schematic/flat.kicad_sch` is read twice
- **THEN** both sheets have the id `derived_id("sch", "kicad", <the root uuid of the file>)`

### Requirement: Schematic sheet schema
`tools/gen_schemas.py` SHALL generate `schemas/fenolite.model.v0/schematic.json` with schema id `fenolite.schematic.v0` from `fenolite.model.schematic.SchematicSheet`. The schema drift test MUST cover it, and `canonical.dumps`/`canonical.loads` MUST round-trip a `SchematicSheet` idempotently.

#### Scenario: Schema drift detected
- **GIVEN** a contributor adds a field to `SymbolInstance` without regenerating schemas
- **WHEN** `uv run pytest tests/unit/test_schema_drift.py` runs
- **THEN** it fails naming `schematic.json`

#### Scenario: Float rejected in a sheet document
- **GIVEN** a `schematic.json` document where `symbols[0].position.x` is `1.5`
- **WHEN** it is validated against the schematic schema with `tests/_schema.py`
- **THEN** validation fails with a message naming `/symbols/0/position/x`

#### Scenario: Schemas up to date
- **WHEN** `uv run python tools/gen_schemas.py --check` runs
- **THEN** it exits 0
