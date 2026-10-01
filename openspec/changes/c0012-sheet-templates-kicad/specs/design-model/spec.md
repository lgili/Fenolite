## MODIFIED Requirements

### Requirement: Model layers for v0.1
The model SHALL provide the `circuit` layer (`Component`, `Pin`, `Net`, `NetClass`, `Interface`, `Module`), the `board` layer (`Board`, `Layer`, `Stackup`, `StackLayer`, `FootprintInstance`, `Pad`, optional minimal `Padstack`, `Track`, `Arc`, `Via`, `Zone`, `Keepout`, `Text`, `Graphic`, `Hole`, `Outline`), the `rules` layer (`Rule`, `RuleSet`, selector algebra `all | net | netclass | ref | layer | item_kind | and | or | not`, kinds `clearance`, `track_width`, `via_diameter`, `via_drill`, `hole_size`, `edge_clearance`), the `manufacturing` layer (`Manifest`, `PnpRow`) and the `findings` layer (`Issue`), aggregated by `Design` with read-only indexes `by_id`, `by_ref`, `by_net`, `by_layer`.

The model SHALL also provide the `presentation` module `fenolite.model.presentation`:
- the value objects `TitleBlock` (`title`, `date`, `revision`, `organization`, `doc_id`, `responsible`, `approver`, all `""` by default, and `params`, a mapping of parameter name to text, empty by default) and `SheetFrameRef` (`paper`, one of `A0` … `A5`, `Letter`, `Legal`, `Tabloid` and `custom`, default `A4`; `portrait`, default false; `width` and `height` in nm, used only by `custom`; `drawing_sheet`, a project-relative path or `None`);
- `Board.title_block: TitleBlock | None` and `Board.sheet: SheetFrameRef | None`, both defaulting to `None`, stored in `board.json`;
- the definition `DrawingSheet` and its items, which are not part of `Design` and not stored in the `.fenolite/` layer files (requirement "Drawing sheet definitions").

The six layer files keep their names, and the circuit, rules, manufacturing and findings layers and the `Design` indexes are unchanged.

#### Scenario: Indexes resolve
- **GIVEN** a design with component `R1` on net `GND`
- **WHEN** `design.by_ref["R1"]` and `design.by_net["GND"]` are read
- **THEN** the component and the set of pads on `GND` are returned

#### Scenario: Duplicate reference is a finding
- **GIVEN** two components with `ref = "R1"`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.duplicate-ref` and severity `error` is produced

#### Scenario: Board carries the sheet and title block
- **GIVEN** a `Board` with `sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")` and `title_block = TitleBlock(title="Bench", params={"LOT": "7"})`
- **WHEN** the design is written with `canonical.dump_dir` and loaded again with `canonical.load_dir`
- **THEN** the loaded board's `sheet` and `title_block` equal the originals, and `board.json` holds both under the keys `sheet` and `title_block`

#### Scenario: Board documents without presentation fields load
- **GIVEN** a `board.json` written before this change, without the keys `sheet` and `title_block`
- **WHEN** it is loaded with `canonical.loads` and validated against the regenerated `board.json` schema
- **THEN** loading succeeds, validation passes, and `board.sheet` and `board.title_block` are `None`

## ADDED Requirements

### Requirement: Drawing sheet definitions
`fenolite.model.presentation` SHALL provide the drawing-sheet definition `DrawingSheet(name, setup, items)`, an entity with the common header, and its value objects:
- `SheetSetup(text_size, line_width, text_line_width, left_margin, right_margin, top_margin, bottom_margin)`;
- `SheetPoint(corner="rb", x=0, y=0)`: an offset from the named corner (`lt`, `lb`, `rt`, `rb`) of the margin box, which is the page minus the setup margins, positive toward the interior;
- `SheetRepeat(count=1, step_x=0, step_y=0, label_step=1)`: `label_step` defaults to 1, the value KiCad uses when `incrlabel` is absent (`H-K-WKS-REPEAT`);
- the items `SheetShape` (`kind` in `line | rect`, required, `start`, `end`, `width=None`), `SheetText` (`text`, `pos`, `size=None`, `bold`, `italic`, `justify` in `left | center | right`, `vjustify` in `top | center | bottom`, `rotation` in µdeg, `max_len`, `max_height`) and `SheetBitmap` (`pos`, `png` as base64 text, `scale_ppm=1_000_000`), each with `repeat`, `scope` in `all | first_only | not_first`, `name` and `comment`.

These rules MUST hold:
- Every definition and value object MUST be immutable. Lengths MUST be integer nm, angles integer µdeg and the bitmap scale integer parts per million; no field MAY be a float.
- `DrawingSheet.items` MUST be marked ordered, so the canonical form keeps the drawing order.
- The item union MUST decode without ambiguity, because `canonical.loads` takes the first union member that decodes and the canonical form leaves out default values. `SheetShape.kind` MUST have no default, as `Graphic.kind` has none, so it is always written; `SheetText` and `SheetBitmap` differ by their required fields (`text`, `png`).
- A `DrawingSheet` MUST NOT be part of `Design` or of the `.fenolite/` layer files: one sheet serves many boards and sizes.
- Texts MUST hold only neutral tokens. `SHEET_TOKENS` SHALL be `title`, `doc_id`, `revision`, `sheet`, `sheets`, `date`, `organization`, `responsible`, `approver`, `filename` and `paper`. `split_tokens(text)` SHALL split a text into literal strings and `SheetToken(name, param=False)` values, reading `{name}` for a name of `SHEET_TOKENS`, `{param:NAME}` for a name matching `[A-Za-z_][A-Za-z0-9_]*`, and `{{` and `}}` as literal braces. It MUST raise `ValueError` for an unknown or malformed token. Every `SheetText.text` that a builder or reader produces MUST be accepted by `split_tokens`.
- `PAPER_SIZES` SHALL map `A0` … `A5`, `Letter`, `Legal` and `Tabloid` to their portrait width and height in nm: A0 to A4 from S-0077, A5 and the US sizes from S-0079, with inches converted at exactly 25.4 mm.

#### Scenario: Tokens split
- **WHEN** `split_tokens("Rev {revision} lot {param:LOT_NO} {{x}}")` is called
- **THEN** it returns `("Rev ", SheetToken("revision"), " lot ", SheetToken("LOT_NO", param=True), " {x}")`

#### Scenario: Unknown token refused
- **WHEN** `split_tokens("{owner}")` and `split_tokens("{param:9X}")` are called
- **THEN** each raises `ValueError` naming the token

#### Scenario: Paper sizes are exact
- **WHEN** `PAPER_SIZES["A4"]`, `PAPER_SIZES["Letter"]` and `PAPER_SIZES["Tabloid"]` are read
- **THEN** they are `(210_000_000, 297_000_000)`, `(215_900_000, 279_400_000)` and `(279_400_000, 431_800_000)`

#### Scenario: Item order survives the canonical form
- **GIVEN** a `DrawingSheet` whose items are a `SheetText`, a `SheetShape` of kind `rect`, a `SheetShape` of kind `line` and a `SheetBitmap`, in that order, each with only its required fields set
- **WHEN** it is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the items keep that order, each loaded item has the type and `kind` of its original, and the loaded sheet equals the original

#### Scenario: Sheets are not layer content
- **GIVEN** a design whose board has `sheet = SheetFrameRef("A4", drawing_sheet="frame.kicad_wks")`
- **WHEN** `canonical.dump_dir` writes it
- **THEN** the same six layer files are written and none of them contains a `DrawingSheet`

### Requirement: Identifiers of drawing sheets
The closed prefix table SHALL include `wks` (drawing sheet).
Both ids below are the case "imported objects with a native id" of "Identifier derivation", which this change does not modify: the `<backend>` part names the source format, and the native id is a name that the source file declares, as library names are for definitions read from a library.
- A sheet built from a `*.sheet.toml` specification comes from that file, whose `sheet.name` is its native id: its id MUST be `derived_id("wks", "template", <sheet.name>)`.
- A sheet read from a KiCad file MUST have the id `derived_id("wks", "kicad", <name>)`, where `<name>` is the `name` argument of the reader or, when it is `None`, the file stem (`""` for text read without a file name).
- Sheet items, `TitleBlock` and `SheetFrameRef` MUST carry no ids.

#### Scenario: Same name, same id
- **WHEN** `tests/data/kicad/sheets/all_items.kicad_wks` is read twice
- **THEN** both sheets have the id `derived_id("wks", "kicad", "all_items")`

#### Scenario: Prefix accepted
- **WHEN** `new_id("wks", random.Random(1))` is called
- **THEN** it returns an id starting with `wks_`, and `new_id("wkx", random.Random(1))` raises `ValueError`

### Requirement: Drawing sheet schema
`tools/gen_schemas.py` SHALL generate `schemas/fenolite.model.v0/drawing_sheet.json` with schema id `fenolite.drawing_sheet.v0` from `fenolite.model.presentation.DrawingSheet`, and SHALL regenerate `board.json` with the optional `sheet` and `title_block` fields. The schema drift test MUST cover `drawing_sheet.json`, and `canonical.dumps`/`canonical.loads` MUST round-trip a `DrawingSheet` idempotently.

#### Scenario: Schema drift detected
- **GIVEN** a contributor adds a field to `SheetText` without regenerating schemas
- **WHEN** `uv run pytest tests/unit/test_schema_drift.py` runs
- **THEN** it fails naming `drawing_sheet.json`

#### Scenario: Float rejected in a sheet document
- **GIVEN** a `drawing_sheet.json` document where `items[0].pos.x` is `1.5`
- **WHEN** it is validated against the drawing-sheet schema
- **THEN** validation fails with a message naming `/items/0`, the pointer of the union item that matches no alternative (the repository validator `tests/_schema.py` reports an `anyOf` failure at the union node)

#### Scenario: Schemas up to date
- **WHEN** `uv run python tools/gen_schemas.py --check` runs
- **THEN** it exits 0

### Requirement: Presentation values are validated
`Design.validate()` SHALL report these errors for the presentation fields of the board:

| code | severity | when |
|---|---|---|
| `model.sheet-path` | error | `Board.sheet.drawing_sheet` is an absolute path (a leading `/` or `\`, or a drive letter) or holds a `..` segment |
| `model.sheet-size` | error | `custom` without both `width` and `height`; `width` or `height` set on a named size; `portrait` set on `custom`; or a `custom` size equal, in either orientation, to `Letter`, `Legal` or `Tabloid` |
| `model.param-name` | error | a key of `TitleBlock.params` that does not match `[A-Za-z_][A-Za-z0-9_]*` |

`drawing_sheet` MAY be a POSIX path relative to the project or start with `${KIPRJMOD}/`.

#### Scenario: Absolute sheet path
- **GIVEN** a board with `sheet = SheetFrameRef("A4", drawing_sheet="/srv/frames/frame.kicad_wks")`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.sheet-path` and severity `error` is produced

#### Scenario: Custom size equal to Letter
- **GIVEN** a board with `sheet = SheetFrameRef("custom", width=279_400_000, height=215_900_000)`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.sheet-size` is produced

#### Scenario: Bad parameter name
- **GIVEN** a board with `title_block = TitleBlock(params={"LOT NO": "7"})`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.param-name` naming `LOT NO` is produced

#### Scenario: Valid presentation
- **GIVEN** a board with `sheet = SheetFrameRef("A3", drawing_sheet="${KIPRJMOD}/frame.kicad_wks")` and `title_block = TitleBlock(params={"LOT_NO": "7"})`
- **WHEN** `design.validate()` runs
- **THEN** no `model.sheet-*` or `model.param-name` issue is produced
