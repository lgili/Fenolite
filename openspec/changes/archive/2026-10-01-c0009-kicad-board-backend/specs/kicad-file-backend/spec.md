## ADDED Requirements

### Requirement: Board file reading
`fenolite.backends.kicad.pcb.read_board(source, *, file="", issues=None)` SHALL accept an `os.PathLike` (a `.kicad_pcb` file), a `str` (file text) or a parsed `Node`, and SHALL return a `Design`.
- `header.name` MUST be the file stem for a path and `""` otherwise.
- `board` MUST hold the board entities, and `circuit` the synthesised components and nets. `rules` and `manufacturing` MUST be `None`.
- Warnings and infos MUST be appended to `issues` when a list is given. Errors MUST be raised.
- A root other than `kicad_pcb` MUST raise `FormatError` with the locator of the root.

#### Scenario: Authored board read from a path
- **GIVEN** `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `read_board(Path(...), issues=issues)` is called
- **THEN** `header.name == "two_layer"`, the board has 2 footprints, 3 tracks, 1 arc, 1 via, 1 zone, 1 keepout, 6 graphics and 1 text, and no issue in `issues` has severity `error`

#### Scenario: Foreign root
- **WHEN** `read_board('(footprint "X" (version 20260206) (generator "t") (layer "F.Cu"))')` is called
- **THEN** `FormatError` is raised with `locator == "/footprint"`

### Requirement: Board version policy
`read_board` MUST follow the read path of `kicad-version-gating`. It MUST call `versions.inspect` and `versions.require_readable` on the root, and MUST append `versions.version_issues` of the result to `issues`.
- Boards of 8.0, 9.0 and 10.0, development versions included, SHALL be read.
- Older boards MUST raise `UnsupportedFormatError` (`FEN-3003`) whose hint names `kicad-cli pcb upgrade`.
- Newer boards SHALL be read with the warning `kicad.version.future`. Every opaque fragment of such a board MUST carry the file version as its minimum version, so that `versions.require_editable` blocks edits and no writer can emit it for a known target.

#### Scenario: KiCad 7 board refused
- **GIVEN** a board with `(version 20221018)`
- **WHEN** it is read
- **THEN** `UnsupportedFormatError` is raised and its hint contains `kicad-cli pcb upgrade`

#### Scenario: KiCad 8 board read
- **GIVEN** `tests/data/kicad/tokens/old/old.kicad_pcb` (`20240108`)
- **WHEN** it is read
- **THEN** a `Design` is returned whose board holds one `Graphic` of kind `rect` on `Edge.Cuts`, and no issue has severity `error`

#### Scenario: Future board read but not editable
- **GIVEN** the authored board with its header changed to `(version 20990101)`
- **WHEN** it is read with an `issues` list
- **THEN** `issues` holds one warning `kicad.version.future`, every opaque slot carries minimum version `20990101`, and `versions.require_editable(versions.inspect(node))` raises `FutureFormatError`

### Requirement: Layer table and layer kinds
The reader SHALL turn each row `(N "name" type ["user name"])` of the `layers` child into a `Layer` and SHALL keep the rows in `Board.layers` in file order.
- `name` MUST be the canonical name, and `ordinal` MUST be the row index.
- `kind` MUST come from `fenolite.backends.kicad.layers.layer_kind(name, row_type)`:
  - `F.Cu`, `B.Cu` and `In<n>.Cu` → `copper`
  - `*.SilkS` → `silkscreen`, `*.Mask` → `soldermask`, `*.Paste` → `solderpaste`
  - `*.CrtYd` → `courtyard`, `*.Fab` → `fabrication`
  - `Edge.Cuts` → `edge`
  - `Margin` and `*.Adhes` → `mechanical`
  - `Dwgs.User`, `Cmts.User`, `Eco1.User`, `Eco2.User` and `User.<n>` → `user`
  - any other name → `copper` when the row type is `signal`, `power`, `mixed` or `jumper`, and `user` otherwise
- `layers.is_canonical(name)` MUST be true only for names matched by the list above, without the last fallback.
- N, the type and the user name MUST be kept in `Layer.ext["kicad"]` as the pairs `number`, `type` and `user_name`.
- Items MUST keep canonical KiCad layer names.

#### Scenario: Copper rows of the authored board
- **WHEN** the authored board is read
- **THEN** `F.Cu` has `kind == "copper"` and `ordinal == 0`, `B.Cu` has `kind == "copper"` and `ordinal == 1`, and the `kicad` bag of `B.Cu` holds the pair `("number", "2")`

#### Scenario: Inner and unknown layers
- **WHEN** `layer_kind("In3.Cu")`, `layer_kind("User.4")`, `layer_kind("F.Adhes")` and `layer_kind("Foo", "signal")` are called
- **THEN** they return `copper`, `user`, `mechanical` and `copper`

#### Scenario: Canonical names
- **WHEN** `is_canonical("In3.Cu")`, `is_canonical("Edge.Cuts")` and `is_canonical("Foo")` are called
- **THEN** they return `True`, `True` and `False`

### Requirement: Modelled board content
The reader SHALL model exactly these root children and leave every other one as an opaque slot:
- the header (`version`, `generator`, `generator_version`), whose values are kept in `Board.ext["kicad"]` as the pairs `version`, `generator` and `generator_version`;
- `layers`, and the net table rows with N ≥ 1;
- `footprint` → `FootprintInstance`, `segment` → `Track`, `arc` → `Arc`, `via` → `Via`;
- `zone` → `Zone`, or `Keepout` for a rule area; a teardrop zone (an `attr` child holding `teardrop`) MUST stay an opaque root slot;
- `gr_line`, `gr_arc`, `gr_circle`, `gr_rect` and `gr_poly` → `Graphic` of kind `line`, `arc`, `circle`, `rect` and `polygon`, with the c0008 rules for points, fill and stroke;
- `gr_text` → `Text`, with `size` and `thickness` projected from `effects/font`. A `gr_text` without a font size or thickness MUST stay opaque.

Via fields MUST be `position`, `diameter` (from `size`), `drill`, `layers`, `net_id`, and `via_type` from the leading atom (`blind`, `buried` or `micro`; `through` when absent). Any other leading atom MUST raise `FormatError`. `Board.outline` and `Board.stackup` MUST be `None` on import. Edge.Cuts content MUST stay ordinary `Graphic`s on layer `Edge.Cuts`.

#### Scenario: Copper items of the authored board
- **WHEN** the authored board is read
- **THEN** it has 3 `Track`s, 1 `Arc` and 1 `Via` with `via_type == "through"`, `layers == ("F.Cu", "B.Cu")` and the net GND

#### Scenario: Blind via
- **GIVEN** a board holding `(via blind (at 1 1) (size 0.6) (drill 0.3) (layers "F.Cu" "In1.Cu") (net 1) (uuid "…"))`
- **WHEN** it is read
- **THEN** the via has `via_type == "blind"` and `layers == ("F.Cu", "In1.Cu")`

#### Scenario: Edge graphics are authoritative
- **WHEN** the authored board is read
- **THEN** `board.outline is None` and exactly four `Graphic`s of kind `line` are on layer `Edge.Cuts`

#### Scenario: Text from gr_text
- **WHEN** the authored board is read
- **THEN** its single `Text` has `text == "FENOLITE"`, layer `F.SilkS`, and integer `size` and `thickness` from the font

#### Scenario: Teardrop zone stays opaque
- **GIVEN** a board holding a zone with `(attr (teardrop (type padvia)))`
- **WHEN** it is read
- **THEN** no `Zone` is created for it, and the zone is an `Opaque` slot of the board at its position

### Requirement: Board footprints and the pad frame
Each `footprint` SHALL become a `FootprintInstance`:
- `lib_ref` comes from the name atom, and `position` and `rotation` from `at`, as stored on both sides (a bottom rotation is not converted);
- `side` is `bottom` when `layer` is `B.Cu`, and `top` otherwise;
- `locked` is projected from a `locked` atom or `(locked yes)`;
- `attributes` holds the `attr` atoms in file order.

Pads MUST be mapped by the shared footprint mapping with root chain `("kicad_pcb", "footprint")`.
- `Pad.position` MUST be the stored footprint-local position, so that the absolute position is `instance.position + R(instance.rotation)·pad.position` with no further mirror.
- `Pad.rotation` MUST be `pad_angle_from_board(stored, instance.rotation)`, that is `(stored − footprint) mod 360°`.
- `pad_angle_to_board(relative, footprint)` MUST return `(relative + footprint) mod 360°` in [0°, 360°).
- `Pad.layers` MUST be the actual board layers. `*.Cu` expands to every copper row of `layers`, and `*.X` and `F&B.X` expand to `F.X` and `B.X`. A `layers` child with a wildcard MUST be a projected slot.
- `Pad.net_id` MUST come from the pad's `net`.

#### Scenario: Top footprint at 90 degrees
- **WHEN** the authored board is read
- **THEN** `R1` has `position == Point(20_000_000, 15_000_000)`, `rotation == 90_000_000`, `side == "top"`, `attributes == ("smd",)`, and both pads have `rotation == 0`

#### Scenario: Bottom footprint keeps stored coordinates
- **WHEN** the authored board is read
- **THEN** `D1` has `side == "bottom"` and `rotation == 30_000_000`, and its pad `"2"` has `position == Point(2_540_000, -1_000_000)`, `rotation == 0` and `layers == ("F.Cu", "B.Cu", "F.Mask", "B.Mask")`

#### Scenario: Angle pair round trip
- **WHEN** `pad_angle_to_board(pad_angle_from_board(s, f), f)` is computed for every stored angle `s` in [0°, 360°) used by the authored board and footprint angles 0°, 30°, −90° and 270°
- **THEN** it equals `s`

#### Scenario: Unknown attribute atom
- **GIVEN** a footprint with `(attr smd frobnicate)`
- **WHEN** it is read with an `issues` list
- **THEN** `attributes == ("smd",)`, the `attr` child is an `Opaque` slot, and `issues` holds one info `kicad.board.kept-opaque`

### Requirement: Nets in both forms
The reader SHALL accept net references in both forms, decided per reference by its first atom:
- **Numbered form.** Table rows `(net N "name")` with N ≥ 1 MUST become `Net` entities in table order, with N kept in `Net.ext["kicad"]` as the pair `("number", "<N>")`. Row 0 MUST stay an opaque slot. `(net N "name")` and `(net N)` references MUST resolve through the table.
- **Name form.** `(net "name")` references MUST create a `Net` per distinct name, in the order of first reference.

Net 0 and the empty name MUST give `net_id = None`. A number absent from the table MUST give `net_id = None`, keep the reference as an `Opaque` slot, and add the warning `kicad.board.unknown-net`. A zone's `net_name` MUST stay opaque. `Net.netclass_id` MUST be `None`.

#### Scenario: Numbered table
- **WHEN** the authored board is read
- **THEN** `circuit.nets` are `GND`, `VCC` and `LED_A` in that order, with numbers `1`, `2` and `3` in their `kicad` bags

#### Scenario: Name form
- **GIVEN** a `20260206` board whose only item is `(segment (start 0 0) (end 1 0) (width 0.25) (layer "F.Cu") (net "GND") (uuid "…"))`
- **WHEN** it is read
- **THEN** `circuit.nets` holds one net `GND`, and the track's `net_id` is its id

#### Scenario: Unknown net number
- **GIVEN** a `20241229` board with `(net 0 "")` and `(net 1 "A")` whose segment holds `(net 7)`
- **WHEN** it is read with an `issues` list
- **THEN** the track's `net_id` is `None`, its `net` child is an `Opaque` slot, and `issues` holds one warning `kicad.board.unknown-net` naming 7

### Requirement: Zones, fills and rule areas
A `zone` with a `keepout` child SHALL become a `Keepout`, and every other non-teardrop zone a `Zone`.
- `Keepout` takes `no_tracks`, `no_vias`, `no_pads`, `no_copper_pour` and `no_footprints` from the `keepout` settings, where `not_allowed` means true.
- `Zone` takes `name`, `priority`, `layers` (from `layer` or `layers`) and `net_id`.
- `Zone.layers` and `Keepout.layers` MUST be actual board layers. Wildcards expand as for pads (`*.Cu` to every copper row, `*.X` and `F&B.X` to `F.X` and `B.X`), and a `layers` child with a wildcard MUST be a projected slot.
- One points-only `polygon` MUST become the outline.
- A `polygon` whose `pts` holds an `arc`, or a zone with several `polygon` children, MUST give `outline == ()`. Every `polygon` child then stays an `Opaque` slot, with the info `kicad.board.zone-outline-opaque`.
- Each `filled_polygon` MUST become one `ZoneFill(layer, polygon, island)`, in file order, several per layer allowed. `island` MUST be true for the bare `(island)` and for `(island yes)`, and false for `(island no)` or no flag.

#### Scenario: Zone with an island fill
- **WHEN** the authored board is read
- **THEN** zone `GND_B` has `layers == ("B.Cu",)`, the net GND, `priority == 0` and two fills on `B.Cu`, of which only the second has `island == True`

#### Scenario: Rule area
- **WHEN** the authored board is read
- **THEN** its `Keepout` has `no_tracks` and `no_vias` true, `no_pads`, `no_copper_pour` and `no_footprints` false, and `layers == ("F.Cu",)`

#### Scenario: Arc in a zone outline
- **GIVEN** a zone whose `polygon` `pts` holds `(arc (start 0 0) (mid 1 1) (end 2 0))`
- **WHEN** it is read with an `issues` list
- **THEN** the zone has `outline == ()`, its `polygon` child is an `Opaque` slot, and `issues` holds one info `kicad.board.zone-outline-opaque`

#### Scenario: Wildcard rule-area layers
- **GIVEN** a board whose copper rows are `F.Cu`, `In1.Cu` and `B.Cu`, holding a rule area with `(layers "*.Cu")`
- **WHEN** it is read
- **THEN** the `Keepout` has `layers == ("F.Cu", "In1.Cu", "B.Cu")`, and its `layers` child is an `Opaque` slot

#### Scenario: Ten-format island flags
- **GIVEN** a `20260206` zone with two fills marked `(island yes)` and `(island no)`
- **WHEN** it is read
- **THEN** the fills have `island` true and false

### Requirement: Unmodelled board content is kept as slots
The reader MUST record the slot list of the board root in `Board.ext["kicad"]`, and the slot list of every modelled item (footprint, pad, track, arc, via, zone, keepout, graphic, text) in its own `ext["kicad"]`, using the encoding of `kicad-slots`.
- Every child of a modelled item that is not modelled MUST be an `Opaque` slot at its position.
- A projected child MUST be an `Opaque` slot whose value is also copied into the model. This covers properties, the footprint lock, wildcard pad, zone and rule-area layers, padstacks, offset drills, strokes, text effects, `pinfunction` and `pintype`.
- Opaque fragments MUST carry the minimum version that `_libread.Context.min_version` gives for root chain `("kicad_pcb", …)`, and the file version when the inventory has no row for the fragment's head.

#### Scenario: Unknown root child survives in place
- **GIVEN** the authored board with `(frobnicate 1)` inserted as the fifth child of the root
- **WHEN** it is read and `slots.from_ext(board.ext["kicad"])` is inspected
- **THEN** the fifth slot is `Opaque("(frobnicate 1)", "20241229")`

#### Scenario: Footprint property is projected
- **WHEN** the authored board is read
- **THEN** the component of `R1` has `ref == "R1"`, and the `property "Reference"` child of the footprint is an `Opaque` slot including its `effects`

### Requirement: Modelled children are reproducible
After mapping an item, the reader SHALL re-emit every modelled child that maps to values (not to nested entities) through `pcb.model_source` and compare it with the original child.
- A child that the emitter does not reproduce tree-equal MUST become an `Opaque` slot. Its value MUST stay projected into the model, and the reader MUST add the info `kicad.board.kept-opaque` naming the reason.
- Emitters MUST write lengths with `Atom.from_nm`, angles as the shortest exact decimal of degrees, and strings with `Atom.string`. They MUST omit a zero footprint or pad angle, and MUST always write the angle of a text, as KiCad does (the corpus boards write `(at X Y 0)` for texts).

#### Scenario: Non-canonical spelling
- **GIVEN** a segment with `(start 12.000000 0)`
- **WHEN** it is read with an `issues` list
- **THEN** the track has `start == Point(12_000_000, 0)`, its `start` child is an `Opaque` slot with fragment `(start 12.000000 0)`, and `issues` holds one info `kicad.board.kept-opaque`

#### Scenario: Canonical children stay modelled
- **WHEN** the authored board is read
- **THEN** every `start`, `end`, `width`, `layer`, `net` and `uuid` child of its tracks is a `Modeled` slot

### Requirement: Exact numbers on boards
Lengths SHALL be read with `Atom.to_nm(exact=True)` and angles with `core.units.parse_angle`, and the reader MUST NOT round.
- A value that is not a whole number of nm or µdeg MUST leave opaque the smallest item that the model can still build without it. That is the child when the field is optional, and otherwise the whole item: a pad within its footprint, a root item within the board.
- The reader MUST add the info `kicad.board.inexact-length` or `kicad.board.inexact-angle` naming the locator.

#### Scenario: Sub-nanometre track
- **GIVEN** a segment with `(start 0.0000001 0)`
- **WHEN** the board is read with an `issues` list
- **THEN** no `Track` is created for it, the segment is an `Opaque` slot of the root at its position, and `issues` holds one info `kicad.board.inexact-length`

#### Scenario: Unrepresentable footprint angle
- **GIVEN** a footprint with `(at 10 10 30.0000001)`
- **WHEN** the board is read with an `issues` list
- **THEN** no `FootprintInstance` or `Component` is created for it, the footprint is an `Opaque` slot of the root, and `issues` holds one info `kicad.board.inexact-angle`

### Requirement: Identifiers of board items
Board ids SHALL follow the `design-model` rules with these native ids:
- footprint `<fp uuid>`; component `fp:<fp uuid>`; pin `<fp uuid>:pin:<number>`;
- pad `<fp uuid>:<pad uuid>`; padstack `<fp uuid>:<pad uuid>:padstack`;
- net `net:<name>`; layer `layer:<canonical name>`;
- tracks, arcs, vias, zones, keepouts, graphics and texts: their `uuid`;
- design header and board: `kicad_pcb`.

An item without a uuid MUST use `content_id(<prefix>, "kicad", "kicad_pcb", <head>, content_hash(<compact text>, <occurrence>))`. A uuid already used in the file MUST take the occurrence suffix `"<uuid>:<k>"` for its k-th repetition, and the reader MUST add the warning `kicad.board.duplicate-uuid`. KiCad uuids MUST be kept in `native_ids["kicad"]`.

#### Scenario: Stable ids across reads
- **WHEN** the authored board is read twice
- **THEN** every id of the two designs is equal, and `design.validate()` reports no `model.duplicate-id`

#### Scenario: Repeated uuid
- **GIVEN** two segments that carry the same uuid `U`
- **WHEN** the board is read with an `issues` list
- **THEN** the tracks have ids `derived_id("trk", "kicad", "U")` and `derived_id("trk", "kicad", "U:1")`, both keep `U` as native id, and `issues` holds one warning `kicad.board.duplicate-uuid`

### Requirement: Board read issue codes
`read_board` SHALL report problems only with the codes of this closed table, plus the `kicad.version.*` codes of `kicad-version-gating`. `pcb.ISSUE_CODES` MUST map each code to its severity. On boards, the shared footprint mapping MUST report `kicad.board.kept-opaque` instead of `kicad.lib.kept-opaque`. The `ReadResult.issues` of a board also hold the `model.*` codes of `Design.validate()` (`backend-protocol` "Read results"); they are model findings, not reader codes, and are not in this table.

| code | severity | when |
|---|---|---|
| `kicad.board.inexact-length` | info | a length that is not a whole number of nm |
| `kicad.board.inexact-angle` | info | an angle that is not a whole number of µdeg |
| `kicad.board.zone-outline-opaque` | info | a zone or rule-area outline with `pts` arcs or several `polygon` children |
| `kicad.board.duplicate-uuid` | warning | a uuid already used by another item of the file |
| `kicad.board.unknown-net` | warning | a numbered net reference absent from the table |
| `kicad.board.kept-opaque` | info | a modelled or projected child that loses modelled meaning or fails the emitter check |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_numbers.py -k closed_set` collects every issue code that `read_board` produces in the board unit tests
- **THEN** each code other than `kicad.version.*` is a key of `ISSUE_CODES` with the severity of this table, and no `model.*` code comes from `read_board`

#### Scenario: Oval drill on a board pad
- **GIVEN** a board pad with `(drill oval 1.2 2.0)`
- **WHEN** the board is read with an `issues` list
- **THEN** the pad has `drill is None`, and `issues` holds one info `kicad.board.kept-opaque` and no `kicad.lib.*` code

### Requirement: Same-version rebuild
`pcb.rebuild_board(design)` SHALL return the `kicad_pcb` node of a design read by `read_board`, built with `slots.rebuild` and `pcb.ModelSource`, the first `slots.SlotSource` implementation in `src`.
- Modelled children MUST be emitted from the current model values. Opaque slots MUST be emitted verbatim at their positions.
- The header MUST be the source header.
- Items of each collection MUST be matched to their slots in the order of the index in their `provenance.locator`.
- An entity without a `kicad` slot list MUST raise `ValueError` naming its id.
- For every board file `f` read without error, with `t` its text, RT1 MUST hold:
  - `tree_equal(rebuild_board(read_board(t)), parse(t))`;
  - the canonical JSON of `read_board(dumps(rebuild_board(read_board(t))))` equals that of `read_board(t)` when every `provenance` is set to `None`. Both sides are read from text, so `header.name` is `""` on both;
  - `opaque_count` and `opaque_digests` are equal.

#### Scenario: Authored board round trip
- **GIVEN** the authored board
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_rebuild.py -k rt1` runs
- **THEN** the three RT1 conditions hold

#### Scenario: Created entity refused
- **GIVEN** a design read from the authored board with one extra `Track` that has no `ext`
- **WHEN** `rebuild_board` is called
- **THEN** `ValueError` is raised naming the track's id

#### Scenario: Collection order does not matter
- **GIVEN** the authored design with `board.tracks` reversed
- **WHEN** it is rebuilt
- **THEN** the result is tree-equal to the original board

### Requirement: Opaque count and digests
`pcb.opaque_count(design)` SHALL return the number of `Opaque` slots across every `ext["kicad"]` bag of a design read from KiCad, that is the number of payload keys of the form `slot:<rel>:opaque` or `slot:<rel>:opaque@<N>`. `pcb.opaque_digests(design)` SHALL return a `collections.Counter` of the SHA-256 hex digests of their fragments.

#### Scenario: Count follows the slots
- **GIVEN** the authored board, and the same board with `(group "" (uuid "…") (members))` added at the end of the root
- **WHEN** both are read
- **THEN** the second `opaque_count` is the first plus one, and the digest of the group fragment appears once more

### Requirement: Shared footprint mapping
The pad, drill, padstack and graphic mapping of c0008 SHALL live in `fenolite.backends.kicad._fpmap`, parameterised by root chain (`("footprint",)` or `("kicad_pcb", "footprint")`), graphic head map (`fp_*` or `gr_*`) and kept-opaque code. `mod.py` MUST use it with its own values and MUST keep its behaviour.

#### Scenario: Footprint reading unchanged
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_mod.py tests/unit/backends/kicad/test_mod_pads.py` runs after the move, with those files unchanged
- **THEN** it passes

#### Scenario: Inventory rows match inside boards
- **GIVEN** a board pad holding `(padstack (mode front_inner_back) …)`
- **WHEN** the board is read
- **THEN** `Context.min_version` receives file kind `kicad_pcb` and the full chain `kicad_pcb/footprint/pad/padstack`, and the opaque `padstack` slot carries a minimum version not older than `20240929`, from inventory row `pad-padstack`

### Requirement: IPC-D-356 parsing
`fenolite.backends.kicad.ipcd356.read_ipcd356(text)` SHALL parse the netlist that `kicad-cli pcb export ipcd356` writes into `Ipcd356(unit_nm, records)`.
- Each `317` or `327` record MUST give `code`, `net`, `ref`, `pin`, `x`, `y` (export units, Y up), `rotation` from the `R` field when present, and `side`.
- `ref` and `pin` MUST be the export's fixed-width fields as written, stripped of padding: the export truncates the reference to 6 characters and the pin to 4 (observed on 10.0.6, S-0019). A via record has `ref == "VIA"` and an empty `pin`.
- `UNITS CUST 0` MUST give `unit_nm == 2540`.
- Text without a `UNITS` line MUST raise `FormatError`.
- `tests/kicad/test_geometry_frame.py` MUST parse its export with this function.

#### Scenario: Through-hole record
- **GIVEN** an authored export text with the line `P  UNITS CUST 0` and one `317` record for net `GND`, reference `D1`, pin `1`, at `X+0001000Y-0002000` with `R030`
- **WHEN** `read_ipcd356` is called
- **THEN** `unit_nm == 2540` and the record has `net == "GND"`, `ref == "D1"`, `pin == "1"`, `x == 1000`, `y == -2000` and `rotation == 30`

#### Scenario: Via and truncated records
- **GIVEN** an authored export text with a `317` via record, whose reference field is `VIA` and whose pin field is blank, and a `327` record whose reference field holds the six characters `ABCDEF` of the reference `ABCDEFG1`
- **WHEN** `read_ipcd356` is called
- **THEN** the via record has `ref == "VIA"` and `pin == ""`, and the other record has `ref == "ABCDEF"`

#### Scenario: Missing units
- **WHEN** `read_ipcd356` is called on text without a `UNITS` line
- **THEN** `FormatError` is raised

### Requirement: Authored two-layer board
`tests/data/kicad/board/two_layer.kicad_pcb` SHALL be an authored CC0 board with header `20241229` and generator version `"9.0"`, holding the content listed in design Decision 19, declared `origin = "authored"` in `tests/data/MANIFEST.toml`. `kicad-cli` 9.0.9 and 10.0.6 MUST load it.

#### Scenario: Fixture loads on both majors
- **GIVEN** `kicad-cli` 10.0.6 locally or 9.0.9 in the `kicad-9` job
- **WHEN** `uv run pytest tests/kicad/board/test_board_loads.py -k fixture` runs
- **THEN** `KicadCli.load_board_svg` on the fixture exits 0 and writes the SVG

#### Scenario: Fixture declared and clean
- **WHEN** `uv run pytest tests/corpus/test_manifest.py tests/residue -q` runs
- **THEN** the fixture is accepted as authored and no residue or derived-corpus finding names it

### Requirement: Board reading evidence
Before merge, the reader MUST reach this evidence:
- Every non-heavy `rt0` board at format 8.0 or newer (the 16 non-heavy demos at 10.0.6 and the 5 readable ones at 9.0.9.1, 21 boards) MUST read with no error issue from `read_board` and pass RT1 (`tests/corpus/test_board_read.py`, `tests/corpus/test_board_rt1.py`). "No error issue" counts the reader's issues only. `Design.validate()` findings, such as duplicate references that KiCad itself saves, are counted by the census and are not part of the criterion.
- `kicad-demo-9-0-9-1-pcb-04` (row `malformed`, not `rt0`) MUST raise `FormatError` when it is cached, and the three third-party rows MUST raise `UnsupportedFormatError` (`FEN-3003`) with a `pcb upgrade` hint.
- On 10.0.6, the `pcb upgrade --force` copies of the upgrade set (the 16 non-heavy 10.0.6 demos and the 3 third-party boards) MUST read with no error issue from `read_board` and pass RT1.
- The census MUST count, per origin (native demos; upgraded third-party copies), inexact lengths and angles by context, kept-opaque reasons, uuid repeats, opaque zone outlines and `Design.validate()` findings by code and severity. It MUST write them only to the file named by `FENOLITE_CENSUS_OUT`. A census-based label of `CORPUS-VERIFIED` MUST rest on counts from both origins.

`pcb.EVIDENCE` SHALL be `INFERRED`, linked to `H-K-PCB-READ`, and SHALL stay so; RT1 makes the lossless read `CORPUS-VERIFIED`, not the meaning of each field.

#### Scenario: Demo boards read and round-trip
- **GIVEN** the fetched corpus
- **WHEN** `uv run pytest tests/corpus/test_board_read.py tests/corpus/test_board_rt1.py -q` runs
- **THEN** 21 boards pass, the malformed row raises `FormatError` when it is cached, and the third-party rows raise `UnsupportedFormatError`

#### Scenario: Census stays out of the repository
- **GIVEN** `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** `uv run pytest tests/corpus/test_board_census.py` runs
- **THEN** the counts are written to that file and `git status --porcelain` is unchanged

### Requirement: Board format facts are documented
`docs/formats/kicad/board.md` SHALL hold the board facts in a table with the header `| fact | source | label | hypothesis |`. It covers the modelled, projected and opaque content per head, both net forms, layer kinds (the `*.Adhes` row and the fallback labelled as Fenolite choices), the pad frame and angle pair, zones and island flags, number rules, and the observed formats of the `pos` and IPC-D-356 exports. Every row MUST cite a source id, and every row below `KICAD-VERIFIED` or `CORPUS-VERIFIED` MUST name a hypothesis.

#### Scenario: Fact table checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it passes with `board.md` present

### Requirement: KiCad file backend decision record
`docs/adr/0002-kicad-file-backend.md` SHALL record the backend decisions: slots and opaque by default, reading 8.0 and newer, writing targets 9 and 10 with 8.0 read-only, downgrade refused, `kicad-cli` only as a subprocess oracle through the package runner, and the pad frame. It MUST use the six MADR-lite sections, and `tests/unit/test_adrs.py` MUST require it.

#### Scenario: ADR present
- **WHEN** `uv run pytest tests/unit/test_adrs.py` runs
- **THEN** it passes, and `0002-kicad-file-backend.md` is in its `REQUIRED` list
