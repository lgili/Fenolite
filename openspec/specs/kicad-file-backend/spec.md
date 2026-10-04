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
- `Zone` takes `name`, `priority`, `layers` (from `layer` or `layers`) and `net_id`, and `settings`, `filled` and `locked` as "Zone settings are read" describes.
- `Zone.layers` and `Keepout.layers` MUST be actual board layers. Wildcards expand as for pads (`*.Cu` to every copper row, `*.X` and `F&B.X` to `F.X` and `B.X`), and a `layers` child with a wildcard MUST be a projected slot.
- One points-only `polygon` MUST become the outline.
- A `polygon` whose `pts` holds an `arc`, or a zone with several `polygon` children, MUST give `outline == ()`. Every `polygon` child then stays an `Opaque` slot, with the info `kicad.board.zone-outline-opaque`.
- Each `filled_polygon` MUST become one `ZoneFill(layer, polygon, island)`, in file order, several per layer allowed. `island` MUST be true for the bare `(island)` and for `(island yes)`, and false for `(island no)` or no flag.

#### Scenario: Zone with an island fill
- **WHEN** the authored board is read
- **THEN** zone `GND_B` has `layers == ("B.Cu",)`, the net GND, `priority == 0` and two fills on `B.Cu`, of which only the second has `island == True`

#### Scenario: Settings of the authored zone
- **WHEN** the authored board is read
- **THEN** zone `GND_B` has `settings == ZoneSettings()`, `filled == True` and `locked == False`, and its rule area keeps its `connect_pads` and `min_thickness` children as `Opaque` slots

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
The reader MUST record the slot list of the board root in `Board.ext["kicad"]`, and the slot list of every modelled item (footprint, pad, footprint field, track, arc, via, zone, keepout, graphic, text) in its own `ext["kicad"]`, using the encoding of `kicad-slots`.
- Every child of a modelled item that is not modelled MUST be an `Opaque` slot at its position.
- A projected child MUST be an `Opaque` slot whose value is also copied into the model. This covers, among others, the properties that are not footprint fields ("Footprint fields on boards"), the value atom of a footprint field, the `effects` of a footprint field that the emitter does not reproduce, the footprint lock, wildcard pad, zone and rule-area layers, padstacks, offset drills, strokes, text effects of `gr_text`, `pinfunction` and `pintype`.
- Opaque fragments MUST carry the minimum version that `_libread.Context.min_version` gives for root chain `("kicad_pcb", …)`, and the file version when the inventory has no row for the fragment's head.

#### Scenario: Unknown root child survives in place
- **GIVEN** the authored board with `(frobnicate 1)` inserted as the fifth child of the root
- **WHEN** it is read and `slots.from_ext(board.ext["kicad"])` is inspected
- **THEN** the fifth slot is `Opaque("(frobnicate 1)", "20241229")`

#### Scenario: Footprint property is a field
- **WHEN** the authored board is read
- **THEN** the component of `R1` has `ref == "R1"`, the `property "Reference"` child of the footprint is a `Modeled("fields")` slot, and the slot list of that field holds the value atom `"R1"` as an `Opaque` slot

#### Scenario: Bare property is projected
- **GIVEN** a copy of the authored board, built in the test, whose `R1` footprint holds `(property ki_fp_filters "R_*")` after its `Value` property
- **WHEN** it is read
- **THEN** that child is an `Opaque` slot of the footprint, and the component's `properties` map `ki_fp_filters` to `R_*`

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
| `kicad.board.paper-unmodelled` | info | a `paper` child whose name or size the model does not name ("Paper and title block on boards") |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_numbers.py -k closed_set` collects every issue code that `read_board` produces in the board unit tests
- **THEN** each code other than `kicad.version.*` is a key of `ISSUE_CODES` with the severity of this table, and no `model.*` code comes from `read_board`

#### Scenario: Oval drill on a board pad
- **GIVEN** a board pad with `(drill oval 1.2 2.0)`
- **WHEN** the board is read with an `issues` list
- **THEN** the pad has `drill is None`, and `issues` holds one info `kicad.board.kept-opaque` and no `kicad.lib.*` code

#### Scenario: Unmodelled paper is an info
- **GIVEN** a board holding `(paper "USLetter")`
- **WHEN** it is read with an `issues` list
- **THEN** `issues` holds one info `kicad.board.paper-unmodelled`, and `ISSUE_CODES["kicad.board.paper-unmodelled"] == "info"`

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
For a created design, `write_board` SHALL emit exactly the root head set of c0007's `tests/data/kicad/tokens/skeleton.kicad_pcb`, plus `title_block` when one of the seven fields of `Board.title_block` is non-empty:
- `version`, `generator` and `generator_version`;
- `(general (thickness T) (legacy_teardrops no))`, where T is the sum of the `Board.stackup` layer thicknesses, or 1.6 mm without a stack-up;
- `paper`, written by `pcb.paper_node(Board.sheet)`, which gives `(paper "A4")` when `Board.sheet` is `None` ("Paper and title block on boards");
- `title_block`, written by `pcb.title_block_node(Board.title_block)` right after `paper`, only when one of its seven fields is non-empty;
- `layers`, from `Board.layers` and each layer's `kicad` bag;
- `(setup (pad_to_mask_clearance 0))`;
- for target 9 only, the net table.

The content follows in `CANONICAL_ORDER`. `pcb.CREATED_ROOT_HEADS` MUST stay the head set of a created board without a title block; `pcb.CANONICAL_ORDER["kicad_pcb"]` MUST hold `title_block` right after `paper`, and `pcb.CANONICAL_ORDER["title_block"]` MUST be `("title", "date", "rev", "company", "comment")`. `fenolite.backends.kicad.layers.created_layers(copper)` MUST return the 2- and 4-copper-layer sets recorded in `docs/formats/kicad/board.md`, numbered in the 9.0 scheme (`F.Cu` 0, `B.Cu` 2, `In1.Cu` 4, `In2.Cu` 6, `Edge.Cuts` 25), with the KiCad number, type and user name in each layer's `kicad` bag. Any other `copper` value MUST raise `ValueError`. Every head and field name the writer can create MUST match a row of the token inventory, appear in c0007's skeleton, or be listed in `pcb.FLOOR_HEADS`: a closed tuple of names that the 8.0 board format already has, each recorded in `docs/formats/kicad/board.md` with its source and written by the created test board that the triad oracle loads on both majors. `FLOOR_HEADS` MUST include `title_block`, `title`, `date`, `rev`, `company` and `comment` (S-0001; S-0033 at tag 8.0.0), and `tests/_boards.py::created_board()` MUST set `SheetFrameRef("A4")` and a `TitleBlock` whose seven fields are non-empty, so the created test board writes them.

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

#### Scenario: Created board with a Tabloid sheet
- **GIVEN** a created design whose board has `created_layers(2)`, `sheet = SheetFrameRef("Tabloid")` and `title_block = TitleBlock(title="Bench")`
- **WHEN** it is written for target 10
- **THEN** the root's child heads are `version`, `generator`, `generator_version`, `general`, `paper`, `title_block`, `layers`, `setup`, and the `paper` child is `(paper "User" 431.8 279.4)`

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
- When `Board.sheet` differs from `pcb.project_paper` of the root `paper` fragment, the writer MUST re-emit that fragment whole with `pcb.paper_node`. When `Board.title_block` differs from `pcb.project_title_block` of the root `title_block` fragment, the writer MUST rewrite that fragment in place, or insert it, as "Paper and title block on boards" states. Both projections are editable, and an unchanged value MUST keep its fragment.
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

#### Scenario: Paper edited on a read board
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its board's `sheet` changed to `SheetFrameRef("A3")`
- **WHEN** the design is written for target 9
- **THEN** no issue is raised, and the `paper` child is `(paper "A3")` at its source index

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
`fenolite.backends.kicad.embed.place_footprint(defn, *, component, at, rotation=0, side="top", locked=False, key, copper=("F.Cu", "B.Cu"))` SHALL return a `FootprintInstance` for `defn` placed at `at` with stored angle `rotation` on `side`:
- It MUST call `versions.require_editable` on the definition's source format first.
- It MUST emit the definition with `_fpmap.emit_footprint`, drop the children `version`, `generator` and `generator_version`, name the footprint `defn.lib_id`, set its layer to `F.Cu` (top) or `B.Cu` (bottom), and set the value atoms of Reference and Value from `component`.
- Every KiCad uuid MUST be `embed.placement_uuid(key, locator)`, which is `uuid5(FENOLITE_NS, f"kicad-place:{key}:{locator}")`, with `locator` the bare locator of the node in the emitted definition (`/footprint` for the footprint itself).
- The instance MUST be mapped by c0009's board-footprint mapping, so its pads, slots and ids equal those `read_board` gives for the written board. `component_id` MUST be `component.id`, `lib_ref` MUST be `defn.lib_id`, `attributes` MUST hold `defn.kind` (unless `unspecified`) followed by `defn.flags`, and every pad MUST have `net_id = None`.
- `copper` MUST name the copper layers of the board that will hold the instance, in the order of its layer table. Every `*.Cu` pad layer MUST expand to exactly those names, in that order, as `read_board` expands it on that board. The default fits a two-layer board; a caller placing on a board with inner copper layers MUST pass their names (c0011's build passes those of `layers.created_layers(copper)`).
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

#### Scenario: Wildcard pads on a four-layer board
- **GIVEN** `Mini_LED_THT_3mm` read from `tests/data/libs/Mini_v9.pretty`, whose pad `"1"` has layers `*.Cu` and `*.Mask`, and a board made in the test with `layers.created_layers(4)`
- **WHEN** it is placed with `key="D1"` and `copper=("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")`, the board holding it is written for target 10, and the text is read with `read_board`
- **THEN** pad `"1"` of the instance and pad `"1"` of the read-back footprint both have layers `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, `F.Mask` and `B.Mask`, in that order, and the written pad keeps `(layers "*.Cu" "*.Mask")`

#### Scenario: Default copper on a four-layer board is refused
- **GIVEN** the same definition placed with `key="D1"` and the default `copper`, on the same four-layer board
- **WHEN** the board is written for target 10
- **THEN** `write_board` raises `LossyWriteError` with `droppable == False` and one `kicad.board.projection-read-only` issue per wildcard pad ("Projected fields on write"), and no text is returned

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

### Requirement: Project JSON is preserved exactly
`fenolite.backends.kicad.pro.read_project_text(text, *, file="")` SHALL parse a `.kicad_pro` file into a `JsonObject` that keeps the key order of every object and keeps every number as a `JsonNumber` holding its original text, and `write_project_text(data)` SHALL print it back. No float MUST exist at any step.
- Reading MUST raise `FormatError` with `file`: with `offset`, the UTF-8 byte offset of the error, for a syntax error; and with a JSON-pointer `locator` for a duplicate key inside one object (the key's pointer), `NaN`, `Infinity` or `-Infinity` (the value's pointer), and a root that is not an object (`""`).
- `JsonNumber` MUST reject text that does not match the JSON number grammar.
- The printer MUST use two-space indentation, one member or element per line, `"key": value`, `{}` and `[]` for empty containers, strings escaped as JSON with non-ASCII characters kept as UTF-8, and a final newline.
- `read_project_text(write_project_text(d))` MUST be structurally equal to `d`, with numbers compared as text. Byte identity with KiCad's printer is not required.

#### Scenario: Order and spellings survive a round trip
- **GIVEN** the text `{"b": 1.50, "a": {"x": 1e-3, "y": -0}, "z": [1, "s", true, null]}`
- **WHEN** it is read with `read_project_text`, printed with `write_project_text` and read again
- **THEN** the keys are in the order `b`, `a`, `z`, and the numbers are `JsonNumber("1.50")`, `JsonNumber("1e-3")`, `JsonNumber("-0")` and `JsonNumber("1")`

#### Scenario: Printer layout
- **WHEN** `write_project_text({"a": [JsonNumber("1")], "b": {}})` is called
- **THEN** it returns `'{\n  "a": [\n    1\n  ],\n  "b": {}\n}\n'`

#### Scenario: Duplicate key refused
- **WHEN** `read_project_text('{"meta": {"version": 3, "version": 4}}', file="p.kicad_pro")` is called
- **THEN** `FormatError` is raised with `file == "p.kicad_pro"`, `locator == "/meta/version"` and a message naming the key `version`

#### Scenario: Not a number refused
- **WHEN** `read_project_text('{"a": NaN}')` is called
- **THEN** `FormatError` is raised with `locator == "/a"`, and no float is created

#### Scenario: Syntax error located by offset
- **WHEN** `read_project_text('{"a": }')` is called
- **THEN** `FormatError` is raised with `offset == 6` and an empty `locator`

#### Scenario: GUI fixtures round-trip
- **GIVEN** `tests/data/kicad/project/empty_10.kicad_pro` and, when it exists, `empty_9.kicad_pro`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pro.py -k fixture` runs
- **THEN** each file read, printed and read again is structurally equal to the first read, with identical key order and number texts

### Requirement: Project files are synthesised and preserved
`fenolite.backends.kicad.pro.synthesize_project(design, *, target=DEFAULT_TARGET, board_name, allow_lossy=False, issues=None)` SHALL return the text of a complete project file built from a fresh copy of the packaged template of `target` (`backends/kicad/data/project_template_<target>.json`). `update_project(existing_text, design, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return the existing file with only its managed keys changed.

Synthesis MUST set:
- `meta.filename` to `"<board_name>.kicad_pro"`;
- `net_settings.classes` to the template's `Default` entry followed by one lowered entry per model `NetClass` other than `Default`, sorted by name; a model class named `Default` MUST update the four lowered values of the first entry;
- `net_settings.netclass_patterns` to one entry `{"netclass": <class name>, "pattern": <net name>}` per net whose `netclass_id` names a class other than `Default`, sorted by net name.

Every other key, `boards`, `netclass_assignments`, `text_variables` and `pcbnew.page_layout_descr_file` included, MUST keep its template value; `write_triad` then sets `text_variables` and `pcbnew.page_layout_descr_file` from the design with `pro.apply_sheet_keys` ("Projects carry the drawing sheet and text variables"), which leaves the text unchanged when the design sets neither. Synthesis MUST add no key path absent from the template other than those of `pro.PATTERN_ENTRY_PATHS`: `/net_settings/netclass_patterns/*`, `/net_settings/netclass_patterns/*/netclass` and `/net_settings/netclass_patterns/*/pattern`. A `netclass_id` that names no class MUST raise `ConsistencyError` naming `model.unknown-netclass`; callers run `Design.validate()` first, which reports that error as a finding, so the CLI's `FEN-1001` for the exception marks a caller bug.

An update MUST:
- replace the four lowered values of each class entry whose name matches a model class, keeping the original text of a value that is equal in nanometres;
- append the model classes absent from the file, lowered from the file's `Default` entry and sorted by name, and never delete a class entry;
- regenerate the exact-name pattern entries whose pattern equals a model net name and place them first, keeping every other pattern entry verbatim and in order after them;
- add the warning `kicad.project.pattern-conflict` when a kept pattern entry or assignment matches, by `pattern_matches`, a model net that has another class;
- keep every other key, its position, its value and its number spellings, `meta.filename`, `boards` and the version pair included, except where "Project files are gated by target" removes keys.

A classed net whose name contains a character of `pro.UNSAFE_PATTERN_CHARS` (`*` and `?`), or whose exact-name pattern matches, by `pattern_matches`, another net of the design that is not in the same class, MUST raise `LossyWriteError` (`FEN-7001`, `droppable=True`) with the error `kicad.project.pattern-unsafe` naming the net and the other nets. With `allow_lossy=True` the net MUST get no pattern, and `issues` MUST hold the warning `kicad.project.dropped-pattern` instead.

Another requirement of this capability MAY take named keys out of the template-value rule, the added-path rule and the keep rule above, as "Project files carry the board-setup minimums" does for the keys of `lowering.MINIMUM_KEYS`. It names this requirement and the keys, and those keys follow it.

#### Scenario: Synthesis for target 10
- **GIVEN** a design with class HV (clearance `2_000_000` nm), nets `+3V3` and `Net-(R1-Pad1)` in HV, and `GND` with `netclass_id = None`
- **WHEN** `synthesize_project(design, target=10, board_name="bench")` is called
- **THEN** the result has `meta.filename == "bench.kicad_pro"`, class names `["Default", "HV"]`, HV `clearance == JsonNumber("2")`, and exactly the patterns `+3V3` and `Net-(R1-Pad1)` for HV, in that order

#### Scenario: No key outside the template
- **GIVEN** the same design
- **WHEN** it is synthesised for target 9 and for target 10
- **THEN** every key path of each result is a key path of `project_template_9.json` or `project_template_10.json` respectively, with list items written `*`, or one of `pro.PATTERN_ENTRY_PATHS`; the template's `netclass_patterns` is `[]`, so it has no path below `/net_settings/netclass_patterns/*`

#### Scenario: Unknown keys and tuning profiles kept on update
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) holding a top-level key `x_unknown` with value `{"k": 1.000}`, a `tuning_profiles` value and class HV with clearance `2`
- **WHEN** `update_project(text, design, target=10)` runs with HV at clearance `3_000_000` nm
- **THEN** `x_unknown` and `tuning_profiles` are structurally equal to the input with `JsonNumber("1.000")` kept, and the only changed value is the HV clearance, now `JsonNumber("3")`

#### Scenario: Equal value keeps its spelling
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) whose HV clearance is written `2.000`
- **WHEN** it is updated with HV at `2_000_000` nm
- **THEN** the HV clearance is still `JsonNumber("2.000")`

#### Scenario: Unsafe net name refused
- **GIVEN** a design whose net `CLK*` is in class HV
- **WHEN** `synthesize_project(design, target=10, board_name="b")` is called
- **THEN** `LossyWriteError` is raised naming `CLK*`; with `allow_lossy=True` the text is returned, `issues` holds the warning `kicad.project.dropped-pattern`, and no pattern names `CLK*`

#### Scenario: Over-matching name refused
- **GIVEN** a design whose net `D[0]` is in class HV and whose net `D0` has `netclass_id = None`
- **WHEN** `synthesize_project(design, target=10, board_name="b")` is called
- **THEN** `LossyWriteError` is raised with `droppable == True` and the error `kicad.project.pattern-unsafe` naming `D[0]` and `D0`; when `D0` is also in HV, the pattern `D[0]` is written and no issue is added

#### Scenario: Wildcard pattern conflicts with the model
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) with classes HV and LV and the wildcard entry `{"netclass": "LV", "pattern": "+3*"}`, and a design where `+3V3` is in HV
- **WHEN** `update_project` runs with an `issues` list
- **THEN** the wildcard entry is kept after the exact-name entries and `issues` holds one warning `kicad.project.pattern-conflict` naming `+3V3`, HV and LV

### Requirement: Project files are gated by target
`synthesize_project` and `update_project` MUST NOT emit, for target 9, a key path of `pro.TEN_ONLY_PATHS`: the key paths present in `project_template_10.json` and absent from `project_template_9.json`, with list items written `*`. `update_project(…, target=9)` on a project whose pair is (3, 5) or that holds such a path SHALL:
- raise `DowngradeRefusedError(FileKind.BOARD, 10, 9)` (`FEN-7002`) when the design's board has source major 10, because the board's source major drives the refusal;
- otherwise raise `LossyWriteError` (`FEN-7001`, `droppable=True`) with one `kicad.project.too-new-key` error per path and, for the pair (3, 5), one more whose `where` is `/net_settings/meta/version`; with `allow_lossy=True`, remove each path and write `net_settings.meta.version` 4, with one warning `kicad.project.dropped-too-new` per error that the call would have raised.

For target 10, every key MUST be kept.

#### Scenario: 10.0 project for a 9.0 board
- **GIVEN** a project text with pair (3, 5) and a top-level `tuning_profiles` key, and a design whose board was read from a 9.0 file
- **WHEN** `update_project(text, design, target=9)` is called
- **THEN** `LossyWriteError` is raised whose issues include `kicad.project.too-new-key` with `where == "/tuning_profiles"`

#### Scenario: Lossy update for target 9
- **GIVEN** the same inputs
- **WHEN** `update_project(text, design, target=9, allow_lossy=True, issues=found)` is called
- **THEN** the result has no `tuning_profiles` key and no class `tuning_profile` key, `net_settings.meta.version == JsonNumber("4")`, and `found` holds `kicad.project.dropped-too-new` warnings

#### Scenario: Version alone is too new
- **GIVEN** a project text with pair (3, 5) and no key of `TEN_ONLY_PATHS`, and a design whose board was read from a 9.0 file
- **WHEN** `update_project(text, design, target=9)` is called, then again with `allow_lossy=True, issues=found`
- **THEN** the first call raises `LossyWriteError` whose only issue is `kicad.project.too-new-key` with `where == "/net_settings/meta/version"`, and the second returns a text with `net_settings.meta.version == JsonNumber("4")` and `found` holds one `kicad.project.dropped-too-new` warning with that `where`

#### Scenario: Downgrade refused
- **GIVEN** the same project and a design whose board was read from a 10.0 file
- **WHEN** `update_project(text, design, target=9, allow_lossy=True)` is called
- **THEN** `DowngradeRefusedError` is raised with `cli_code == "FEN-7002"`, `kind == FileKind.BOARD`, `source_major == 10` and `target_major == 9`

### Requirement: Project files are read into the model
`fenolite.backends.kicad.pro.read_project(source, *, file="", issues=None)` SHALL accept an `os.PathLike` (a `.kicad_pro` file) or a `str` (file text) and return a `ProjectInfo` with the parsed tree, the version pair, the status, the major, the classes (four values in nm), the patterns, the assignments, the floors, the drawing sheet named by `pcbnew.page_layout_descr_file` and the text variables ("Projects carry the drawing sheet and text variables"). `apply_project(design, info, *, issues=None)` SHALL return a new `Design`:
- `Circuit.netclasses` MUST be one `NetClass` per `classes` entry, in file order, with id `derived_id("cls", "kicad", "netclass:<name>")` and provenance naming the file and the entry's JSON pointer; a value that is not a whole number of nm MUST read as `None` with the info `kicad.project.inexact-value`.
- A net's candidate classes are those of its `netclass_assignments` entry (a string or a list of strings) and of every pattern entry that `pattern_matches` its name. Its `netclass_id` MUST be the candidate of highest priority: the lowest `priority` value, ties in `classes` order. A net with no candidate MUST keep `netclass_id = None`, which means `Default`.
- `pattern_matches(pattern, name)` MUST follow the reading of S-0046: it MUST return true when the pattern matches the whole name as a wildcard (`*` any run, `?` one character, every other character itself, case-sensitive), or when the pattern compiles as a Python regular expression whose `re.fullmatch` matches the name. The flavour and the whole-name matching are `INFERRED` (`H-K-PRO-PATTERNS`).
- Several distinct candidates for one net MUST give the warning `kicad.project.multiple-classes` naming them all, because KiCad forms an aggregate class while the model keeps one; a pattern or assignment naming an absent class MUST give `kicad.project.unknown-class`; an entry of another shape MUST give the info `kicad.project.unread-entry`. Each such entry is skipped.
- A `FUTURE` project MUST be read with the warning `kicad.version.future`.
- `apply_project` MUST also copy the drawing sheet into `Board.sheet.drawing_sheet` and the text variables into `Board.title_block.params`, as "Projects carry the drawing sheet and text variables" states.

#### Scenario: Bench project read back
- **GIVEN** the bench of `tests/_netclass_bench.py` written by `write_triad` for target 10, then read with `read_board` and `read_project`
- **WHEN** `apply_project(design, info)` is called
- **THEN** `Circuit.netclasses` holds `Default` and `HV`, the nets `+3V3` and `SIG1` have the HV id, and `SIG10`, `Net-(R1-Pad1)`, `Net-R1-Pad1`, `D[0]`, `D0` and `GND` have `netclass_id is None`

#### Scenario: Wildcard pattern
- **GIVEN** a project whose only pattern is `{"netclass": "HV", "pattern": "SW?_*"}` and a design with nets `SW1_A` and `SW10`
- **WHEN** the project is applied
- **THEN** `SW1_A` is in HV and `SW10` is not

#### Scenario: Patterns read as wildcards and regular expressions
- **GIVEN** the documented reading of S-0046
- **WHEN** `pattern_matches` is called with (`D[0]`, `D0`), (`D[0]`, `D[0]`), (`net*`, `ne`), (`+3V3`, `+3V3`) and (`SIG1`, `SIG10`)
- **THEN** it returns `True`, `True`, `True`, `True` and `False`

#### Scenario: Two classes for one net
- **GIVEN** a target-10 project (`meta.version` 3, `net_settings.meta.version` 5) whose classes HV and PWR have `priority` 0 and 1, and whose patterns give `+3V3` both HV (`+3V3`) and PWR (`+*`)
- **WHEN** it is applied with an `issues` list
- **THEN** `+3V3` is in HV and `issues` holds one warning `kicad.project.multiple-classes` naming HV and PWR; with the two priorities swapped, `+3V3` is in PWR

#### Scenario: Minimal canary project
- **GIVEN** the text `{}`
- **WHEN** `read_project("{}")` is called
- **THEN** the status is `SUPPORTED`, both versions are `None`, `major is None` and there are no classes

### Requirement: Project issue codes
`fenolite.backends.kicad.proerrors.ISSUE_CODES`, re-exported as `pro.ISSUE_CODES`, SHALL be the closed table of project issue codes and severities. `proerrors` MUST import only `core`, so that `lowering` and `pro` can both use it:

| code | severity |
|---|---|
| `kicad.project.below-floor` | warning |
| `kicad.project.pattern-unsafe` | error |
| `kicad.project.dropped-pattern` | warning |
| `kicad.project.too-new-key` | error |
| `kicad.project.dropped-too-new` | warning |
| `kicad.project.multiple-classes` | warning |
| `kicad.project.unknown-class` | warning |
| `kicad.project.pattern-conflict` | warning |
| `kicad.project.inexact-value` | info |
| `kicad.project.unlowered-field` | info |
| `kicad.project.unread-entry` | info |
| `kicad.project.reserved-variable` | error |
| `kicad.project.dropped-variable` | warning |
| `kicad.project.unread-variable` | info |

Every issue the project functions append MUST use a code from this table or a `kicad.version.*` code of `kicad-version-gating`, and every code MUST match `ISSUE_CODE`. Another requirement of this capability MAY add rows to the table, as "Project files carry the board-setup minimums" does; it names this requirement, and its rows belong to the closed table `ISSUE_CODES`.

#### Scenario: Closed table
- **GIVEN** the issues appended by the project unit tests of task groups 2 to 5
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pro_read.py -k codes` runs
- **THEN** it passes only if every code appended during the project unit tests is a key of `ISSUE_CODES` or starts with `kicad.version.`

### Requirement: Generated projects are coherent
`fenolite.backends.kicad.triad.write_triad(design, *, name, target=DEFAULT_TARGET, existing_project=None, allow_lossy=False, issues=None)` SHALL return exactly the three files `<name>.kicad_pcb`, `<name>.kicad_pro` and `<name>.kicad_dru`:
- the board from c0017's `write_board`;
- the rules from c0018's `lower_rules`, from an empty `RuleSet` when `design.rules is None`;
- the project from `update_project(existing_project, …)` when one is given, else from `synthesize_project(…, board_name=name)`, followed in both cases by `pro.apply_sheet_keys(…, allow_lossy=allow_lossy, issues=issues)` ("Projects carry the drawing sheet and text variables").

An error of any of the three writers MUST abort the whole set. Functions of `fenolite` MUST NOT read or write a `.kicad_prl` file. Every `kicad-cli` run on a generated set MUST go through c0009's `KicadCli`, which works on a temporary copy. The KiCad backend's capability report MUST list `kicad_pro` in `write_kinds` and `lower` in `operations`, and MUST NOT list `kicad_pro` in `read_kinds`, because `Backend.read` returns a `Design` or a `Library` and `read_project` returns a `ProjectInfo`. `KicadBackend.lower(design, *, name, target=None, existing_project=None, allow_lossy=False, issues=None)` MUST return the files of `write_triad` for the same arguments, appending the same issues, `target=None` meaning `default_target`.

#### Scenario: Three files, always
- **GIVEN** a design with no rules
- **WHEN** `write_triad(design, name="blink", target=10)` is called
- **THEN** the keys are exactly `blink.kicad_pcb`, `blink.kicad_pro` and `blink.kicad_dru`, and the rules text is `(version 1)` followed by a newline

#### Scenario: Existing project is updated, not replaced
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) holding the key `x_unknown`
- **WHEN** `write_triad(design, name="b", target=10, existing_project=text)` is called
- **THEN** `b.kicad_pro` still holds `x_unknown` with its original value

#### Scenario: One failing writer aborts the set
- **GIVEN** a design whose classed net is named `CLK*`
- **WHEN** `write_triad(design, name="b", target=10)` is called
- **THEN** `LossyWriteError` is raised and no text is returned

#### Scenario: Capability report
- **GIVEN** the KiCad backend with this change applied
- **WHEN** `uv run fenolite capabilities --json` runs
- **THEN** the `kicad` entry of `result.backends` has `kicad_pro` in `write_kinds`, not in `read_kinds`, and `lower` in `operations`

#### Scenario: Backend lowering returns the triad
- **GIVEN** a design with no rules
- **WHEN** `KicadBackend().lower(design, name="blink")` is called
- **THEN** it returns exactly `blink.kicad_pcb`, `blink.kicad_pro` and `blink.kicad_dru`, equal to `write_triad(design, name="blink", target=10)`

#### Scenario: Backend lowering keeps the issues
- **GIVEN** `bench_design(target=10, hv_clearance=500_000)` and `text`, a target-10 project from `pro.template(10)` whose `board.design_settings.rules.min_clearance` is 1.5
- **WHEN** `KicadBackend().lower(design, name="b", existing_project=text, issues=issues)` is called with an empty list
- **THEN** `issues` is not empty, holds the warning `kicad.project.below-floor` naming `HV`, and equals what `write_triad(design, name="b", target=10, existing_project=text, issues=other)` puts in `other`

### Requirement: Project format facts are documented
`docs/formats/kicad/project.md` SHALL record, in Fenolite's own words and in fact tables with the header `| fact | source | label | hypothesis |`:
- the roles of `.kicad_pro` and `.kicad_prl`, and the absence of a public specification;
- the key diff of the two GUI-saved fixtures and the version pair of each;
- the class keys, the pattern entry keys and the floor keys Fenolite reads or writes;
- the managed keys and the update rules;
- the census counts and the answer on tuning profiles.

Every row MUST cite an id of `docs/evidence/sources.md`, and every row below `KICAD-VERIFIED` and `CORPUS-VERIFIED` MUST name an `H-K-PRO-*` hypothesis or `H-K-TOK-RULES-SILENT`. The page MUST state that the templates come only from the GUI saves and that the demos and S-0066 are used for key names and counts only.

#### Scenario: Fact tables checked
- **GIVEN** `docs/formats/kicad/project.md` written by task 1.3, and a `project.md` entry in `HYPOTHESIS_IDS` of `tests/unit/test_format_facts.py` that accepts only `H-K-PRO-*` and `H-K-TOK-RULES-SILENT`
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** both pass, and a `project.md` row below the verified levels that names another hypothesis fails the first

### Requirement: Path property on placed footprints
`fenolite.backends.kicad.embed.with_property(defn, *, name, value) -> FootprintDef` SHALL return a copy of the footprint definition `defn` with one hidden property added, and `embed.PATH_PROPERTY` SHALL be `"fenolite.path"`.
- The new property MUST be appended after the last `property` child of the definition, in the form `(property "<name>" "<value>" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid U) (effects (font (size 1 1) (thickness 0.15))))`, the form of the `Datasheet` property of the `Mini_v9` footprints and of boards written by 10.0.6 (S-0058). `U` is replaced by `place_footprint`.
- The entry `name -> value` MUST be added to the copy's `FootprintDef.properties`, and `defn` MUST stay unchanged.
- Every token of the property MUST be an 8.0-floor name, so the emit check of `kicad-version-gating` passes for targets 9 and 10.
- `place_footprint` needs no change for the property: it MUST give the new node a uuid from the key and its locator, and on the bottom side flip its layer to `B.Fab`, as for every other child.
- Locator indices count earlier siblings with the same head (`kicad-sexpr`), so appending the property MUST NOT change the locator or the placement uuid of any other node of the copy.
- `read_board` MUST project the property into `Component.properties["fenolite.path"]`, through c0009's footprint mapping.
- The build writes the component path as the value on every built footprint while `H-K-BUILD-PATHPROP` holds. If a `build-pathprop-t9` or `build-pathprop-t10` probe refutes `H-K-BUILD-PATHPROP`, the build MUST write no such property, and c0019 matches by uuid only.

#### Scenario: Property appended last
- **GIVEN** `Mini_R_0603` read from `tests/data/libs/Mini_v9.pretty`
- **WHEN** `with_property(defn, name=PATH_PROPERTY, value="power/R1")` is placed with key `power/R1` and written for target 10
- **THEN** the footprint's last `property` child is `fenolite.path` with value `"power/R1"`, layer `F.Fab` and `(hide yes)`, and `read_board` of the text gives `properties["fenolite.path"] == "power/R1"`

#### Scenario: No other uuid moves
- **GIVEN** the same definition placed with key `R1`, once plain and once through `with_property`
- **WHEN** the uuids of every node other than the new property are compared
- **THEN** they are equal

#### Scenario: Bottom side
- **GIVEN** the definition with the property added
- **WHEN** it is placed with `side="bottom"`
- **THEN** the property node has layer `B.Fab` and keeps `(hide yes)`

#### Scenario: Emit check is clean on both targets
- **GIVEN** a board made in the test with `layers.created_layers(2)` that holds `Mini_R_0603`, `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm` from `tests/data/libs/Mini_v9.pretty`, each placed through `with_property` and `place_footprint`, `D1` on the bottom side
- **WHEN** the board node that `write_board` emits for target 9, and the one for target 10, is checked with `versions.check_emittable` for the same target
- **THEN** both calls return no issue

### Requirement: Drawing sheet files are read
`fenolite.backends.kicad.wks.read_drawing_sheet(source, *, file="", name=None, issues=None)` SHALL accept an `os.PathLike` (a `.kicad_wks` file), a `str` (file text) or a parsed `Node`, and return a `DrawingSheet`.
- The roots `kicad_wks`, `page_layout` and `drawing_sheet` MUST be read; a legacy root (c0007's `LEGACY_WORKSHEET_ROOTS`) MUST add the info `kicad.wks.legacy-root`. The version MUST be checked as boards check it: `info = versions.inspect(root, file=file)`, then `versions.require_readable(info, file=file)`, with `versions.version_issues(info)` added to `issues`.
- `setup` MUST map to `SheetSetup` (`textsize`, `linewidth`, `textlinewidth`, `left_margin`, `right_margin`, `top_margin`, `bottom_margin`). `line` and `rect` MUST map to `SheetShape` with `kind` `line` and `rect`, and `tbtext` and `bitmap` to `SheetText` and `SheetBitmap`, with `name`, `comment`, the points and their corner atom (none means `rb`), `linewidth`, `repeat`, `incrx`, `incry`, `incrlabel` (absent means `label_step = 1`, KiCad's default; `H-K-WKS-REPEAT`), `option`, `font` (`size`, `bold`, `italic`), `justify`, `rotate` (degrees, stored in µdeg), `maxlen`, `maxheight`, `scale` (stored in parts per million) and `pngdata` (stored as base64 text).
- `polygon` items and items with an unknown head MUST be opaque items at their position. Unmodelled children of a modelled item (`face`, `color`, unknown heads) MUST be opaque slots under nested relative locators (`tbtext[3]/font[0]`).
- Each modelled child MUST be re-emitted with the writer's emitter and compared with the original. A child that is not reproduced tree-equal (an explicit `rbcorner`, `(pos 10.000 10)`) MUST become an opaque slot whose value stays projected into the model, with the info `kicad.wks.kept-opaque`. On write, such a slot MUST be re-emitted verbatim while its projection equals the model, and from the model otherwise.
- An item MUST stay opaque, with the info `kicad.wks.kept-opaque` naming the reason, when one of its lengths is not a whole number of micrometres, an angle is not a whole number of µdeg, its scale is not a whole number of parts per million, one of its children holds a value atom outside `wks.VALUE_ATOMS`, its text holds a variable that the token map cannot read, or its text holds a `%` followed by an ASCII letter. KiCad still resolves these legacy text codes (`%T` draws the title) in `page_layout` and in `kicad_wks` 20231118 files alike (observed on 10.0.6 on 2026-10-01; `H-K-WKS-PCT`), so such a text is neither a literal nor a neutral token.
- Texts MUST be read through the inverse of `wks.KICAD_TOKENS`: each mapped variable reads as its neutral token, any other `${X}` with X matching `[A-Za-z_][A-Za-z0-9_]*` and not in `wks.RESERVED_VARIABLES` reads as `{param:X}`, and literal braces read as `{{` and `}}`. A KiCad-only variable (`${SHEETNAME}`, `${SHEETPATH}`, `${LAYER}`, `${KICAD_VERSION}`, `${KIPRJMOD}`, `${COMMENT4}` … `${COMMENT9}`) or a malformed `${` keeps the item opaque.
- `rebuild_drawing_sheet(sheet)` SHALL return the source tree of a read sheet, with the source root and header, modelled items emitted from the model and opaque items and slots verbatim at their positions. For every authored fixture under `tests/data/kicad/sheets/` and `tests/data/kicad/tokens/` and the corpus row `kicad-demo-10-0-6-wks-01`, with `t` its text, `tree_equal(rebuild_drawing_sheet(read_drawing_sheet(t)), parse(t))` MUST hold, and `wks.opaque_count` MUST count its opaque items and slots.
- Reading third-party worksheets is `INFERRED` (one corpus origin plus authored fixtures).

#### Scenario: Every modelled kind read
- **GIVEN** the authored fixture `tests/data/kicad/sheets/all_items.kicad_wks`
- **WHEN** it is read
- **THEN** its items include a `SheetShape` of each kind (`line`, `rect`), a `SheetText` and a `SheetBitmap`, every corner and scope value occurs, and a `tbtext` without corner atom has `pos.corner == "rb"`

#### Scenario: Tokens read back as neutral text
- **GIVEN** a sheet holding `(tbtext "${TITLE} / ${COMMENT1} / ${LOT_NO} / {x}" (pos 10 10))`
- **WHEN** it is read
- **THEN** the item is a `SheetText` with `text == "{title} / {doc_id} / {param:LOT_NO} / {{x}}"`

#### Scenario: Explicit default corner kept
- **GIVEN** a sheet holding `(tbtext "A" (pos 10 10 rbcorner))`
- **WHEN** it is read with an `issues` list and rebuilt with `rebuild_drawing_sheet`
- **THEN** the item is a `SheetText` with `pos == SheetPoint("rb", 10_000_000, 10_000_000)`, its `pos` child is an opaque slot, `issues` holds one info `kicad.wks.kept-opaque`, and the rebuilt tree is tree-equal to the source

#### Scenario: KiCad-only variable keeps the item opaque
- **GIVEN** a sheet holding `(tbtext "${SHEETNAME}" (pos 10 10))`
- **WHEN** it is read with an `issues` list
- **THEN** the item is opaque and `issues` holds one info `kicad.wks.kept-opaque`

#### Scenario: Sub-micrometre length on a modelled item
- **GIVEN** the authored fixture `tests/data/kicad/sheets/sub_um.kicad_wks`, holding `(line (start 50.0006 30 ltcorner) (end 60 30 ltcorner))` and one `tbtext` with whole-micrometre values
- **WHEN** it is read with an `issues` list and rebuilt
- **THEN** the `line` is an opaque item, `issues` holds one info `kicad.wks.kept-opaque` naming the length, the `tbtext` is a `SheetText`, and the rebuilt tree is tree-equal to the source

#### Scenario: Legacy percent code keeps the item opaque
- **GIVEN** a sheet holding `(tbtext "Title: %T" (pos 10 10))`
- **WHEN** it is read with an `issues` list
- **THEN** the item is opaque and `issues` holds one info `kicad.wks.kept-opaque`

#### Scenario: Demo worksheet read
- **GIVEN** the fetched corpus row `kicad-demo-10-0-6-wks-01`, a `page_layout` root whose lengths that are not whole micrometres all sit in its single `polygon` item and whose texts use `%` codes
- **WHEN** `uv run pytest tests/corpus/test_wks_corpus.py` runs (`needs_corpus`)
- **THEN** the `polygon` and every text with a `%` code are opaque and counted by `opaque_count`, and the RT1 condition holds

#### Scenario: Legacy root
- **GIVEN** c0007's fixture `tests/data/kicad/tokens/page_layout.kicad_wks`
- **WHEN** it is read with an `issues` list
- **THEN** `issues` holds the info `kicad.wks.legacy-root`, and `rebuild_drawing_sheet` returns a tree whose root is `page_layout`

### Requirement: Drawing sheet files are written
`fenolite.backends.kicad.wks.write_drawing_sheet(sheet, *, target=DEFAULT_TARGET, allow_lossy=False)` SHALL return a `WriteResult` whose text is one `.kicad_wks` file that both majors load.
- The root MUST be `kicad_wks`, followed by `(version 20231118)` (S-0032) and `(generator "fenolite")`, with no `generator_version`; a legacy root is re-rooted. For a read sheet, the writer MUST first call `versions.require_editable(versions.inspect(<source root>))`, as boards do: a sheet read from a `FUTURE` file MUST raise `FutureFormatError` (`FEN-3002`) and is never re-headed to 20231118, because future files are read-only (`kicad-version-gating`). The output MUST NOT depend on `target`: the text for target 9 and target 10 MUST be byte-identical, and `target` selects only the emit check.
- Children MUST follow `wks.CANONICAL_ORDER` (header, `setup`, then the items in `items` order, opaque items of a read sheet at their positions). The text MUST be printed with `dumps(style="kicad")`.
- Lengths MUST be written in millimetres with `Atom.from_nm`, rotations as the shortest exact decimal of degrees. The corner atoms MUST be `ltcorner`, `lbcorner` and `rtcorner`, and `rb` MUST be written without a corner atom. Scopes MUST be written `(option page1only)` and `(option notonpage1)`. `repeat`, `incrx` and `incry` MUST be written only when they differ from 1, 0 and 0, and `incrlabel` only when `label_step` is not 1, because KiCad steps labels by 1 when `incrlabel` is absent (`H-K-WKS-REPEAT`). A bitmap MUST be written as `pngdata` with at most 32 space-separated hex bytes per `data` row (S-0035).
- Texts MUST be written through `wks.KICAD_TOKENS`: `{title}` → `${TITLE}`, `{doc_id}` → `${COMMENT1}`, `{revision}` → `${REVISION}`, `{sheet}` → `${#}`, `{sheets}` → `${##}`, `{date}` → `${ISSUE_DATE}`, `{organization}` → `${COMPANY}`, `{responsible}` → `${COMMENT2}`, `{approver}` → `${COMMENT3}`, `{filename}` → `${FILENAME}`, `{paper}` → `${PAPER}`, `{param:X}` → `${X}`, and `{{`/`}}` → literal braces.
- The writer MUST refuse, with `LossyWriteError` (`FEN-7001`, `droppable=False`), a modelled length that is not a multiple of 1 000 nm (`kicad.wks.below-resolution`), a `{param:X}` with X in `wks.RESERVED_VARIABLES` (`kicad.wks.param-reserved`), and a neutral text whose KiCad form holds a `${`, or a `%` followed by an ASCII letter, that no token produced (`kicad.wks.literal-variable`; KiCad would resolve either, `H-K-WKS-PCT`).
- `versions.check_emittable(root, FileKind.WORKSHEET, target)` MUST run on the final tree. Each `kicad.token.uninventoried` warning MUST become the error `kicad.wks.uninventoried`, and each value atom outside `wks.VALUE_ATOMS` (corners, options, justify values, font flags) the error `kicad.wks.unknown-value`. Both MUST raise `LossyWriteError` (`FEN-7001`, `droppable=True`) with a hint naming `--allow-lossy`; with `allow_lossy=True`, the opaque item holding them MUST be dropped with the warning `kicad.wks.dropped-item` naming its locator. Modelled items MUST produce only inventoried names and listed values. The requirements of `kicad-version-gating` are unchanged.
- `KicadBackend.write_sheet(sheet, *, target=None, allow_lossy=False)` MUST return `write_drawing_sheet` for the same arguments, `target=None` meaning `default_target`. The capability report MUST list `kicad_wks` in `write_kinds` and MUST NOT list it in `read_kinds`, because `Backend.read` returns a `Design` or a `Library`.
- The evidence of a write is `INFERRED` (`wks.WRITE_EVIDENCE`, `H-K-WKS-CORNER`): a write runs no `kicad-cli`, and the oracle of `kicad-oracle` verifies the constructs, not each written file.

#### Scenario: Header and target independence
- **GIVEN** the sheet built from `iso5457_generic`
- **WHEN** it is written for target 9 and for target 10
- **THEN** both texts are byte-identical and start with `(kicad_wks (version 20231118) (generator "fenolite")`, and `check_emittable` on the parsed text gives no issue for either target

#### Scenario: Unknown head refused, then dropped
- **GIVEN** a sheet read from a text holding `(frobnicate 1)` as an item
- **WHEN** it is written, then written again with `allow_lossy=True`
- **THEN** the first call raises `LossyWriteError` with `droppable == True` and an issue `kicad.wks.uninventoried`; the second returns a text without `frobnicate` and a warning `kicad.wks.dropped-item`

#### Scenario: Unknown value atom refused
- **GIVEN** a sheet read from a text holding an opaque item with `(option bogus)`
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.wks.unknown-value`

#### Scenario: Sub-micrometre length refused
- **GIVEN** a built sheet with a `SheetShape` of kind `line` ending at `SheetPoint("lt", 500, 0)`
- **WHEN** it is written with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with `droppable == False` and an issue `kicad.wks.below-resolution`

#### Scenario: Reserved parameter refused
- **GIVEN** a built sheet with a `SheetText` `"{param:TITLE}"`, a second with the text `"${{x}}"` and a third with the text `"Title: %T"`
- **WHEN** each is written
- **THEN** the first raises `LossyWriteError` with `kicad.wks.param-reserved`, and the second and third with `kicad.wks.literal-variable`

#### Scenario: Label step written only when not 1
- **GIVEN** a built sheet with two repeated `SheetText` items `"A"`, one with `SheetRepeat(count=3, step_y=5_000_000)` and one with `SheetRepeat(count=3, step_y=5_000_000, label_step=0)`
- **WHEN** it is written and read back
- **THEN** the first `tbtext` has no `incrlabel` child, the second has `(incrlabel 0)`, and the read items equal the built ones

#### Scenario: Future worksheet not rewritten
- **GIVEN** a sheet read from a `kicad_wks` text whose `version` is newer than every supported version
- **WHEN** it is read with an `issues` list and then written
- **THEN** `issues` holds the warning `kicad.version.future`, and the write raises `FutureFormatError` (`FEN-3002`)

#### Scenario: Capability report
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the `kicad` entry has `kicad_wks` in `write_kinds` and not in `read_kinds`

### Requirement: Drawing sheet issue codes
`fenolite.backends.kicad.wks.ISSUE_CODES` SHALL be the closed table of drawing-sheet issue codes, and every issue that `read_drawing_sheet` and `write_drawing_sheet` add MUST use one of its codes or a `kicad.version.*` code of `kicad-version-gating`:

| code | severity | when |
|---|---|---|
| `kicad.wks.kept-opaque` | info | an item or child kept opaque on read, with the reason |
| `kicad.wks.legacy-root` | info | a `page_layout` or `drawing_sheet` root on read |
| `kicad.wks.uninventoried` | error | a name with no inventory row on write |
| `kicad.wks.unknown-value` | error | a value atom outside `VALUE_ATOMS` on write |
| `kicad.wks.below-resolution` | error | a modelled length that is not a whole micrometre on write |
| `kicad.wks.param-reserved` | error | a `{param:X}` with X a reserved KiCad variable |
| `kicad.wks.literal-variable` | error | a `${`, or a `%` followed by an ASCII letter, in the written text that no token produced |
| `kicad.wks.dropped-item` | warning | an opaque item dropped under `allow_lossy` |

#### Scenario: Closed table
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_wks_write.py -k codes` collects every code that the drawing-sheet unit tests produce
- **THEN** each is a key of `ISSUE_CODES` with the severity of this table or starts with `kicad.version.`

### Requirement: Paper and title block on boards
`fenolite.backends.kicad.pcb` SHALL project the root children `paper` and `title_block` into `Board.sheet` and `Board.title_block` on read, and SHALL write them from those fields, as the MODIFIED "Created board header" and "Projected fields on write" require. Both MUST stay opaque root slots, so the closed list of "Modelled board content", every `opaque_count` and RT1 are unchanged.
- `project_paper(node, *, issues=None)` MUST return `SheetFrameRef(<name>, portrait=<portrait atom present>)` for `(paper "A0")` … `(paper "A5")`. For `(paper "User" W H)` it MUST return `Letter`, `Legal` or `Tabloid` when W x H equals that size of `PAPER_SIZES` in either orientation (portrait when W < H), and otherwise `SheetFrameRef("custom", width=W, height=H)`. Any other name (`USLetter`, `A` … `E`, …), and a size that is not a whole number of nm, MUST give `None` and add the info `kicad.board.paper-unmodelled` to `issues`; `read_board` passes its own `issues` list. A board without `paper` has `Board.sheet = None`.
- `project_title_block(node)` MUST map `title`, `date`, `rev`, `company`, `comment 1`, `comment 2` and `comment 3` through `pcb.TITLE_BLOCK_FIELDS` to `title`, `date`, `revision`, `organization`, `doc_id`, `responsible` and `approver`. `comment 4` … `comment 9` and unknown children MUST stay in the fragment unmapped. A board without `title_block` has `Board.title_block = None`. `Board.sheet.drawing_sheet` and `TitleBlock.params` come from the project ("Projects carry the drawing sheet and text variables").
- `paper_node(sheet)` MUST write `(paper "A3")` with a `portrait` atom when portrait, `(paper "A4")` for `None`, and `(paper "User" W H)` in millimetres for `Letter`, `Legal`, `Tabloid` and `custom`, with W > H for a US size unless it is portrait. KiCad's own names `USLetter`, `USLegal` and `USLedger` MUST NOT be written (`H-K-PCB-PAPER`).
- `title_block_node(block)` MUST write the non-empty fields among the seven, in the order `title`, `date`, `rev`, `company`, `comment 1`, `comment 2`, `comment 3`.
- On a read board, the writer MUST project the fragment again and compare it with the model. An unchanged value MUST keep its fragment. A changed `paper` MUST be re-emitted whole with `paper_node`. A changed `title_block` MUST be rewritten in place: the value atom of a changed mapped child replaced, a newly set field inserted at the place its order gives among the mapped children, an emptied field removed, and every other child kept tree-equal at its position; `None` counts as `TitleBlock()`, and a board read without `title_block` gains `title_block_node(block)` right after `paper`. These are projections re-emitted from changed model values in the sense of "Slots for lossless round-trip".

#### Scenario: Named paper read
- **GIVEN** the authored board with its `paper` child replaced by `(paper "A3" portrait)`
- **WHEN** it is read
- **THEN** `board.sheet == SheetFrameRef("A3", portrait=True)` and the `paper` child is an `Opaque` slot

#### Scenario: User paper equal to Letter
- **GIVEN** a board holding `(paper "User" 215.9 279.4)`
- **WHEN** it is read
- **THEN** `board.sheet == SheetFrameRef("Letter", portrait=True)`

#### Scenario: Unmodelled paper kept
- **GIVEN** a board holding `(paper "USLetter")`
- **WHEN** it is read with an `issues` list and written again for its own target
- **THEN** `board.sheet is None`, `issues` holds the info `kicad.board.paper-unmodelled`, and the written `paper` child is tree-equal to the source

#### Scenario: Title block projected and edited in place
- **GIVEN** a board whose `title_block` holds `(title "A")`, `(rev "1")` and `(comment 4 "keep")`
- **WHEN** it is read, `title_block.title` is changed to `"B"` and `title_block.organization` set to `"Lab"`, and the design is written
- **THEN** the written `title_block` holds `(title "B")`, `(rev "1")`, `(company "Lab")` after `rev`, and `(comment 4 "keep")` unchanged, and no other root child changed

#### Scenario: Corpus boards unchanged
- **WHEN** `uv run pytest tests/corpus/test_board_rt1.py` runs (`needs_corpus`)
- **THEN** it passes, and every corpus board's `opaque_count` equals the value before this change

### Requirement: Projects carry the drawing sheet and text variables
`fenolite.backends.kicad.pro.apply_sheet_keys(project_text, design, *, allow_lossy=False, issues=None)` SHALL return the project text with `pcbnew.page_layout_descr_file` (`pro.PAGE_LAYOUT_POINTER`) and `text_variables` set from the design, and `triad.write_triad` SHALL run it on the project text after `synthesize_project` or `update_project`. The three codes below are rows of the closed table of "Project issue codes".
- When `Board.sheet.drawing_sheet` is not `None`, `pcbnew.page_layout_descr_file` MUST be set to it verbatim; otherwise the existing value MUST be kept. `schematic.page_layout_descr_file` MUST NOT be touched.
- Each key of `TitleBlock.params` MUST add or replace one member of `text_variables`. New members MUST be appended after the existing ones, sorted by name, and no member MUST be deleted. The key paths `pro.SHEET_KEY_PATHS` (`/text_variables/*`) MUST be the only paths that `write_triad` adds beyond the template's and `pro.PATTERN_ENTRY_PATHS`.
- A name in `wks.RESERVED_VARIABLES` MUST give the error `kicad.project.reserved-variable` and raise `LossyWriteError` (`FEN-7001`, `droppable=True`); with `allow_lossy=True` the variable MUST be left out with the warning `kicad.project.dropped-variable`.
- When the design sets neither key (no `Board.sheet.drawing_sheet` and no parameter), the text MUST come back unchanged, so every c0010 scenario holds byte for byte.
- `read_project` MUST fill `ProjectInfo.drawing_sheet` (`None` for an absent or empty value) and `ProjectInfo.text_variables` (name and value pairs in file order; a member whose value is not a string gives the info `kicad.project.unread-variable` and is skipped, so c0010's `kicad.project.unread-entry` keeps its meaning). `apply_project` MUST copy the first into `Board.sheet.drawing_sheet` when `Board.sheet` is not `None`, and the second into `TitleBlock.params`, creating `TitleBlock(params=…)` when `Board.title_block` is `None` and there are variables.
- A triad written by `write_triad` without `existing_project` MUST read back with `sheet` and `title_block` equal to the design's in normal form (`H-K-PRO-WKS`): `Board.sheet = None` reads back as `SheetFrameRef("A4")`, the `(paper "A4")` of a created board, and a `TitleBlock` whose seven fields are empty and which has no parameter reads back as `None`, because no `title_block` is written for it.

| code | severity |
|---|---|
| `kicad.project.reserved-variable` | error |
| `kicad.project.dropped-variable` | warning |
| `kicad.project.unread-variable` | info |

#### Scenario: Nothing to set
- **GIVEN** a design whose board has no `sheet` and no `title_block`
- **WHEN** `write_triad(design, name="b", target=10)` is called
- **THEN** `b.kicad_pro` equals `synthesize_project(design, target=10, board_name="b")` byte for byte

#### Scenario: Both keys written and read back
- **GIVEN** a design whose board has `sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")` and `title_block = TitleBlock(title="Bench", params={"LOT": "7"})`
- **WHEN** the triad is written for target 10, then read with `read_board`, `read_project` and `apply_project`
- **THEN** the project has `pcbnew.page_layout_descr_file == "frame.kicad_wks"` and `text_variables == {"LOT": "7"}`, and the read board's `sheet` and `title_block` equal the design's

#### Scenario: Default presentation reads back in normal form
- **GIVEN** a design whose board has no `sheet` and `title_block = TitleBlock()`
- **WHEN** the triad is written for target 10, then read with `read_board`, `read_project` and `apply_project`
- **THEN** the read board has `sheet == SheetFrameRef("A4")` and `title_block is None`

#### Scenario: Existing variables kept
- **GIVEN** an existing project text whose `text_variables` is `{"ZZ": "1", "LOT": "6"}`, and a design with params `{"LOT": "7", "AA": "2"}`
- **WHEN** `write_triad(design, name="b", target=10, existing_project=text)` is called
- **THEN** `text_variables` is `{"ZZ": "1", "LOT": "7", "AA": "2"}`, in that order

#### Scenario: Reserved variable refused
- **GIVEN** a design with params `{"TITLE": "x"}`
- **WHEN** `write_triad(design, name="b", target=10)` is called, then again with `allow_lossy=True` and an `issues` list
- **THEN** the first call raises `LossyWriteError` with `kicad.project.reserved-variable`; the second writes no `TITLE` member and `issues` holds `kicad.project.dropped-variable`

### Requirement: Drawing sheet format facts are documented
`docs/formats/kicad/worksheet.md` SHALL hold the worksheet facts in a table with the header `| fact | source | label | hypothesis |`: the roots and header constant, the setup and item heads, corner atoms and the default corner, repeat and its clipping, label increment, page-1 options, value atoms, text variables and their resolution on a board, the legacy `%` text codes that KiCad still resolves, the stated 1 µm resolution and what KiCad draws for finer lengths, `pngdata` rows, the silent fallback for missing files, and the SVG form used by the oracle. Every row MUST cite a source id, and every row below `KICAD-VERIFIED` or `CORPUS-VERIFIED` MUST name a hypothesis.
- `docs/formats/kicad/board.md` MUST gain rows for the `paper` forms and the `title_block` children and their order.
- `docs/formats/sheets.md` MUST state, in Fenolite's words and with a registered source id per row, the paper sizes (S-0077, S-0079) and the frame, zone and title-block figures used by the examples (S-0077, S-0078). No ISO text or figure is reproduced.
- `tests/unit/test_format_facts.py` MUST check `worksheet.md` with the rules above and `sheets.md` for a registered source id per row.

#### Scenario: Fact tables checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes and its collected pages include `docs/formats/kicad/worksheet.md` and `docs/formats/sheets.md`

#### Scenario: Unsourced row refused
- **GIVEN** a row of `worksheet.md` with label `INFERRED` and no hypothesis
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it fails naming the row

### Requirement: Project files carry the board-setup minimums
`fenolite.backends.kicad.pro.synthesize_project` and `pro.update_project` SHALL write the minimums that `lowering.lower_minimums(design.rules, target=target, current=…, issues=…)` returns into `board.design_settings.rules` (`pro.MINIMUM_POINTER`) of the project text they return, so that `triad.write_triad` and `KicadBackend.lower` ship them. For the keys of `lowering.MINIMUM_KEYS`, this requirement takes precedence over the template-value rule and the keep rule of "Project files are synthesised and preserved". The five codes below extend the closed table of "Project issue codes".
- The minimums MUST be written before the net classes are lowered, so that the floors that `lower_netclass` receives are the written values and `kicad.project.below-floor` compares with them.
- After the net classes are lowered, both functions MUST call `lowering.class_conflicts(design.rules, target=target, clearances=…, model_names=…, issues=…)` with the clearance of every class entry of the project they return and the names of `design.circuit.netclasses`.
- `current` MUST be the value of each key in the project being written (`pro.project_minimums`), and the value of the target's template (`pro.template(target)`) for a key that the project lacks.
- A key whose existing value is a JSON number equal in nanometres to the written value MUST keep its text. Any other value MUST be replaced by the exact millimetre text of the nanometres as a `JsonNumber` (`lowering.millimetres`), and the writer MUST NOT produce a float.
- A key that an existing project lacks MUST be appended after the members of `board.design_settings.rules`, in the order of the table. A missing `board`, `design_settings` or `rules` object MUST be appended to its parent. When a key must be written and one of these members is not an object, `FormatError` MUST be raised with its JSON pointer.
- An update MUST add the info `kicad.project.minimum-replaced` for each written key whose existing value is absent, is not a JSON number, or differs in nanometres, naming the key, the old text (or `absent`), the new value and the governing rule. Synthesis adds no such info.
- Every other key, its position and its number spelling MUST stay as read, or as in the template for synthesis. When `lower_minimums` returns no key, the text MUST be the text returned for the same design with `rules=None`, byte for byte.
- `pro.project_minimums(data, *, issues=None)` SHALL return the nanometre value of each key of `lowering.MINIMUM_KEYS` that `board.design_settings.rules` holds as a JSON number. A value that is not a whole number of nm MUST read as absent with the info `kicad.project.inexact-value`.
- Minimums MUST NOT be lifted into rules: `read_project` and `apply_project` MUST leave `Design.rules` as it is, so that a design written by `write_triad` and read back holds the rules of its `.kicad_dru` and nothing more, and writing it again gives the same minimums.

| code | severity | when |
|---|---|---|
| `kicad.project.minimum-replaced` | info | an update writes a minimum that is absent from the file, is not a number there, or differs in nanometres |
| `kicad.project.minimum-kept` | info | the governing board-wide rule has a severity other than `error` or no `min`, so the minimum is kept |
| `kicad.project.rule-below-minimum` | warning | a rule asks for less than a minimum that Fenolite does not write, on a target where the minimum governs custom rules |
| `kicad.project.class-shadowed` | warning | a board-wide clearance rule overrides a larger class clearance, on a target where custom rules govern class items |
| `kicad.project.default-over-rule` | warning | the `Default` class, which the model does not set, keeps unclassed nets above a board-wide clearance rule, on a target where class clearances govern above custom rules |

#### Scenario: Synthesis writes the fab minimums
- **GIVEN** a design whose rules are the five board-wide rules of the scenario "Fab rule set" of `rules-model`
- **WHEN** `synthesize_project(design, target=10, board_name="b")` is called
- **THEN** `board.design_settings.rules` holds `min_clearance == JsonNumber("0.1")`, `min_track_width == JsonNumber("0.127")`, `min_via_diameter == JsonNumber("0.45")`, `min_through_hole_diameter == JsonNumber("0.2")` and `min_copper_edge_clearance == JsonNumber("0.3")`, every other member equals the template's with the same number text, and the members keep the template's order

#### Scenario: Classes compare with the written minimums
- **GIVEN** a board-wide `clearance` rule with `min=300_000` and a class HV with `clearance=200_000`
- **WHEN** the design is synthesised for target 10 with an `issues` list
- **THEN** `issues` holds the warning `kicad.project.below-floor` naming HV, `0.2`, `min_clearance` and `0.3`, although the template's `min_clearance` is 0

#### Scenario: Class conflicts use the written classes
- **GIVEN** a board-wide `clearance` rule with `min=100_000` and a model class HV with `clearance=2_000_000`, and no model class `Default`
- **WHEN** the design is synthesised for target 10 with an `issues` list, once with `RULES_OVER_CLASSES == frozenset({9, 10})` and once with it empty
- **THEN** the first `issues` holds `kicad.project.class-shadowed` naming HV and no `kicad.project.default-over-rule`; the second holds `kicad.project.default-over-rule` naming the template's `Default` clearance `0.2` and no `kicad.project.class-shadowed`

#### Scenario: No board-wide rule, no change
- **GIVEN** `bench_design(target=10)` of `tests/_netclass_bench.py`, whose only rule is the canary on `net CANARY_A`, and a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) whose `min_track_width` is written `0.25`
- **WHEN** it is synthesised for target 10, and the project text is updated with it
- **THEN** the synthesised `board.design_settings.rules` equals the template's member for member, and the updated text keeps `min_track_width == JsonNumber("0.25")` and adds no `kicad.project.minimum-replaced`

#### Scenario: Update keeps spelling, replaces and appends
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) whose rules object holds `min_track_width` written `0.127000`, `min_through_hole_diameter` written `0.3` and no `min_copper_edge_clearance`, and a design with board-wide `track_width` (`min=127_000`), `hole_size` (`min=250_000`) and `edge_clearance` (`min=300_000`) rules
- **WHEN** `update_project(text, design, target=10, issues=found)` is called
- **THEN** `min_track_width` keeps `JsonNumber("0.127000")`, `min_through_hole_diameter == JsonNumber("0.25")`, `min_copper_edge_clearance == JsonNumber("0.3")` is the last member, every other member is unchanged, and `found` holds `kicad.project.minimum-replaced` for `min_through_hole_diameter` and `min_copper_edge_clearance` only

#### Scenario: Rules member that is not an object
- **GIVEN** a target-10 project text whose `board.design_settings.rules` is `[]`, and a design with one board-wide `track_width` rule
- **WHEN** `update_project` is called
- **THEN** `FormatError` is raised with `locator == "/board/design_settings/rules"`

#### Scenario: Minimums stay out of the model's rules
- **GIVEN** the design of "Synthesis writes the fab minimums" written by `write_triad(design, name="b", target=10)`
- **WHEN** `b.kicad_pro` is read with `read_project` and applied with `apply_project` to a design read from `b.kicad_pcb`
- **THEN** the applied design's `rules` is the read design's `rules`, `project_minimums(info.data)` returns the five written values, and `write_triad` of the original design with `existing_project` set to the text of `b.kicad_pro` keeps the five number texts and adds no `kicad.project.minimum-replaced`

### Requirement: Round-trip verdict
`fenolite.backends.kicad.roundtrip.rt1(text, *, file="") -> RoundTrip` SHALL compute in `src` the RT1 of "Same-version rebuild" on a board text `t`, as c0009 Decision 3 defines it:
- `tree_equal`: `tree_equal(rebuild_board(read_board(t)), parse(t))`;
- `model_equal`: the canonical JSON of `read_board(dumps(rebuild_board(read_board(t))))` equals that of `read_board(t)` when every `provenance` is set to `None`;
- `opaque_equal`: `opaque_count` and `opaque_digests` are equal on both reads.

`passed` MUST be the conjunction of the three, and `opaque_count` the count of the first read. `rt1` MUST raise the reader's errors (`FormatError` and its subclasses) unchanged.
- `RoundTrip.difference` MUST be the locator that c0006's `sexpr.first_difference(rebuilt, parsed)` returns when `tree_equal` is false, otherwise `model` when `model_equal` is false, otherwise `opaque` when `opaque_equal` is false, and `""` when RT1 passes. No second locator function is added.
- `KicadBackend.validate(path, *, issues=None) -> Validation` MUST return `Validation(read, rt1(text, file=…))` for a `.kicad_pcb` file, `read` being what `KicadBackend.read(path)` returns. For any other kind it MUST raise `ValueError` naming the kind.
- RT1 runs on the board only; comparing the board with `.fenolite/` belongs to c0019.

#### Scenario: Authored board passes
- **GIVEN** `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_roundtrip.py -k passes` calls `rt1` on its text
- **THEN** `passed` is true, `difference` is `""`, and `opaque_count` equals `pcb.opaque_count(read_board(text))`

#### Scenario: Altered pad located
- **GIVEN** `rebuild_board` patched to change the size of one pad of the authored board
- **WHEN** `rt1` runs on the authored board text
- **THEN** `passed` and `tree_equal` are false, and `difference` names that pad's locator

#### Scenario: Board validated through the backend
- **WHEN** `KicadBackend().validate(Path("tests/data/kicad/board/two_layer.kicad_pcb"))` is called
- **THEN** `validation.read` equals `KicadBackend().read(path)` and `validation.roundtrip.passed` is true

#### Scenario: Footprint file refused
- **WHEN** `KicadBackend().validate(Path("tests/data/libs/Mini.pretty/Mini_R_0603.kicad_mod"))` is called
- **THEN** a `ValueError` naming `kicad_mod` is raised

### Requirement: Read and write throughput is measured
`tests/unit/backends/kicad/test_throughput.py::test_read_write_5mib` SHALL measure, when `FENOLITE_CENSUS_OUT` names a file and only then, how fast Fenolite reads and writes a board of at least 5 MiB, and SHALL assert no time limit.
- The board MUST be built in memory by `tests/_boards.py::large_board(min_bytes=5 * 2**20)` from created entities with deterministic ids on the two-copper layer stack, and written with `write_board` for target 10.
- The test MUST time `read_board(text)` and `write_board(design, target=10)` with `time.perf_counter_ns` (S-0090), keeping the best of three runs of each, and MUST then measure the peak traced memory of one read and one write with `tracemalloc` (S-0091) in a separate pass.
- It MUST write the size in bytes, both times, the MiB per second of each, both peaks, the Python version and the platform through `tests/_boards.py::census`, and the numbers MUST be copied into `docs/evidence/kicad-board-read.md` with the machine described.
- Without `FENOLITE_CENSUS_OUT` the test MUST skip, so the `unit` job does not pay for it.

#### Scenario: Benchmark recorded
- **GIVEN** `FENOLITE_CENSUS_OUT` naming a file in a temporary folder
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_throughput.py -rA` runs
- **THEN** the census file holds a board of at least 5 242 880 bytes with read and write times, MiB per second and peak memory, and `git status --porcelain` is unchanged

#### Scenario: Skipped by default
- **GIVEN** `FENOLITE_CENSUS_OUT` unset
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_throughput.py` runs
- **THEN** the test is skipped and no board is built

### Requirement: Edge.Cuts outlines chain exactly
`tests/corpus/test_outline_census.py::test_edge_cuts_chain` (marker `needs_corpus`) and `tests/kicad/board/test_board_upgraded.py::test_outline_census` (markers `needs_kicad`, `needs_corpus`, `kicad_min_major(10)`) SHALL measure whether the board outlines of the corpus chain into closed rings by exact endpoint equality, which answers c0005's open question on a snapping tolerance for `assemble_rings`.
- **Pieces.** For each board, every root `Graphic` on a layer of kind `edge` MUST become pieces: a `line` one `Segment`, an `arc` one `Arc` through its three points, a `rect` four `Segment`s and a `polygon` one `Segment` per side. A `circle` is a closed ring by itself and MUST be counted, not chained. Zero-length segments MUST be counted and left out, as callers of `assemble_rings` do. Edge items inside footprints stay opaque and MUST only be counted.
- **Outcome.** `assemble_rings(pieces)` either returns rings, which MUST be counted, or raises `GeometryError`, whose code MUST be counted. For `geometry.open-contour`, the smallest distance between two loose endpoints MUST be recorded in whole nanometres, rounded up, in the buckets up to 1 µm, up to 10 µm, and larger.
- **Origins.** The 21 readable non-heavy native demos and the 3 upgraded third-party copies MUST be counted per origin through `tests/_boards.py::census` and copied into `docs/evidence/kicad-board-read.md`.
- **Verdict.** `H-G-EDGE-EXACT` holds when no board of either origin has two loose endpoints within 1 µm of each other. The tests MUST NOT fail on any outcome; the hypothesis row records it.

#### Scenario: Native demos measured
- **GIVEN** the `rt0` corpus cached
- **WHEN** `uv run pytest tests/corpus/test_outline_census.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** the census file holds, for the native demos, the boards whose outline chained, the failure codes with their counts, and the gap buckets

#### Scenario: Upgraded copies measured
- **GIVEN** the cached third-party rows and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_board_upgraded.py -k outline_census` runs
- **THEN** the same counts are written for origin `third-party`

#### Scenario: Small gap bucketed
- **GIVEN** four `Graphic` lines on `Edge.Cuts` that form a square, with one end moved 500 nm away from its neighbour
- **WHEN** `uv run pytest tests/corpus/test_outline_census.py -k gap` runs the census function on them
- **THEN** it records `geometry.open-contour` and a smallest gap of 500 nm in the bucket up to 1 µm

### Requirement: Footprint fields on boards
`read_board` SHALL map every placed `property` child of a board footprint to a `FootprintField` of `FootprintInstance.fields`, in file order, and SHALL keep the property's value in the component (`design-model`, "Footprint fields").
- A property is placed when it holds a name atom, a value atom, `at`, `layer` and an `effects` whose `font` holds `size`. Only the first property of a name in one footprint is a field. A later property with the same name MUST stay an `Opaque` slot of the footprint, with the info `kicad.board.kept-opaque`.
- The values MUST come from the node:
  - `name` from its first atom; `position` from the X and Y of `at`; `rotation = pad_angle_from_board(stored, instance.rotation)`, `stored` being the angle of `at`, or 0 when it is absent;
  - `layer` from the first atom of `layer`;
  - `visible` false for a `hide` child other than `(hide no)`, in the node or in its `effects`, and for a bare `hide` atom in the node or in its `effects`, and true otherwise; a `hide` inside `effects` keeps that `effects` a projected slot;
  - `size = Size(W, H)` from the font's `(size H W)`, and `thickness` from the font's `thickness`, or `None` when it is absent;
  - `h_justify`, `v_justify` and `mirrored` from the atoms `left`, `right`, `top`, `bottom` and `mirror` of `effects/justify`.
- The footprint's slot for the node MUST be `Modeled("fields")`. The field MUST carry its own slot list in `ext["kicad"]`: the name atom, `at`, `layer`, `hide`, `uuid` and `effects` modelled; the value atom an `Opaque` slot whose value is projected into the component; every other child, such as `unlocked`, opaque at its position. The modelled children follow "Modelled children are reproducible", so an `effects` that the emitter does not reproduce, for example one with `bold` or a font `face`, stays a projected slot.
- The field's id MUST be `derived_id("fld", "kicad", "<key>:field:<name>")`, `<key>` being the native id from which the footprint's pad ids derive, and `native_ids["kicad"]` MUST be the property's uuid.
- A property that is not placed, and every `fp_text`, MUST be read as before this change. A property whose `at` or font holds a length or angle that is not a whole number of nm or µdeg MUST stay a projected slot of the footprint, with the info `kicad.board.inexact-length` or `kicad.board.inexact-angle` ("Exact numbers on boards").
- `rebuild_board` MUST rebuild each field from its slot list, so that RT1 ("Same-version rebuild") keeps holding.

#### Scenario: Reference of a rotated top footprint
- **WHEN** `tests/data/kicad/board/two_layer.kicad_pcb` is read
- **THEN** `R1` has the fields `Reference` and `Value`, in that order; `Reference` has `position == Point(0, -1_430_000)`, `rotation == 0`, layer `F.SilkS`, `visible`, `size == Size(1_000_000, 1_000_000)`, `thickness == 150_000`, both justifications `center` and `mirrored == False`; its slot list holds the value atom `"R1"` as an `Opaque` slot; and the component of `R1` has `ref == "R1"`

#### Scenario: Field of a bottom footprint
- **WHEN** the same board is read
- **THEN** the `Reference` field of `D1` has `position == Point(1_270_000, 2_960_000)`, `rotation == 0` (stored 30° minus the footprint's 30°), layer `B.SilkS` and `mirrored == True`

#### Scenario: Hidden field with justification
- **GIVEN** a copy of the authored board, built in the test, whose `Value` property of `R1` holds `(hide yes)` after its `layer` and `(justify left bottom)` in its `effects`
- **WHEN** it is read
- **THEN** that field has `visible == False`, `h_justify == "left"` and `v_justify == "bottom"`, and its `hide` and `effects` children are `Modeled` slots

#### Scenario: Eight-format hidden field
- **GIVEN** a board with header `20240108`, built in the test, whose only footprint holds `(property "Value" "X" (at 0 1 0) (layer "F.Fab") hide (uuid "…") (effects (font (size 1 1) (thickness 0.15))))`
- **WHEN** it is read with an `issues` list
- **THEN** no issue has severity `error`, the `Value` field has `visible == False`, and the `hide` atom is an `Opaque` slot of the field

#### Scenario: Bare and repeated properties
- **GIVEN** a copy of the authored board, built in the test, whose `R1` holds `(property ki_fp_filters "R_*")` and two placed properties named `MPN`
- **WHEN** it is read with an `issues` list
- **THEN** `R1` has the fields `Reference`, `Value` and `MPN` only; the bare property and the second `MPN` are `Opaque` slots of the footprint; `issues` holds one info `kicad.board.kept-opaque` locating the second `MPN`; and the component's `properties` map `ki_fp_filters` to `R_*`

#### Scenario: Round trip with fields
- **GIVEN** the authored board and the fetched corpus
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_rebuild.py -k rt1 tests/corpus/test_board_rt1.py tests/corpus/test_board_fields.py` runs
- **THEN** RT1 holds for every board, and every `Reference` and `Value` property of the 21 corpus boards is a field

### Requirement: Footprint fields are written
`write_board` SHALL write each `FootprintField` of a footprint as a `property` node from the model.
- The node MUST hold the name atom, the value atom, `(at X Y A)` with the field's position and the board angle `A = pad_angle_to_board(rotation, footprint rotation)`, written also when it is 0, `(layer "L")`, `(hide yes)` only when the field is not visible, `(uuid "U")`, and `(effects (font (size H W) (thickness T)) (justify …))`. `thickness` is left out when it is `None`. `justify` holds `left` or `right`, then `top` or `bottom`, then `mirror`, each only when set, and is left out when none is.
- A read field MUST be rebuilt from its slot list: unchanged modelled children keep their text, opaque children stay at their positions, and a child new to the field follows "Canonical insertion of new fields" with `CANONICAL_ORDER["property"]`, which MUST be `name`, `value`, `at`, `layer`, `hide`, `uuid`, `effects`. `pcb.FLOOR_HEADS` MUST include `hide`.
- The value atom MUST follow "Projected fields on write": it takes the component's `ref` or `value` for `Reference` and `Value`, and any other changed value gives `kicad.board.projection-read-only`.
- A child that the reader kept as a projected slot MUST keep its fragment while the model agrees with it; an `at` whose angle lies outside [0°, 360°), such as the `-90` that KiCad writes for some fields, agrees with the model when it is equal modulo 360°. A changed value of such a child MUST give `kicad.board.projection-read-only`, unless the child differs from the emitter's output for the old value only in spelling; a `(hide no)` child and an `at` with plain numbers count as spellings. A bare `hide` atom cannot be removed: showing such a field gives `kicad.board.projection-read-only`.
- A created footprint MUST take the placement of each property that the writer creates from the field of the same name, when `fields` holds one; the property's uuid is then `kicad_uuid(field)`.
- A field without a slot list on a read footprint, a field of a created footprint whose name the component lacks, and a second field with the name of another field of the same footprint MUST raise `ValueError` naming the field. A read field removed from the model leaves its node out, and the component's property then gives `kicad.board.projection-read-only`; for `Reference` and `Value`, whose values "Projected fields on write" does not compare, this holds when the footprint has more field nodes than fields and no node holds the name.

#### Scenario: Field moved and turned on a read board
- **GIVEN** the authored board read with `read_board`, whose `R1` `Reference` field is given `position = Point(0, -2_000_000)` and `rotation = 90_000_000`
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that property node holds `(at 0 -2 180)` and is otherwise tree-equal to the source node

#### Scenario: Hidden, resized and justified
- **GIVEN** the authored board read, whose `R1` `Value` field is given `visible = False`, `size = Size(800_000, 800_000)`, `thickness = 120_000` and `h_justify = "left"`
- **WHEN** the design is written for target 10 and the text is read again
- **THEN** the node holds `(hide yes)` between `layer` and `uuid`, `(font (size 0.8 0.8) (thickness 0.12))` and `(justify left)`, and the re-read field equals the model's

#### Scenario: Bottom field justified
- **GIVEN** the authored board read, whose `D1` `Reference` field is given `h_justify = "right"`
- **WHEN** it is written for target 9
- **THEN** that node's `effects` holds `(justify right mirror)`

#### Scenario: Unchanged fields
- **GIVEN** the authored board read with `read_board`
- **WHEN** it is written for target 9
- **THEN** every `property` node of the text is tree-equal to its source node

#### Scenario: Created footprint with fields
- **GIVEN** `tests/_boards.py::created_board()`, whose footprint has a `Reference` field at `Point(0, -1_500_000)` and a hidden `Value` field
- **WHEN** it is written for targets 9 and 10 and each text is read with `read_board`
- **THEN** the re-read fields equal the model's, and `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens` passes with `hide` in `FLOOR_HEADS`

#### Scenario: Field added to a read footprint
- **GIVEN** the authored board read, with a new field `MPN` without slots appended to `R1`
- **WHEN** `write_board` is called
- **THEN** a `ValueError` naming `MPN` is raised

### Requirement: Footprint field helpers
The module `fenolite.backends.kicad.fields` SHALL convert fields between the model frame and the board frame, and SHALL place a field beside its footprint's courtyard.
- `field_anchor(fp, field) -> Point` MUST equal `Transform.placement(fp.position, fp.rotation).apply(field.position)`, and `field_angle(fp, field) -> Udeg` MUST equal `(field.rotation + fp.rotation) mod 360°`.
- `set_field(fp, name, *, anchor=None, angle=None, layer=None, visible=None, size=None, thickness=None, justify=None, mirrored=None) -> FootprintInstance` MUST return a copy of `fp` whose field `name` takes every given value. `anchor` and `angle` are board-frame values. The field keeps its position when `field_anchor` already gives `anchor`, and otherwise stores `Transform.placement(fp.position, fp.rotation).inverse().apply(anchor)`; it stores `pad_angle_from_board(angle, fp.rotation)` as its rotation. `justify` is a pair `(h_justify, v_justify)`. Every other field and value MUST stay unchanged, and an unknown name MUST raise `KeyError` naming it.
- `place_outside(fp, name, *, side, gap=DEFAULT_GAP) -> FootprintInstance` MUST take `B`, the bounding box of the points of `placed_extent(fp).own` (c0028's `fenolite.backends.kicad.frame`, its pad fallback included), or the point box at `fp.position` when it holds no ring. It MUST then set through `set_field` the board angle 0 and, with `(cx, cy)` the centre of `B` rounded half to even and `d = gap + t // 2`, `t` being the field's thickness or 0:
  - `side="top"`: anchor `(cx, B.y0 − d)`, `v_justify = "bottom"`, `h_justify = "center"`;
  - `side="bottom"`: anchor `(cx, B.y1 + d)`, `v_justify = "top"`, `h_justify = "center"`;
  - `side="left"`: anchor `(B.x0 − d, cy)`, `h_justify = "right"`, or `"left"` when the field is mirrored, and `v_justify = "center"`;
  - `side="right"`: anchor `(B.x1 + d, cy)`, `h_justify = "left"`, or `"right"` when the field is mirrored, and `v_justify = "center"`.
- `DEFAULT_GAP` MUST be 250 000 nm, a Fenolite choice. A negative `gap` MUST raise `ValueError`.
- `fields.EVIDENCE` MUST be `INFERRED` with the hypotheses `H-K-FIELD-FRAME`, `H-K-FIELD-JUSTIFY` and `H-K-FIELD-OUTSIDE`, and MUST stay `INFERRED`, because the bench does not cover every string.

#### Scenario: Anchor and angle of a rotated field
- **GIVEN** the authored board read with `read_board`
- **WHEN** `field_anchor` and `field_angle` are called for the `Reference` field of `R1` (footprint at 20 mm, 15 mm and 90°)
- **THEN** they return `Point(18_570_000, 15_000_000)` and `90_000_000`

#### Scenario: Board-frame round trip
- **GIVEN** `Mini_R_0603` placed with `place_footprint` at 0°, 30° and 90° on the top and at 30° on the bottom
- **WHEN** `set_field(fp, "Reference", anchor=field_anchor(fp, f), angle=field_angle(fp, f))` is called with its `Reference` field `f`
- **THEN** the returned footprint equals `fp`

#### Scenario: Outside on top of a rotated part
- **GIVEN** the authored board read, whose `R1` courtyard box on the board is (19.27 mm, 13.52 mm) to (20.73 mm, 16.48 mm)
- **WHEN** `place_outside(r1, "Reference", side="top")` is called
- **THEN** the field's anchor is `Point(20_000_000, 13_195_000)`, its board angle 0, `v_justify == "bottom"` and `h_justify == "center"`, so it stores `position == Point(1_805_000, 0)` and `rotation == 270_000_000`

#### Scenario: Mirrored field on the left
- **GIVEN** the authored board read
- **WHEN** `place_outside(d1, "Reference", side="left")` is called
- **THEN** the field has `h_justify == "left"` and `mirrored == True`, and its anchor's X is the left edge of `D1`'s box minus 325 000 nm

#### Scenario: Negative gap
- **WHEN** `place_outside(r1, "Reference", side="top", gap=-1)` is called
- **THEN** a `ValueError` is raised

### Requirement: Zone settings are read
The board reader SHALL model these children of a `zone` that becomes a `Zone`, through the new module `fenolite.backends.kicad.zones` (`project_settings`):
- `connect_pads`: its atom gives `settings.connection` (no atom → `thermal`, `yes` → `solid`, `no` → `none`, `thru_hole_only` → `thru_hole_only`), and its `(clearance C)` child gives `settings.clearance`;
- `min_thickness` → `settings.min_thickness`;
- `fill`: the atom `yes` gives `Zone.filled`; `(mode hatch)` gives `fill_mode == "hatched"`; `thermal_gap` → `thermal_gap`; `thermal_bridge_width` → `thermal_spoke_width`; `smoothing` (`chamfer`, `fillet`) and `radius` → `smoothing` and `smoothing_radius`; `island_removal_mode` 0, 1 and 2 → `always`, `never` and `below_area`; `island_area_min`, in square millimetres, converted exactly to square nanometres; `hatch_thickness`, `hatch_gap`, `hatch_orientation`, `hatch_smoothing_level`, `hatch_smoothing_value`, `hatch_border_algorithm` and `hatch_min_hole_area` → the fields of `settings.hatch`;
- `(locked yes)` → `Zone.locked`.

Further rules:
- An absent child MUST give the `ZoneSettings` defaults for its part, `filled == False` when `fill` is absent, `locked == False` when `locked` is absent, and no slot.
- Each modelled child MUST pass c0009's reproducibility check ("Modelled children are reproducible") against the emitter of "Zone settings are written" for the major of the file (`versions.major_for`). For major 9, the emitter writes `island_removal_mode` and `island_area_min` only when the mode is not `always`. For major 10, it writes `island_removal_mode` always and `island_area_min` only for `below_area`.
- A child that the emitter does not reproduce, that is repeated, or that holds an unknown atom, child or value, MUST stay an `Opaque` slot. The values it does hold MUST be projected into `Zone.settings`, `Zone.filled` or `Zone.locked`, and the info `kicad.board.kept-opaque` MUST name the reason. A value that cannot be read keeps its default. An inexact length or angle follows "Exact numbers on boards"; an area that is not a whole number of square nanometres keeps its child opaque with `kicad.board.kept-opaque`.
- A rule area MUST keep these children opaque, as before. The children `hatch`, `filled_areas_thickness`, `attr`, `placement` and every other child of a zone MUST stay opaque.

#### Scenario: Ten-format pour
- **GIVEN** a `20260206` board whose zone holds `(connect_pads yes (clearance 0.3)) (min_thickness 0.2) (fill yes (thermal_gap 0.4) (thermal_bridge_width 0.35) (island_removal_mode 2) (island_area_min 2.5))`
- **WHEN** it is read with `read_board`
- **THEN** the zone has `connection == "solid"`, `clearance == 300_000`, `min_thickness == 200_000`, `thermal_gap == 400_000`, `thermal_spoke_width == 350_000`, `island_removal == "below_area"`, `min_island_area == 2_500_000_000_000` and `filled == True`, and its `connect_pads`, `min_thickness` and `fill` children are `Modeled` slots

#### Scenario: Nine-format island forms
- **GIVEN** a `20241229` board with one zone whose `fill` holds `(island_removal_mode 1) (island_area_min 5)` and another whose `fill` holds `(island_removal_mode 0)`
- **WHEN** it is read with an `issues` list
- **THEN** the first zone has `island_removal == "never"`, `min_island_area == 5_000_000_000_000` and a `Modeled` `fill` slot; the second has `island_removal == "always"` and an `Opaque` `fill` slot, and `issues` holds one info `kicad.board.kept-opaque`

#### Scenario: Hatched fill
- **GIVEN** a `20260206` zone whose `fill` is `(fill yes (mode hatch) (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0) (hatch_thickness 0.8) (hatch_gap 1.2) (hatch_orientation 45) (hatch_border_algorithm min_thickness) (hatch_min_hole_area 0.3))`
- **WHEN** it is read
- **THEN** `fill_mode == "hatched"`, `hatch == ZoneHatch(thickness=800_000, gap=1_200_000, orientation=45_000_000, border="min_thickness", min_hole_area="0.3")`, and the `fill` child is a `Modeled` slot

#### Scenario: Unknown fill child
- **GIVEN** a `20260206` zone whose `fill` is `(fill yes (thermal_gap 0.6) (thermal_bridge_width 0.5) (frobnicate 1))`
- **WHEN** it is read with an `issues` list
- **THEN** `thermal_gap == 600_000` and `filled == True`, the `fill` child is an `Opaque` slot, and `issues` holds one info `kicad.board.kept-opaque`

#### Scenario: Settings absent
- **GIVEN** a `20241229` board whose zone has no `connect_pads`, `min_thickness` or `fill` child
- **WHEN** it is read
- **THEN** the zone has `settings == ZoneSettings()`, `filled == False` and no slot for those children, and the three RT1 conditions of "Same-version rebuild" hold

#### Scenario: Locked zone
- **GIVEN** a `20260206` zone holding `(locked yes)`
- **WHEN** it is read
- **THEN** `locked == True`, and the `locked` child is a `Modeled` slot

#### Scenario: Demo zones are modelled
- **GIVEN** the fetched corpus and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** `uv run pytest tests/corpus/test_board_census.py -k zone_settings` runs
- **THEN** every zone of the 21 readable native demos and of the upgraded third-party copies has `Modeled` `connect_pads`, `min_thickness` and `fill` slots, and the counts per origin are written to that file

### Requirement: Zone settings are written
`write_board` SHALL write the settings of every `Zone` from the model, in the form of the target, through `zones.emit_settings`:
- `connect_pads`: the atom of `connection` (none for `thermal`, `yes`, `no`, `thru_hole_only`), then `(clearance C)`;
- `(min_thickness T)`;
- `fill`: the atom `yes` when `Zone.filled`; `(mode hatch)` for a hatched fill; `thermal_gap`; `thermal_bridge_width`; `smoothing` and `radius` when `smoothing` is not `none`; the island form of the target (target 9: `island_removal_mode` and `island_area_min` only when the mode is not `always`; target 10: `island_removal_mode` always, and `island_area_min` only for `below_area`); and for a hatched fill `hatch_thickness`, `hatch_gap`, `hatch_orientation`, `hatch_smoothing_level` and `hatch_smoothing_value` when the level is above 0, `hatch_border_algorithm` and `hatch_min_hole_area`;
- `(locked yes)` when `Zone.locked`.

Created and read zones differ:
- **Created zone.** A created zone MUST hold these children, in this order: `net` and, for target 9, `net_name`, as before; `locked` when set; `layer` or `layers`; `uuid`; `name` when set; `(hatch edge 0.5)`; `priority` when not 0; `connect_pads`; `min_thickness`; `(filled_areas_thickness no)`, for target 9 only; `fill`; `polygon`; `filled_polygon`. `pcb.CANONICAL_ORDER` MUST hold this zone order, and the entries `connect_pads` (its atom `connection`, then `clearance`) and `fill` (its atom `filled`, then the children in the order above). `pcb.POSITIONAL` MUST name the two atoms.
- **Read zone.** A `Modeled` child MUST be emitted from the model in the target's form. A child that the zone does not have MUST be inserted at its canonical position only when its part of the model differs from the defaults (`filled == True` counts), so an unchanged zone gains no child. An `Opaque` child whose values were projected MUST follow "Projected fields on write": it is kept verbatim while its projection equals the model. When only `Zone.filled` differs and the atoms of the opaque `fill` child are the plain form (no atom, or `yes` alone), the child MUST be written with its `yes` atom set from the model and its lists as read. Any other change gives `kicad.board.projection-read-only` naming `settings`, `filled` or `locked` and the locator.
- **Rule areas** MUST be written as before.

Every name the writer can now create MUST be in c0007's skeleton, in the token inventory or in `pcb.FLOOR_HEADS` ("Created board header"). `FLOOR_HEADS` gains `mode`, `smoothing`, `radius`, `island_removal_mode`, `island_area_min`, `hatch_thickness`, `hatch_gap`, `hatch_orientation`, `hatch_smoothing_level`, `hatch_smoothing_value`, `hatch_border_algorithm`, `hatch_min_hole_area` and `zone_connect`. Each of them is present in the board format at tag 8.0.0 (S-0033) and recorded in `docs/formats/kicad/board.md`. `tests/_boards.py::created_board()` MUST write each of them for target 9. It gains a second zone `GND_HATCH` (net `GND`, `F.Cu`, hatched with `hatch.smoothing_level == 1`, `smoothing="fillet"` with a radius of 0.5 mm, `island_removal="below_area"`, `locked=True`), and pad `"1"` of `U1` gets `zone_connection="solid"`.

#### Scenario: Created zone for target 10
- **GIVEN** a created zone with `settings == ZoneSettings(clearance=300_000, connection="solid", thermal_gap=400_000, thermal_spoke_width=350_000)`, `filled == False` and no name
- **WHEN** it is written for target 10 and the text is parsed
- **THEN** between its `uuid` and its `polygon` the zone holds exactly `(hatch edge 0.5) (connect_pads yes (clearance 0.3)) (min_thickness 0.25) (fill (thermal_gap 0.4) (thermal_bridge_width 0.35) (island_removal_mode 0))`

#### Scenario: Created zone for target 9
- **GIVEN** the same zone
- **WHEN** it is written for target 9 and the text is parsed
- **THEN** between its `uuid` and its `polygon` the zone holds exactly `(hatch edge 0.5) (connect_pads yes (clearance 0.3)) (min_thickness 0.25) (filled_areas_thickness no) (fill (thermal_gap 0.4) (thermal_bridge_width 0.35))`

#### Scenario: Fill flag follows the model
- **GIVEN** a created zone with one `ZoneFill` and `filled == True`, and `tests/data/kicad/board/two_layer.kicad_pcb` read with `read_board` whose zone `GND_B` is given `filled = False` and no fills
- **WHEN** both are written for target 9
- **THEN** the created zone's `fill` starts `(fill yes`, and the `fill` of `GND_B` is `(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))` at its source position

#### Scenario: Clearance edited on a read zone
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and the clearance of zone `GND_B` changed to 300 000 nm
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that zone holds `(connect_pads (clearance 0.3))` at the source position of `connect_pads`, and every other child of the zone is tree-equal to the source

#### Scenario: A zone without settings stays without them
- **GIVEN** the board of the scenario "Settings absent" read with `read_board`
- **WHEN** it is written for target 9 unchanged, and again after its clearance is changed to 300 000 nm
- **THEN** the first text holds no `connect_pads`, `min_thickness` or `fill` in the zone, and the second holds `(connect_pads (clearance 0.3))` before the zone's `polygon` and still no `min_thickness` or `fill`

#### Scenario: Projected settings are read-only
- **GIVEN** the zone of the scenario "Unknown fill child" read with `read_board`, and its `thermal_gap` changed to 700 000 nm
- **WHEN** it is written for target 10
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.projection-read-only` naming `settings` and the locator of the `fill` child

#### Scenario: Fill flag cleared on an opaque fill child
- **GIVEN** the zone of the scenario "Unknown fill child" read with `read_board`, and its `filled` set to false
- **WHEN** it is written for target 10
- **THEN** its `fill` child is `(fill (thermal_gap 0.6) (thermal_bridge_width 0.5) (frobnicate 1))`, and no issue is reported

#### Scenario: Upgrade to target 10 writes the island mode
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`
- **WHEN** it is written for target 10
- **THEN** the `fill` of `GND_B` is `(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))`, and the zone holds no `filled_areas_thickness`

#### Scenario: Created tokens stay known
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens` runs, and the created test board is written for targets 9 and 10 and checked with `check_emittable`
- **THEN** the test passes with the extended `FLOOR_HEADS`, and both checks return no issue

### Requirement: Pad zone connection
The shared footprint mapping (`_fpmap`) SHALL model a pad's `(zone_connect N)` as `Pad.zone_connection`, for board pads and for `.kicad_mod` pads alike: 0 → `none`, 1 → `thermal`, 2 → `solid` and 3 → `thru_hole_only`.
- A pad without the child MUST have `zone_connection is None` and no slot.
- Any other value MUST keep the child as an `Opaque` slot, with `zone_connection is None` and the info `kicad.board.kept-opaque` on a board or `kicad.lib.kept-opaque` in a footprint file.
- A pad with several `zone_connect` children MUST keep each of them as an `Opaque` slot with the same info, and `zone_connection` is projected from the first one. A model value that differs from what the opaque children hold MUST give `kicad.board.projection-read-only` on a board, and the read-only error of `mod.write_footprint` in a footprint file.
- The emitters MUST write `(zone_connect N)` from the model. A created pad writes it after `net` and before `uuid` (`CANONICAL_ORDER["pad"]`); a read pad without the child gets it only when the value is not `None`.
- `embed.place_footprint` MUST keep the value of the definition's pads, and `mod.write_footprint` MUST write it.
- A footprint-level `zone_connect` child MUST stay opaque in both readers.

#### Scenario: Solid exposed pad on a board
- **GIVEN** a `20260206` board whose footprint pad holds `(zone_connect 2)`
- **WHEN** it is read and written for target 10
- **THEN** the pad has `zone_connection == "solid"` and a `Modeled` slot for the child, and the written pad node is tree-equal to the source

#### Scenario: Library pad placed
- **GIVEN** a copy of `Mini_R_0603`, built in the test, whose pad `"1"` holds `(zone_connect 0)`
- **WHEN** it is read with `read_footprint` and placed with `place_footprint`, and the board is written for target 10
- **THEN** the definition's pad and the instance's pad have `zone_connection == "none"`, and the written pad holds `(zone_connect 0)`

#### Scenario: Unknown code
- **GIVEN** a board pad holding `(zone_connect 7)`
- **WHEN** it is read with an `issues` list
- **THEN** `zone_connection is None`, the child is an `Opaque` slot, and `issues` holds one info `kicad.board.kept-opaque`

#### Scenario: Created pad
- **GIVEN** a created pad with `zone_connection == "thru_hole_only"` on net `GND`
- **WHEN** its footprint is written for target 9
- **THEN** the pad holds `(zone_connect 3)` after its `net` child and before its `uuid` child

#### Scenario: Library footprints round trip
- **GIVEN** the fetched footprint corpus
- **WHEN** `uv run pytest tests/corpus/test_footprint_rt.py` runs
- **THEN** it passes, and every pad that holds `zone_connect` 0 to 3 has a `Modeled` slot for it

### Requirement: Design rules for the copper check
`fenolite.backends.kicad.copperrules.design_rules_from_texts(design, *, project_text, rules_text, major=versions.DEFAULT_TARGET, file_stem="", issues=None) -> DesignRules` SHALL apply the texts of a project file and a rules file, each `None` when absent, to a board design read with `read_board`:
- **Project.** It MUST read `project_text` with c0010's `pro.read_project(project_text, file=f"{file_stem}.kicad_pro")`, return `pro.apply_project(design, info)` as the design, and return `info.floors.get("clearance")` as `min_clearance`.
- **Rules.** It MUST read `rules_text` with c0018's `dru.read_rules(rules_text, file=f"{file_stem}.kicad_dru")` and set the design's `rules` to the result. `opaque_clearance_rules` MUST count the rule items of `dru.parse_rules(rules_text)` that hold a `clearance` constraint and were kept opaque.
- **Tables.** `rules_over_classes` MUST be `major in lowering.RULES_OVER_CLASSES` and `floor_over_rules` MUST be `major in lowering.FLOOR_OVER_RULES["min_clearance"]`, c0026's tables measured per major (`H-K-PRO-MIN-CLASS`, `H-K-PRO-MIN-RULE-2`). As shipped, the first holds 9 and 10 and the second holds no major.
- **Failures.** A text that raises `FormatError` (its subclasses included) MUST be named in `unread` with the error's message, and the design MUST keep what that file would have given.
- **Issues.** The readers' issues (`kicad.project.*`, `kicad.version.*`, `rules.kept-opaque`) MUST be appended to `issues`.
- **Evidence.** `evidence` MUST be `Evidence.combine` of `pro.EVIDENCE` when a project text was read and `dru.EVIDENCE` when a rules text was read, and `Evidence()` when neither was.
- `KicadBackend.design_rules(design, project, *, issues=None)` MUST pass the texts of `<stem>.kicad_pro` and `<stem>.kicad_dru` from `project.files`, `<stem>` being the stem of `project.board`, or `None` for a file the copy set does not hold, and as `major` the major of the project file (`ProjectInfo.major`) when it has one, else `versions.DEFAULT_TARGET`. It MUST read no other file.

#### Scenario: Net-class bench applied
- **GIVEN** the bench of `tests/_netclass_bench.py` written by `write_triad` for target 10, and its board read back with `read_board`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copperrules.py -k bench` calls `design_rules_from_texts` with the written project and rules texts
- **THEN** the design's classes are `Default` and `HV`, the nets `+3V3` and `SIG1` have the HV id, and `min_clearance` equals `info.floors.get("clearance")` of the written project

#### Scenario: Opaque clearance rule counted
- **GIVEN** a rules text holding `(version 1)`, one clearance rule whose condition is `A.Type == 'Text'` and one `track_width` rule with the same condition
- **WHEN** `design_rules_from_texts` is called with it
- **THEN** `opaque_clearance_rules` is 1, the design's `rules` holds no lifted rule, and `issues` holds two `rules.kept-opaque` infos

#### Scenario: No project files
- **WHEN** `design_rules_from_texts(design, project_text=None, rules_text=None)` is called
- **THEN** it returns `design` unchanged, `min_clearance is None`, `unread == ()` and evidence level `UNVERIFIED`

#### Scenario: Measured tables applied
- **GIVEN** `lowering.RULES_OVER_CLASSES` patched to `frozenset({10})` and `lowering.FLOOR_OVER_RULES["min_clearance"]` to `frozenset({9})`
- **WHEN** `design_rules_from_texts(design, project_text=None, rules_text=None, major=9)` and the same call with `major=10` run
- **THEN** the first gives `rules_over_classes` false and `floor_over_rules` true, and the second the reverse

### Requirement: Footprints are re-placed on a read board
`fenolite.backends.kicad.replace.move_footprint(design, footprint_id, *, at=None, rotation=None, side=None, definitions=None, force=False) -> Design` SHALL return `design` with that footprint at the new placement and nothing else changed.
- **Translation.** When the rotation and the side stay, only `FootprintInstance.position` MUST change; every slot of the footprint MUST stay.
- **Rotation or side change.** The footprint MUST be replaced by `embed.place_footprint` of `definitions[<lib_ref>]` at the new placement, with its component, its lock, the board's copper layers, and `key` equal to its `fenolite.path` property when it has one and to its reference otherwise. Each field of the old footprint that the definition lacks MUST first be added to the definition with `embed.with_property`, in the old order. The new footprint MUST keep the old one's id, uuid, user properties, Reference and Value, and each pad MUST take the net of the old pad with the same number. When the side stays, each field that both footprints hold MUST take the old field's placement and appearance (`position`, `rotation`, `layer`, `size`, `thickness`, `visible`, `h_justify`, `v_justify`, `mirrored`); when the side changes, the fields MUST be the definition's.
- Without a definition for the footprint's `lib_ref`, a rotation or side change MUST raise `PlacementError` carrying `place.no-definition` naming the reference.
- A locked footprint MUST raise `PlacementError` carrying `place.locked` unless `force` is true.
- An unknown `footprint_id` MUST raise `PlacementError` carrying `place.unknown-ref`.
- The board order of footprints MUST be kept, and the written board MUST pass `roundtrip.rt1`.

#### Scenario: Translation keeps every slot
- **GIVEN** `tests/data/kicad/board/two_layer.kicad_pcb` read with `read_board`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_replace.py -k translate` moves `R1` by 2 mm and writes the board
- **THEN** the footprint node differs from the original only in its `at` position, and every other root child is tree-equal

#### Scenario: Rotation from the definition
- **GIVEN** the built blink and the definitions of its footprints
- **WHEN** `move_footprint` rotates `U1` to 90° and flips `R1` to the bottom
- **THEN** each new footprint equals `place_footprint` of its definition at that placement, with the old uuid, Reference, Value and pad nets

#### Scenario: No definition
- **GIVEN** a board whose `R1` has a `lib_ref` that `definitions` lacks
- **WHEN** `move_footprint` is asked to rotate it
- **THEN** `PlacementError` is raised with `place.no-definition` naming `R1`, and a translation of the same footprint succeeds

#### Scenario: Locked footprint
- **GIVEN** a locked footprint
- **WHEN** `move_footprint` runs without `force`
- **THEN** `PlacementError` is raised with `place.locked`

### Requirement: Board outline as rings
`fenolite.backends.kicad.outline.board_outline(design) -> BoardOutline` SHALL give the board outline as closed rings in the board frame, without a snapping tolerance (`H-G-EDGE-EXACT`):
- from `Board.outline.points`, followed by each ring of `Board.outline.cutouts`, when the model has an outline (`source == "model"`);
- otherwise from the root graphics on the layer of kind `edge`, chained by `geometry.assemble_rings` (`source == "edge"`); circles are rings by themselves;
- `rings[0]` MUST be the ring of largest area, and the others its cut-outs;
- when no ring closes, `rings` MUST be empty and `problem` MUST be one of `open-contour`, `branching-contour`, `no-edge-content` and `footprint-edges-only`;
- `exact` MUST be false when an arc was approximated.

`H-G-PLACE-OUTLINE` MUST be measured over the readable non-heavy demo boards and its counts recorded.

#### Scenario: Model outline
- **GIVEN** a built blink model
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_outline.py -k model` calls `board_outline`
- **THEN** `source` is `model` and the ring holds the outline's points

#### Scenario: Edge graphics with a cut-out
- **GIVEN** an authored board with four `gr_line` items forming a rectangle and a `gr_circle` inside it, all on `Edge.Cuts`
- **WHEN** `board_outline` runs
- **THEN** `source` is `edge`, `rings[0]` is the rectangle and `rings[1]` the circle's ring

#### Scenario: Open contour named
- **GIVEN** the same board with one line removed
- **WHEN** `board_outline` runs
- **THEN** `rings` is empty and `problem` is `open-contour`

#### Scenario: Demo outlines counted
- **WHEN** `uv run pytest tests/corpus/test_outline_corpus.py` runs over the cached readable non-heavy demo boards
- **THEN** no call raises, and the counts of `model`, `edge` and each `problem` are recorded for `H-G-PLACE-OUTLINE`

