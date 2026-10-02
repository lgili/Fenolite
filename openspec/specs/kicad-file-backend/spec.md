# kicad-file-backend Specification

## Purpose
Read KiCad board files into the neutral model without losing anything: typed reading of `.kicad_pcb` from KiCad 8.0 on with slots (modelled, projected and opaque children kept in place), the version policy, layers, nets in both forms, the pad frame, zones and rule areas, exact numbers, stable ids, a closed set of issue codes, a synthesised circuit, and the same-version rebuild (RT1). Facts and sources: `docs/formats/kicad/board.md`.
## Requirements
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

### Requirement: Board writing per target
`fenolite.backends.kicad.pcb.write_board(design, *, target=DEFAULT_TARGET, allow_lossy=False)` SHALL return a `WriteResult` whose `text` is a `.kicad_pcb` file for KiCad `target`.0 and whose `issues` hold the warnings and infos of the write. It MUST proceed in this order:
1. For a design read from a file, `versions.require_editable` and then `versions.check_target` on the source header (`pcb.source_info(design)`). A created design has no source header and skips this step.
2. The refusal of "KiCad 8 boards are read-only".
3. The header `(version FORMAT_VERSIONS[FileKind.BOARD][target])`, `(generator "fenolite")` and `(generator_version "<target>.0")`, for read and created boards alike.
4. The net form of "Net form per target", applied to every `net` node.
5. For target 10, every node matched by an inventory row with `until_major = 9` is converted or dropped, with one `kicad.board.obsolete-dropped` info per row id whose nodes were removed, converted rows included, carrying the count of nodes.
6. Created entities are inserted in `pcb.CANONICAL_ORDER` ("Slot source for model entities" of `kicad-slots`).
7. `versions.check_emittable(root, FileKind.BOARD, target)` runs on the final tree; its errors are handled by "Lossy writes are refused unless allowed".

Further rules:
- `target` MUST be in `TARGET_MAJORS`; any other value raises `ValueError`.
- `write_board` MUST NOT write any file, and `text` MUST be printed by c0006's `dumps` in `kicad` style and end with a newline.
- Writing the same design twice MUST give identical `text`.
- `WriteResult.issues` MUST hold only warnings and infos; every error MUST be raised.
- The writer's issue codes MUST be the closed set `pcb.WRITE_ISSUE_CODES`: `kicad.board.dropped-too-new` (warning), `kicad.board.obsolete-dropped` (info), `kicad.board.opaque-net-ref`, `kicad.board.projection-read-only`, `kicad.board.outline-conflict` and `kicad.board.flip-unsupported` (errors).

#### Scenario: Header for target 9
- **GIVEN** the created test board `tests/_boards.py::created_board()`, built through the model API without library definitions
- **WHEN** `write_board(design, target=9)` is called and the text is parsed
- **THEN** the root has `(version 20241229)`, `(generator "fenolite")` and `(generator_version "9.0")`

#### Scenario: Emit check is clean for both targets
- **GIVEN** the created test board
- **WHEN** it is written for target 9 and for target 10, and `check_emittable` runs on each parsed text with the same target
- **THEN** both calls return no issue at all

#### Scenario: Read board upgraded to target 10
- **GIVEN** `tests/data/kicad/tokens/skeleton.kicad_pcb` (header `20241229`) read with `read_board`
- **WHEN** `write_board(design, target=10)` is called
- **THEN** the text has header `20260206` and `generator_version "10.0"`, holds none of `hpglpennumber`, `hpglpenspeed`, `hpglpendiameter`, `plotinvisibletext`, `filled_areas_thickness` and `net_name` and no root `net` row, and `issues` holds exactly seven `kicad.board.obsolete-dropped` infos, one for each of the row ids `board-net-table` (count 3), `zone-net-name`, `zone-filled-areas-thickness`, `plot-hpglpennumber`, `plot-hpglpenspeed`, `plot-hpglpendiameter` and `plot-plotinvisibletext` (count 1 each)

#### Scenario: Downgrade refused
- **GIVEN** `tests/data/kicad/tokens/future.kicad_pcb` (header `20260206`) read with `read_board`
- **WHEN** `write_board(design, target=9)` is called
- **THEN** `DowngradeRefusedError` is raised with `cli_code == "FEN-7002"`

#### Scenario: Future board refused
- **GIVEN** a copy of `tests/data/kicad/tokens/future.kicad_pcb` whose header is changed to `20990101`, read with `read_board`
- **WHEN** `write_board(design, target=10)` is called
- **THEN** `FutureFormatError` is raised and no text is returned

#### Scenario: Deterministic text
- **GIVEN** the created test board
- **WHEN** it is written twice for target 10
- **THEN** the two texts are equal byte for byte

### Requirement: Created board header
For a created design, `write_board` SHALL emit exactly the root head set of c0007's `tests/data/kicad/tokens/skeleton.kicad_pcb`:
- `version`, `generator` and `generator_version`;
- `(general (thickness T) (legacy_teardrops no))`, where T is the sum of the `Board.stackup` layer thicknesses, or 1.6 mm without a stack-up;
- `(paper "A4")`;
- `layers`, from `Board.layers` and each layer's `kicad` bag;
- `(setup (pad_to_mask_clearance 0))`;
- for target 9 only, the net table.

The content follows in `CANONICAL_ORDER`. `fenolite.backends.kicad.layers.created_layers(copper)` MUST return the 2- and 4-copper-layer sets recorded in `docs/formats/kicad/board.md`, numbered in the 9.0 scheme (`F.Cu` 0, `B.Cu` 2, `In1.Cu` 4, `In2.Cu` 6, `Edge.Cuts` 25), with the KiCad number, type and user name in each layer's `kicad` bag. Any other `copper` value MUST raise `ValueError`. Every head and field name the writer can create MUST match a row of the token inventory, appear in c0007's skeleton, or be listed in `pcb.FLOOR_HEADS`: a closed tuple of names that the 8.0 board format already has, each recorded in `docs/formats/kicad/board.md` with its source and written by the created test board that the triad oracle loads on both majors.

#### Scenario: Head set of a created 2-layer board
- **GIVEN** a created design whose board has `created_layers(2)` and no content
- **WHEN** it is written for target 9
- **THEN** the root's child heads are, in order, `version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`, `net`

#### Scenario: No net table for target 10
- **GIVEN** the same design
- **WHEN** it is written for target 10
- **THEN** the root's child heads are `version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`, and no child is headed `net`

#### Scenario: Four copper layers
- **WHEN** `created_layers(4)` is called
- **THEN** the copper layers are `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` with KiCad numbers 0, 4, 6 and 2

#### Scenario: Created tokens are known
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens` runs
- **THEN** every head and field in `CANONICAL_ORDER` and in the created header is found in the skeleton, is in `FLOOR_HEADS`, or matches an inventory row, and every name of `FLOOR_HEADS` occurs in the parsed text of the created test board written for target 9

### Requirement: Net form per target
`write_board` SHALL write every net reference in the form of the target, in modelled and opaque content alike:
- **Target 9.** The root holds `(net 0 "")` followed by `(net i "<name>")` for the model's nets sorted by name in code-point order, i = 1 … n. Pads write `(net i "<name>")`; tracks, arcs, vias and zones write `(net i)`; zones also write `(net_name "<name>")`. For a read board, the table MUST take the place of the source's table, and its row 0 MUST replace the source's opaque `(net 0 "")` slot, so the text holds exactly one row 0.
- **Target 10.** The root holds no net table, and the source's opaque `(net 0 "")` slot MUST be removed. Every reference is `(net "<name>")`, and zones write no `net_name`.
- Net 0 and the empty name mean no net. For target 9, a zone or rule area whose net is `None` MUST write `(net 0)` and `(net_name "")`, and every other item whose `net_id` is `None` MUST carry no `net` child. For target 10, an item whose net is `None` MUST NOT carry a `net` child.
- Inside opaque fragments, `(net 0)`, `(net 0 "")` and `(net "")` MUST be written `(net 0)` for target 9 and removed for target 10, and MUST NOT give `kicad.board.opaque-net-ref`.
- Inside opaque fragments, a numbered reference MUST be resolved through the source net table kept by `read_board`, and a named reference by its name; both MUST be re-emitted in the target's form.
- A `net` node in opaque content that matches none of `(net N)`, `(net N "name")` and `(net "name")`, or whose number N ≥ 1 is absent from the source table, MUST give `kicad.board.opaque-net-ref` (error). `allow_lossy` MUST NOT drop it.

#### Scenario: Numbered table for target 9
- **GIVEN** a design with nets `VIN`, `GND` and `LED_A`
- **WHEN** it is written for target 9
- **THEN** the root holds `(net 0 "")`, `(net 1 "GND")`, `(net 2 "LED_A")`, `(net 3 "VIN")` in that order, and a track on `GND` holds `(net 1)`

#### Scenario: Names for target 10
- **GIVEN** the same design
- **WHEN** it is written for target 10
- **THEN** a pad on `VIN` holds `(net "VIN")`, a zone on `GND` holds `(net "GND")` and no `net_name`, and the root holds no net table

#### Scenario: Opaque net reference converted
- **GIVEN** a copy of `tests/data/kicad/tokens/skeleton.kicad_pcb`, built in the test, with an added teardrop zone (an `attr` child holding `teardrop`) that holds `(net 2)` and `(net_name "B")`, where net 2 is `B` in the source table, read with `read_board`, so the teardrop zone is an opaque root slot
- **WHEN** it is written for target 10
- **THEN** the teardrop zone holds `(net "B")` and no `net_name`, and every other child of it is tree-equal to the source

#### Scenario: Unknown opaque net reference
- **GIVEN** a copy of `skeleton.kicad_pcb` whose segment holds `(net 7)` while the source table ends at 2, read with `read_board`, which keeps that reference opaque (c0009 "Nets in both forms")
- **WHEN** it is written with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with `droppable == False` and an issue `kicad.board.opaque-net-ref` whose `where` locates that node

#### Scenario: Unconnected rule area in both forms
- **GIVEN** a copy of `tests/data/kicad/board/two_layer.kicad_pcb` whose rule area holds `(net 0)` and `(net_name "")`, as KiCad 9 writes, read with `read_board`
- **WHEN** it is written for target 9 and for target 10
- **THEN** both writes succeed; the target-9 text holds exactly one root `(net 0 "")` and a rule area holding `(net 0)` and `(net_name "")`; the target-10 text holds no `net` node whose atom is `0` or `""`, and no `net_name`

### Requirement: Lossy writes are refused unless allowed
`write_board` SHALL raise `fenolite.backends.kicad.versions.LossyWriteError` (`cli_code = "FEN-7001"`) when the final emit check reports `kicad.token.too-new` inside an opaque slot and `allow_lossy` is false. The exception MUST carry every such issue in `issues` and `droppable = True`, and its hint MUST name `--allow-lossy`.
- With `allow_lossy=True`, the writer MUST remove the innermost opaque slot holding each such token, add one `kicad.board.dropped-too-new` warning per removed slot naming its locator and inventory row, and run the emit check again, which MUST then report no error.
- A too-new token in modelled content MUST raise `LossyWriteError` with `droppable = False`, with or without `allow_lossy`.
- Every other writer error (`opaque-net-ref`, `projection-read-only`, `outline-conflict`) MUST raise `LossyWriteError` with `droppable = False` and a hint that does not name `--allow-lossy`.
- The gate MUST be the emit check over tokens; a slot's `min_version` MUST NOT refuse a fragment whose tokens the target reads.

#### Scenario: 10.0 footprint embedded for target 9
- **GIVEN** a created design holding `Mini_R_0603` read from `tests/data/libs/Mini.pretty` (header `20260206`) and placed with `place_footprint`
- **WHEN** `write_board(design, target=9)` is called
- **THEN** `LossyWriteError` is raised with `droppable == True`, one of its issues names `duplicate_pad_numbers_are_jumpers`, and its hint contains `--allow-lossy`

#### Scenario: Lossy write allowed
- **GIVEN** the same design
- **WHEN** `write_board(design, target=9, allow_lossy=True)` is called
- **THEN** the text holds no `duplicate_pad_numbers_are_jumpers`, `issues` holds one `kicad.board.dropped-too-new` warning, and `check_emittable` on the parsed text for target 9 returns no error

#### Scenario: Modelled content is never dropped
- **GIVEN** a created design with a `Via` whose `via_type` is `"buried"`
- **WHEN** it is written for target 9 with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with `droppable == False`

### Requirement: KiCad 8 boards are read-only
`write_board` SHALL raise `fenolite.backends.kicad.versions.LegacyEditRefusedError` (`cli_code = "FEN-7003"`) for every target when `major_for(FileKind.BOARD, version)` of the source header is 8. Its hint MUST name `kicad-cli pcb upgrade` and re-saving in KiCad 9.0. `read_board` MUST keep reading such boards. A source whose header maps to major 9, including the development header `20241030`, MUST NOT be refused by this rule.

#### Scenario: KiCad 8 board refused
- **GIVEN** `tests/data/kicad/tokens/old/old.kicad_pcb` (header `20240108`) read with `read_board`
- **WHEN** `write_board(design, target=9)` and `write_board(design, target=10)` are called
- **THEN** each raises `LegacyEditRefusedError` with `cli_code == "FEN-7003"` and a hint containing `kicad-cli pcb upgrade`

#### Scenario: Development header of 9.0 is writable
- **GIVEN** a copy of `tests/data/kicad/tokens/skeleton.kicad_pcb` with header `20241030`, read with `read_board`
- **WHEN** it is written for target 9
- **THEN** no exception is raised and the text has header `20241229`

### Requirement: Projected fields on write
Before re-emitting an opaque fragment that a reader projected into a model field, `write_board` SHALL project the fragment again with the reader's function and compare the result with the model.
- When `Component.ref` or `Component.value` differs, the writer MUST rewrite only the value atom of the `(property "Reference" …)` or `(property "Value" …)` fragment; every other atom and child of that fragment MUST stay tree-equal.
- When a modelled field kept as an `Opaque` projected slot by the reader's reproducibility check differs, the writer MUST emit that field from the model if the fragment differs from the emitter's output for the old value only in spelling (same heads and atom count, numbers equal as decimals, strings equal as text, a zero angle written or omitted); otherwise it MUST give `kicad.board.projection-read-only`. An unchanged value MUST keep its fragment.
- When any other projection differs (`Component.properties` other than Reference and Value, `Graphic.width` from a `stroke`, `Pad.padstack`), the writer MUST give `kicad.board.projection-read-only`, naming the field and the locator.

#### Scenario: Reference renamed
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its resistor component's `ref` changed to `R9`
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that footprint's `property "Reference"` node has value `"R9"` and is otherwise tree-equal to the source node

#### Scenario: Spelling-only projection re-emitted
- **GIVEN** a copy of `two_layer.kicad_pcb`, built in the test, whose first `segment` holds `(width 0.250000)`, read with `read_board`, so the reader keeps that `width` as a projected slot, and the track's width then changed to 300 000 nm
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that segment holds `(width 0.3)` at the position of the source `width`, and no issue is raised

#### Scenario: Read-only projection edited
- **GIVEN** the same board with the resistor's `properties["Datasheet"]` changed
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.projection-read-only` naming `properties` and the footprint's locator

### Requirement: KiCad uuids on write
`write_board` SHALL give every emitted entity that KiCad identifies by `uuid` the value of `entity.native_ids["kicad"]` when present, and otherwise `uuid5(FENOLITE_NS, "kicad-out:" + entity.id)`. A part without its own id (an outline edge) MUST use `"kicad-out:<owner id>:<part>"`. `pcb.kicad_uuid(entity, part="")` MUST return the same value.

#### Scenario: Read uuids are kept
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`
- **WHEN** it is written for target 9 and every `uuid` atom of both texts is collected
- **THEN** the two multisets are equal

#### Scenario: Created track uuid
- **GIVEN** a created `Track` with id `trk_00000000-0000-4000-8000-000000000001` and no native id
- **WHEN** a design holding it is written
- **THEN** the segment's uuid is `uuid5(FENOLITE_NS, "kicad-out:trk_00000000-0000-4000-8000-000000000001")`

### Requirement: Outline lowering
For any board whose `Board.outline` has points, created or read and then given an outline, `write_board` SHALL emit one `gr_line` on `Edge.Cuts` per edge of the outer ring and of each cutout, closing every ring, with stroke width 0.1 mm and type `solid`. The lines are created entities. A board with no outline, or an outline without points, MUST emit none. No `gr_arc` is emitted, because `Outline` holds points only. A board with both a non-empty outline and a `Graphic` on a layer of kind `edge` MUST give `kicad.board.outline-conflict`.

#### Scenario: Rectangle outline
- **GIVEN** a created board whose outline has the points (0, 0), (50 mm, 0), (50 mm, 30 mm), (0, 30 mm)
- **WHEN** it is written
- **THEN** the text holds four `gr_line` nodes on `Edge.Cuts`, the last ending at (0, 0)

#### Scenario: Outline and edge graphics
- **GIVEN** a created board with that outline and a `Graphic` on `Edge.Cuts`
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.outline-conflict`

#### Scenario: Outline set on a read board
- **GIVEN** `tests/data/kicad/tokens/skeleton.kicad_pcb` read with `read_board`, given the rectangle outline, once with its `Edge.Cuts` `gr_rect` and once with that `Graphic` removed from the model
- **WHEN** each design is written for target 9
- **THEN** the first raises `LossyWriteError` with an issue `kicad.board.outline-conflict`, and the second text holds four `gr_line` nodes on `Edge.Cuts` and no `gr_rect`

### Requirement: Footprint embedding
`fenolite.backends.kicad.embed.place_footprint(defn, *, component, at, rotation=0, side="top", locked=False, key)` SHALL return a `FootprintInstance` for `defn` placed at `at` with stored angle `rotation` on `side`:
- It MUST call `versions.require_editable` on the definition's source format first.
- It MUST emit the definition with `_fpmap.emit_footprint`, drop the children `version`, `generator` and `generator_version`, name the footprint `defn.lib_id`, set its layer to `F.Cu` (top) or `B.Cu` (bottom), and set the value atoms of Reference and Value from `component`.
- Every KiCad uuid MUST be `embed.placement_uuid(key, locator)`, which is `uuid5(FENOLITE_NS, f"kicad-place:{key}:{locator}")`, with `locator` the bare locator of the node in the emitted definition (`/footprint` for the footprint itself).
- The instance MUST be mapped by c0009's board-footprint mapping, so its pads, slots and ids equal those `read_board` gives for the written board. `component_id` MUST be `component.id`, `lib_ref` MUST be `defn.lib_id`, `attributes` MUST hold `defn.kind` (unless `unspecified`) followed by `defn.flags`, and every pad MUST have `net_id = None`.
- On the bottom side, `layers.flip_layer` MUST be applied to every `layer` and `layers` atom; every node headed in `embed.MIRROR_HEADS` MUST have its Y negated; the angle of every child `at` MUST become (−φ) mod 360° before being made absolute; and the `justify` of every text on a flipped layer MUST toggle `mirror`. A node whose head is in `embed.FLIP_UNSUPPORTED` MUST make `place_footprint` raise `LossyWriteError` with `droppable == False` and one `kicad.board.flip-unsupported` issue per such node, naming its locator; no instance is returned. On the top side such nodes are copied unchanged.
- On both sides, child angles MUST be stored absolute through c0009's `pad_angle_to_board`.
- `embed.footprint_extent(defn)` MUST return the box of the modelled `F.CrtYd` graphics, else the union of the pad boxes, else `BBox(0, 0, 0, 0)`.

#### Scenario: Top placement of the mini resistor
- **GIVEN** `Mini_R_0603` read from `tests/data/libs/Mini.pretty` and a component `R1` with value `1k`
- **WHEN** `place_footprint(defn, component=r1, at=Point(10_000_000, 10_000_000), key="R1")` is called and the instance is written
- **THEN** the footprint is named `"Mini:Mini_R_0603"`, has layer `F.Cu`, holds no `version` child, its Reference value is `"R1"` and its Value value is `"1k"`

#### Scenario: Uuids from the key
- **GIVEN** the same definition placed twice with keys `R1` and `R2`
- **WHEN** the two instances are compared
- **THEN** no uuid and no id is shared, and placing again with key `R1` reproduces every uuid and id of the first instance

#### Scenario: Bottom placement mirrors the children
- **GIVEN** `Mini_QFP-32_7x7mm_P0.8mm` read from `Mini.pretty`, whose pad `"1"` sits at (−4.15 mm, −2.8 mm) with angle 0 and pad `"9"` has angle 90°
- **WHEN** it is placed with `side="bottom"` and `rotation=30_000_000`
- **THEN** pad `"1"` of the instance has `position == Point(-4_150_000, 2_800_000)` and layers starting with `B.Cu`, pad `"9"` of the instance has `rotation == 270_000_000` (the mirrored library angle, relative to the footprint), the written text stores pad `"9"` as `(at -2.8 -4.15 300)` (−90° + 30°, absolute), and the footprint layer is `B.Cu`

#### Scenario: Unsupported geometry on the bottom
- **GIVEN** a definition read from a copy of `Mini_R_0603`, built in the test, whose pad `"1"` is a `trapezoid` pad holding `(rect_delta 0 0.1)`
- **WHEN** it is placed with `side="bottom"`, then with `side="top"`
- **THEN** the bottom placement raises `LossyWriteError` with `droppable == False` and one issue `kicad.board.flip-unsupported` whose `where` locates the `rect_delta` node, and the top placement returns an instance whose pad keeps `rect_delta` unchanged

#### Scenario: Future definition refused
- **GIVEN** a definition read from a footprint file with header `20990101`
- **WHEN** `place_footprint` is called
- **THEN** `FutureFormatError` is raised

#### Scenario: Courtyard extent
- **GIVEN** `Mini_R_0603`, whose courtyard is an `fp_rect` on `F.CrtYd`
- **WHEN** `footprint_extent(defn)` is called
- **THEN** the result equals the box of that rectangle

### Requirement: DRC report reading
`fenolite.backends.kicad.drc.read_drc_report(text, *, file="")` SHALL return a `DrcReport` (`backend-protocol`, "Neutral DRC report") for the JSON text that `kicad-cli pcb drc --format json` writes.
- The text MUST be parsed as strict JSON with numbers kept as text. `NaN`, `Infinity` and `-Infinity` MUST raise `FormatError`, and no float is ever created.
- A missing key of `drc.REQUIRED_KEYS` (`source`, `date`, `kicad_version`, `violations`, `unconnected_items`, `schematic_parity`, `coordinate_units`) MUST raise `FormatError` naming the key. Unknown keys MUST be ignored.
- `ignored_checks`, present at 10.0.6 only, MUST be accepted and kept as the `key` string of each entry. `included_severities` MUST be kept when present.
- Positions MUST be converted to integer nanometres from `coordinate_units` (`mm`, `mils`, `in`) with exact rational arithmetic, rounded half to even when not exact. Any other unit MUST raise `FormatError`.
- `type` and `severity` MUST stay KiCad's strings, and violations, unconnected items and parity items MUST keep file order.
- `docs/formats/kicad/drc.md` MUST describe the report structure in Fenolite's own words, with key names only from S-0055 and S-0056; `drc.v1.json` MUST NOT be vendored or read at runtime.

#### Scenario: Millimetre report
- **GIVEN** the authored `tests/data/kicad/drc/report_mm.json`, whose first violation is a `clearance` with an item at x 12.5 and y 3.25
- **WHEN** `read_drc_report` reads it
- **THEN** `report.violations[0].type == "clearance"` and its first item has `position == Point(12_500_000, 3_250_000)`

#### Scenario: Mil report
- **GIVEN** the authored `tests/data/kicad/drc/report_mils.json`, whose first item is at x 100 and y 0
- **WHEN** `read_drc_report` reads it
- **THEN** that item has `position == Point(2_540_000, 0)`

#### Scenario: Non-strict number rejected
- **GIVEN** `report_mm.json` with one coordinate replaced by `NaN`
- **WHEN** `read_drc_report` reads it
- **THEN** `FormatError` is raised

#### Scenario: Missing required key
- **GIVEN** `report_mm.json` without `coordinate_units`
- **WHEN** `read_drc_report` reads it
- **THEN** `FormatError` is raised naming `coordinate_units`

#### Scenario: Ignored checks tolerated
- **GIVEN** `report_mm.json` with `"ignored_checks": [{"key": "silk_overlap", "description": "x"}]`
- **WHEN** `read_drc_report` reads it
- **THEN** `report.ignored_checks == ("silk_overlap",)`

### Requirement: Footprint files are written
`fenolite.backends.kicad.mod.write_footprint(defn, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return the text of one `.kicad_mod` file for KiCad `target` (9 or 10), and `write_pretty(defs, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return a mapping from `"<name>.kicad_mod"` to that text for each definition, sorted by name.
- The writer MUST call `require_editable` on the definition, as c0017's `place_footprint` does. A definition read from a future file MUST raise `FutureFormatError` (`FEN-3002`).
- A definition without a slot list in `ext["kicad"]` MUST raise `ValueError`. Footprint generation from scratch is out of scope.
- The root MUST be `(footprint "<name>" …)` with `(version V)`, `(generator "fenolite")` and `(generator_version "<target>.0")`, where `V = FORMAT_VERSIONS[FileKind.FOOTPRINT][target]`. These replace the source's `version`, `generator` and `generator_version` slots in place; missing ones MUST be inserted after the name, in that order.
- Every other child MUST follow the definition's slot list. Modelled children MUST come from c0017's footprint emitter, `_fpmap.emit_footprint(defn, root_chain=("footprint",))`. Opaque children MUST be re-emitted verbatim.
- Before a projected fragment is re-emitted, the writer MUST project it again with `mod`'s reader function and compare the result with the definition. An edited `properties["Reference"]` or `properties["Value"]` MUST rewrite only that property's value atom. Any other difference (other `properties`, `keywords`, `models`, `Graphic.width`, `Pad.padstack`) MUST raise `LossyWriteError` with the error `kicad.footprint.projection-read-only` naming the field and the locator.
- `mod.WRITE_ISSUE_CODES` SHALL be the closed table of the footprint writer's codes: `kicad.footprint.dropped-too-new` (warning) and `kicad.footprint.projection-read-only` (error). Every `kicad.footprint.` code MUST be one of its keys.
- The writer MUST NOT sort pads or graphics. Equality is judged on the model and on load, never on bytes.
- The emitted node MUST pass `check_emittable(node, FileKind.FOOTPRINT, target)`. A `kicad.token.too-new` error MUST raise `LossyWriteError` (`FEN-7001`). With `allow_lossy=True`, the smallest opaque slot holding the token MUST be dropped instead, with a warning `kicad.footprint.dropped-too-new` naming the token, appended to `issues`. Any other error MUST abort.
- A definition read from a 10.0 file MUST be accepted for target 9 when every fragment passes this check; there is no whole-file downgrade refusal for definitions.
- `write_pretty` MUST raise `ValueError` for a repeated name or for a name containing `/`, `\` or `:`.
- The KiCad backend's capability report MUST list `kicad_mod` in `write_kinds`.

#### Scenario: Mini resistor written for KiCad 10
- **GIVEN** `read_footprint(Path("tests/data/libs/Mini.pretty/Mini_R_0603.kicad_mod"))`
- **WHEN** `write_footprint(defn, target=10)` is called
- **THEN** the text starts with `(footprint "Mini_R_0603"`, holds `(version 20260206)`, `(generator "fenolite")` and `(generator_version "10.0")`, and its pads, graphics and properties appear in the order of the source file

#### Scenario: Mini resistor written for KiCad 9
- **GIVEN** the definition of `tests/data/libs/Mini_v9.pretty/Mini_R_0603.kicad_mod`
- **WHEN** `write_footprint(defn, target=9)` is called
- **THEN** the text holds `(version 20241229)` and `(generator_version "9.0")`, and `check_emittable` of its parsed node for target 9 returns no error

#### Scenario: 10.0-only fragment refused for target 9
- **GIVEN** a definition read from a `20260206` footprint holding `(duplicate_pad_numbers_are_jumpers no)`
- **WHEN** `write_footprint(defn, target=9)` is called
- **THEN** `LossyWriteError` is raised, and with `allow_lossy=True` the text lacks that child and `issues` holds one `kicad.footprint.dropped-too-new` warning

#### Scenario: Value edited
- **GIVEN** the definition of `tests/data/libs/Mini.pretty/Mini_R_0603.kicad_mod` with `properties["Value"]` changed to `"10k"`
- **WHEN** it is written for target 10 and the text is parsed
- **THEN** the `property "Value"` node has the value `"10k"` and is otherwise tree-equal to the source node

#### Scenario: Read-only projection edited
- **GIVEN** the same definition with `properties["Datasheet"]` changed
- **WHEN** it is written for target 10
- **THEN** `LossyWriteError` is raised with `droppable is False` and one `kicad.footprint.projection-read-only` naming `properties` and the property's locator

#### Scenario: Footprint write codes are closed
- **GIVEN** the issues produced by the footprint writer's unit tests and the `kicad.footprint.` literals in `src/fenolite/backends/kicad/*.py`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_mod_write.py -k codes` runs
- **THEN** every produced code and every literal is a key of `mod.WRITE_ISSUE_CODES`, with the severity of the table

#### Scenario: Future definition refused
- **GIVEN** a definition read from a footprint with `(version 20991231)`
- **WHEN** `write_footprint(defn, target=10)` is called
- **THEN** `FutureFormatError` is raised

#### Scenario: Definition without slots
- **GIVEN** `FootprintDef(id=..., name="X")`
- **WHEN** `write_footprint` is called on it
- **THEN** a `ValueError` saying that footprint generation is not supported is raised

#### Scenario: Library folder mapping
- **GIVEN** the four definitions of `tests/data/libs/Mini.pretty`
- **WHEN** `write_pretty(defs, target=10)` is called
- **THEN** the keys are the four file names `<name>.kicad_mod` in sorted order, and two definitions with the same name raise `ValueError`

### Requirement: Custom rules files are read and written
`fenolite.backends.kicad.dru` SHALL read and write custom rules files in the full dialect. `parse_rules(text, *, file="")` SHALL return a `RulesDocument` whose ordered items are the version list, the rule lists and the comment lines of the file.
- A line whose first non-blank character is `#` MUST become a `CommentItem` with its exact text and line number, wherever it is. A comment line inside a top-level list MUST stay inside that item's text and mark it `has_comment`.
- A symbol atom containing `'` outside a double-quoted string, such as a single-quoted rule name, MUST raise `FormatError` with `locator == "line N"` and a message naming line N, because KiCad drops the whole file. A `'…'` literal inside a double-quoted condition MUST be accepted.
- A top-level atom, a second `version` list, or a missing version MUST raise `FormatError`. The version MUST follow `kicad-version-gating`: below 1 is too old, above 1 is future and read-only.
- `RulesDocument.node` MUST be the synthetic `kicad_dru` node of the version and rule lists, without comments.

`read_rules(text, *, file="", issues=None)` SHALL return a `RuleSet`:
- A rule list MUST be lifted into a `Rule` only when every child belongs to the closed grammar of `rules-model`: a name, one constraint of a mapped kind with allowed limits and values in `mm`, `mil` or `in` (parsed exactly with `core.units.parse_length`), at most one condition in the closed selector grammar (up to whitespace and redundant parentheses), at most one layer clause with one layer name, and at most one severity among `error`, `warning` and `ignore`. A `hole_size` rule whose condition starts with the conjunct `A.Type == 'Via'` MUST lift as `hole_size` with an `item_kind via` selector.
- Any other rule list, every comment line, and every rule with a comment inside MUST be kept as an `Opaque` slot of `RuleSet.ext["kicad"]` with its exact source text, in file order, and every unlifted rule MUST add the info `rules.kept-opaque` naming the reason.
- A lifted rule MUST get the priority "number of rule items after it, plus 1", the id `derived_id("rul", "kicad", "rule:<name>")` (with `:<k>` for the k-th repetition of a name), its clause order as slots in its own `ext["kicad"]`, and provenance with locator `/kicad_dru/rule[i]` and `dru.EVIDENCE`. A missing severity MUST lift as `"error"`.
- In a future file, every item MUST be kept opaque with the file version as minimum version.

`write_rules(ruleset, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return the file text:
- It MUST write `(version 1)` first, then follow the file slots: comments and opaque rules verbatim in place, the k-th `rules` slot as `ruleset.rules[k]`, rules beyond the slots after the last `rules` slot, and rules of a rule set without slots in tuple order. Rule names and clause order MUST be kept. A clause the model now needs and the slots lack MUST be inserted in the order `layer`, `condition`, `constraint`, `severity`. A rule without clause slots MUST always carry `(severity …)`.
- Modelled rules MUST be written through `rulemap` (the `rules-model` grammar). A rule set read from a future file MUST raise `FutureFormatError`.
- Every opaque rule and every unknown top-level list MUST pass `check_emittable` on a synthetic `kicad_dru` node holding `(version 1)` and that item. An item whose text does not parse there MUST raise `RulesSelfCheckError` with step `parse`, before any gating issue. For target 9, a `kicad.token.too-new` or `kicad.token.uninventoried` issue MUST refuse the item: `RulesLossError` (`FEN-7001`, `droppable` true) is raised, or with `allow_lossy=True` the item is dropped with the warning `rules.dropped-for-target` naming the rule and the token. For target 10, a `kicad.token.uninventoried` item MUST be kept and its warning appended to `issues`.
- Before returning, the writer MUST pass the self-check of `rules-model` ("Lowered text is self-checked"), and every comment and opaque rule MUST come back as the same opaque slot in the same order. A failure MUST raise `RulesSelfCheckError` (`FEN-1001`).
- `versions.wrap_rules` and `versions.rules_text` MUST keep their common-subset behaviour.
- The KiCad backend's capability report MUST list `kicad_dru` in `write_kinds`. `read_kinds` MUST stay unchanged, because `Backend.read` returns a `Design` or a `Library` and `read_rules` returns a `RuleSet`.

#### Scenario: Comments stay in place
- **GIVEN** `tests/data/kicad/rules/comments.kicad_dru`, with a comment line before the first rule, one between two rules and one inside a rule
- **WHEN** `write_rules(read_rules(text), target=10)` is called and the result is read again
- **THEN** the three comment lines appear at the same positions relative to the rules, the rule holding a comment is kept verbatim, and the two rule sets are equal ignoring provenance

#### Scenario: Units read exactly
- **GIVEN** `tests/data/kicad/rules/units.kicad_dru` with the values `0.2mm`, `8mil` and `0.01in`
- **WHEN** it is read
- **THEN** the lifted `min` values are `200000`, `203200` and `254000`, and writing gives `0.2mm`, `0.2032mm` and `0.254mm`

#### Scenario: Single-quoted rule name
- **GIVEN** `tests/data/kicad/rules/broken.kicad_dru`, whose third line opens `(rule 'big one'`
- **WHEN** `read_rules(text, file="broken.kicad_dru")` is called
- **THEN** `FormatError` is raised with `file == "broken.kicad_dru"` and `locator == "line 3"`

#### Scenario: Unrepresentable rule kept opaque
- **GIVEN** a rule `(rule ring (constraint annular_width (min 0.1mm)))` between two lifted rules
- **WHEN** it is read with an `issues` list and written for target 9
- **THEN** it is an `Opaque` slot between the two `rules` slots, `issues` holds one `rules.kept-opaque`, and the written text holds it verbatim at the same position

#### Scenario: 10.0-only rule refused for target 9
- **GIVEN** `tests/data/kicad/rules/ten_only.kicad_dru`, which holds the canary and a rule `(constraint bridged_mask)`
- **WHEN** `write_rules(read_rules(text), target=9)` is called
- **THEN** `RulesLossError` is raised with `droppable is True` and one `kicad.token.too-new` issue naming the `bridged_mask` row

#### Scenario: 10.0-only rule dropped with allow_lossy
- **GIVEN** the same rule set
- **WHEN** `write_rules(ruleset, target=9, allow_lossy=True, issues=found)` is called
- **THEN** the text holds the canary and no `bridged_mask`, and `found` holds one `rules.dropped-for-target` warning

#### Scenario: Unknown construct kept for 10 and refused for 9
- **GIVEN** a preserved rule containing the uninventoried head `(frobnicate 1)`
- **WHEN** it is written for target 10 and for target 9
- **THEN** target 10 keeps it and reports one `kicad.token.uninventoried` warning, and target 9 raises `RulesLossError`

#### Scenario: Future rules file
- **GIVEN** a rules text whose first list is `(version 2)`
- **WHEN** it is read and written for target 10
- **THEN** reading gives the warning `kicad.version.future` and only opaque slots, and writing raises `FutureFormatError`

#### Scenario: Opaque text that does not parse
- **GIVEN** a `RuleSet` whose opaque slot holds `(rule broken (constraint clearance`
- **WHEN** `write_rules` is called
- **THEN** `RulesSelfCheckError` is raised naming the parse step, and no text is returned

#### Scenario: Written kinds in capabilities
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the `write_kinds` of the `kicad` entry of `result.backends` contain `kicad_mod` and `kicad_dru`, and its `read_kinds` do not contain `kicad_dru`

#### Scenario: Dialect fixtures load in KiCad
- **GIVEN** the comments, units and selectors fixtures, each on a bench with the canary
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_dialect.py` runs on 9.0.9 and on 10.0.6
- **THEN** the canary violation is present for each fixture, and the `mil` and `in` rules each give their violation

