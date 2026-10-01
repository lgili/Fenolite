# KiCad boards (`.kicad_pcb`)

`fenolite.backends.kicad.pcb` reads a KiCad board into a `fenolite.model.Design` and rebuilds the same
board from it (same-version round trip, RT1). Nothing here writes a board at another version; that is
the board writer change. Sources are listed in `docs/evidence/sources.md`; every fact carries a source
id and an evidence label, and the hypotheses are in `docs/hypotheses.md`.

No KiCad C++ source was read for this page. The version-history file S-0030 and the keyword file
S-0033 were consulted for names and dated facts only.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| A board file is one list `(kicad_pcb (version V) (generator G) …)`; the header comes first and the order of the other sections is not critical | S-0021 | INFERRED | H-K-PCB-READ |
| Board children: `general`, `paper`, `title_block`, `layers`, `setup` (stack-up and plot settings), the net table up to 9.0, then `footprint`, `gr_*`, `gr_text`, `segment`, `arc`, `via`, `zone`, `group`, `dimension` and newer heads | S-0021, S-0001, S-0039 | INFERRED | H-K-PCB-READ |
| Board format versions: 8.0 `20240108`, 9.0 `20241229`, 10.0 `20260206`; the development header `20241030` is read by 9.0 | S-0030 | INFERRED | H-K-TOK-CONSTANTS |
| Unknown tokens are rejected at the top level and in `setup`, `segment`, `footprint` and `pad` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-STRICT |
| Lengths are millimetres with at most 6 decimals (1 nm); 0 exceptions in the modelled length fields of the corpus boards | S-0001, S-0024 | CORPUS-VERIFIED | H-K-UNIT |
| Files written by `kicad-cli` 10.0.6 hold numbers with more than 6 decimals only where the value is not a length | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-SEXPR-NUM-WRITE-2 |
| `layers` rows are `(ORDINAL "CANONICAL_NAME" TYPE ["USER_NAME"])`; `TYPE` is `jumper`, `mixed`, `power`, `signal` or `user` | S-0021 | INFERRED | H-K-PCB-READ |
| Copper layers can be designated signal, power plane, mixed or jumper; user names are for display and output only | S-0038, S-0001 | INFERRED | H-K-PCB-READ |
| 9.0 renumbered the layer ordinals: `B.Cu` from 31 to 2, `Edge.Cuts` from 44 to 25 | S-0030 | INFERRED | H-K-PCB-READ |
| In the demo boards the copper rows of `layers` come first, in stack order | S-0024 | INFERRED | H-K-PCB-READ |
| A layer list may use the wildcard `*.Cu` for all copper layers (and `*.X` for a technical pair) | S-0001 | INFERRED | H-K-PCB-READ |
| Pad and zone layer lists in the demo boards also use `F&B.Cu` (front and back copper only) | S-0024 | INFERRED | H-K-PCB-READ |
| Up to 9.0 nets are a table of `(net N "NAME")` rows, row 0 being `(net 0 "")`; segments, arcs, vias and zones refer to a net by `(net N)` and pads by `(net N "NAME")` | S-0021, S-0001 | INFERRED | H-K-PCB-READ |
| From board version `20251028`, items refer to nets by name, `(net "NAME")`, and the table is no longer written | S-0030 | INFERRED | H-K-PCB-READ |
| 9.0.9 rejects nets referenced by name; 10.0.6 loads them | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-NETNAME |
| 10.0.6 still reads the numbered net table it no longer writes | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-TOK-OBSOLETE |
| `segment`: `start`, `end`, `width`, `layer`, optional `locked`, `net`, `uuid` (`tstamp` in old files); `arc` adds `mid` | S-0021 | INFERRED | H-K-PCB-READ |
| `via`: optional type atom (`blind`, `micro`; a through via has none), optional `locked`, `at`, `size` (diameter), `drill`, `layers` (the two end layers), optional `remove_unused_layers`, `keep_end_layers`, `free`, `net`, `uuid` | S-0021 | INFERRED | H-K-PCB-READ |
| A board footprint has a library link name, optional `locked`, `layer` (`F.Cu` or `B.Cu`), `uuid`, `at X Y [ANGLE]`, `property` rows, `path` (the linked schematic symbol), `attr`, graphics, pads, zones and a 3D model | S-0001 | INFERRED | H-K-PCB-READ |
| KiCad 9.0 and 10.0 write the footprint lock as `(locked yes)`; property names may be unquoted (`ki_fp_filters`) | S-0024 | INFERRED | H-K-PCB-READ |
| `attr` holds the type `smd` or `through_hole` and the flags `board_only`, `exclude_from_pos_files`, `exclude_from_bom` | S-0001 | INFERRED | H-K-PCB-READ |
| The demo boards also use the flags `dnp`, `allow_missing_courtyard` and `allow_soldermask_bridges`; the manual names the attributes not in schematic, exclude from position files, exclude from bill of materials and do not populate | S-0024, S-0038 | INFERRED | H-K-PCB-READ |
| A board pad carries `(net N "NAME")`, and optionally `(pinfunction "NAME")` (the symbol pin name) and `(pintype "TYPE")` (the pin electrical type) | S-0001 | INFERRED | H-K-PCB-READ |
| The demo boards use 11 of the 12 pin electrical types and forms `<type>+no_connect` in `pintype` | S-0024 | INFERRED | H-K-PCB-READ |
| A footprint angle θ maps local `(x, y)` to `(x·cosθ + y·sinθ, −x·sinθ + y·cosθ)` in the Y-down file frame | S-0010, S-0019 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-ROT-DIR |
| For a bottom footprint, absolute = `at + R(θ)·stored`, with no further mirror | S-0019 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-BOTTOM-PLACE |
| The stored children of a bottom footprint are the library footprint mirrored about local X | S-0019 | INFERRED | H-G-BOTTOM-STORE |
| Pad angles in board files are absolute: the footprint angle is included | S-0019 | INFERRED | H-G-PAD-ANGLE-ABS |
| In the demo boards pad angles lie in [0°, 360°), footprint angles may be negative, and a zero pad or footprint angle is not written | S-0024 | INFERRED | H-K-PCB-READ |
| `gr_text` is `(gr_text "TEXT" (at X Y [ANGLE]) (layer L [knockout]) (uuid U) (effects …))`; the demo boards write the text angle even when it is 0 (456 of 585 texts) | S-0001, S-0024 | INFERRED | H-K-PCB-READ |
| `zone`: `net`, `net_name`, `layer` (or `layers`), `uuid`, optional `name`, `hatch`, optional `priority` (absent when 0), `connect_pads`, `min_thickness`, optional keepout settings, fill settings, `polygon` (the outline), then one `filled_polygon` per filled area | S-0001 | INFERRED | H-K-PCB-READ |
| A zone with a `keepout` child is a rule area; its settings `tracks`, `vias`, `pads`, `copperpour`, `footprints` take `allowed` or `not_allowed` | S-0001 | INFERRED | H-K-PCB-READ |
| Rule areas gained a `placement` child in 9.0 (`20241009`) | S-0030, S-0050 | INFERRED | H-K-PCB-READ |
| Teardrops are zones carrying `(attr (teardrop (type …)))` and a name such as `$teardrop_padvia$` | S-0024 | INFERRED | H-K-PCB-READ |
| A `pts` list may hold `(arc (start)(mid)(end))` in zone polygons | S-0018 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-PTS-ARC |
| A fill island is marked by the bare `(island)` up to 9.0 and by `(island yes)` or `(island no)` from `20250801` | S-0030 | INFERRED | H-K-PCB-READ |
| A `uuid` is a version 4 UUID meant to be globally unique | S-0001 | INFERRED | H-K-PCB-UUID |
| `pcb upgrade --force` re-saves its input in place, in the current format; it exists in 10.0 only | S-0022, S-0037 | KICAD-VERIFIED (10.0.x) | H-K-FMT-RESAVE |
| A 10.0.6 re-save keeps the uuid of every item it keeps; it removes teardrop zones and a footprint's `Footprint` property, and replaces `fp_text` items by properties with new uuids | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-UUID-KEEP-2 |
| `pcb export pos --format csv --units mm` prints `Ref,Val,Package,PosX,PosY,Rot,Side` with 6 decimals of mm; without `--use-drill-file-origin`, `PosX` is the stored x and `PosY` minus the stored y; bottom X is not negated without `--bottom-negate-x` | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-POS |
| `pcb export pos` prints `Rot` as the stored footprint angle modulo 360° on both sides, 270° as `-90.000000` (the 21 corpus demos on 10.0.6; a bottom footprint at 30° on 9.0.9 and 10.0.6) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-POS |
| `pcb export ipcd356` writes `317` (through-hole) and `327` (surface) pad records in units of 0.0001 in, Y up, with an `R` field; non-plated holes are `367` records | S-0019, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-POS |
| IPC-D-356 records have fixed columns: net name 14 characters (the tail of a longer name), reference 6 and pin 4 (longer values truncated); vias are `317` records with reference `VIA`, a blank pin and the midpoint flag `M`; the access code is `A00` for a through pad, `A01` for a top pad and `A02` for a bottom pad | S-0020 | INFERRED | H-K-PCB-POS |
| The IPC-D-356 `R` field of a pad equals (−stored absolute pad angle) mod 360° | S-0020 | INFERRED | H-G-PAD-ANGLE-ABS |
| Text effects hold `(font (size HEIGHT WIDTH) (thickness T))` | S-0001 | INFERRED | H-K-PCB-READ |

## What the reader models

Each child is *modelled* (represented completely and re-emitted from the model), *projected* (its
representable value copied into a field while the child stays an opaque slot) or *opaque* (kept
verbatim). Opaque and projected children keep their position, so a rebuild writes them back in place.

| head | modelled | projected | opaque (examples) |
|---|---|---|---|
| `kicad_pcb` | `version`, `generator`, `generator_version` (values in `Board.ext["kicad"]`), `layers`, net rows N ≥ 1, `footprint`, `segment`, `arc`, `via`, `zone` (not teardrop), `gr_line`, `gr_arc`, `gr_circle`, `gr_rect`, `gr_poly`, `gr_text` | — | `general`, `paper`, `title_block`, `setup`, `(net 0 "")`, teardrop zones, `group`, `dimension`, `generated`, `image`, `table`, `barcode`, `point`, `target`, `embedded_fonts`, `embedded_files`, unknown heads |
| `footprint` | name → `lib_ref`, `layer` → `side`, `at` → `position` and `rotation`, `uuid`, `attr` → `attributes`, `pad`, `path` → `Component.path` | `property` → `Component.ref`, `value`, `properties`; `locked` → `locked` | `descr`, `tags`, `sheetname`, `sheetfile`, `fp_*`, `model`, `zone`, `group`, `units`, clearances, `embedded_*` |
| `pad` | number, type, shape, `at`, `size`, `layers` without wildcards, `drill` with one diameter, `uuid`, `net` | `layers` with wildcards, `padstack`, offset drill, `pinfunction`, `pintype` | `roundrect_rratio`, `chamfer*`, margins, `tenting`, `teardrops`, `primitives`, `options`, `zone_connect`, `remove_unused_layers` |
| `segment`, `arc` | `start`, `mid`, `end`, `width`, `layer`, `net`, `uuid` | — | `locked`, unknown heads |
| `via` | type atom, `at`, `size`, `drill`, `layers`, `net`, `uuid` | — | `locked`, `free`, `remove_unused_layers`, `tenting`, `padstack`, `teardrops` |
| `zone` | `net`, `layer` or `layers`, `uuid`, `name`, `priority`, one points-only `polygon`, `filled_polygon`, `keepout` | `layers` with wildcards | `net_name`, `hatch`, `connect_pads`, `min_thickness`, `filled_areas_thickness`, `fill`, `placement`, `attr`, `locked` |
| `filled_polygon` | `layer`, `island`, points-only `pts` | — | unknown heads |
| `gr_*` | as `fp_*` in footprint libraries (`libraries.md`) | `stroke` (width) | hatch fills, `net`, `locked` |
| `gr_text` | text atom, `at`, `layer` with one atom, `uuid` | `effects` (font size and thickness) | `render_cache`, `locked` |

A modelled child that the emitter does not reproduce exactly (a spelling such as `12.000000`, a
written zero pad or footprint angle, an extra atom such as `knockout`) becomes a projected slot with
the info `kicad.board.kept-opaque`. This is a Fenolite rule that keeps the rebuild exact. The
emitters omit a zero footprint or pad angle and always write the text angle, as the demo boards do.

## Fenolite choices

These are decisions of the reader, not facts about KiCad.

- **Version policy.** Boards of 8.0, 9.0 and 10.0 (development headers included) are read. Older
  boards raise `UnsupportedFormatError` with the `kicad-cli pcb upgrade` hint. Newer boards are read
  with the warning `kicad.version.future`; every opaque fragment then carries the file's own version as
  its minimum version, so the board cannot be edited or written for a known target.
- **Layer kinds.** `F.Cu`, `B.Cu`, `In<n>.Cu` → `copper`; `*.SilkS` → `silkscreen`; `*.Mask` →
  `soldermask`; `*.Paste` → `solderpaste`; `*.CrtYd` → `courtyard`; `*.Fab` → `fabrication`;
  `Edge.Cuts` → `edge`; `Margin` and `*.Adhes` → `mechanical`; `Dwgs.User`, `Cmts.User`,
  `Eco1.User`, `Eco2.User`, `User.<n>` → `user`. The `*.Adhes` row is a Fenolite choice. A name
  outside this list (the fallback, also a choice) is `copper` when its row type is `signal`, `power`,
  `mixed` or `jumper`, and `user` otherwise. `Layer.ordinal` is the row index; the row number, type
  and user name stay in `Layer.ext["kicad"]`. Items keep canonical KiCad layer names.
- **Wildcard expansion.** In pad layer lists, `*.Cu` becomes every copper row of the board's
  `layers`, and `*.X` and `F&B.X` become `F.X` and `B.X`. A `layers` child with a wildcard is a
  projected slot, so the file keeps its spelling.
- **Pad frame.** `FootprintInstance.position` and `rotation` are the stored `at` values on both
  sides; a bottom rotation is not converted. `Pad.position` is the stored footprint-local position,
  so absolute = `instance.position + R(instance.rotation)·pad.position` (`H-G-BOTTOM-PLACE`); bottom
  footprints keep their stored, mirrored coordinates. `Pad.rotation` is relative to the footprint:
  `pad_angle_from_board(stored, footprint) = (stored − footprint) mod 360°`, and
  `pad_angle_to_board(relative, footprint) = (relative + footprint) mod 360°` in [0°, 360°). This pair
  depends on `H-G-PAD-ANGLE-ABS`.
- **Edge graphics.** `Board.outline` is `None` on import; Edge.Cuts items are ordinary `Graphic`s
  on layer `Edge.Cuts`.
- **Nets.** The form is decided per reference by its first atom. In the numbered form, table rows
  with N ≥ 1 become `Net`s in table order, N kept as the pair `("number", "<N>")` in `Net.ext["kicad"]`;
  row 0 stays opaque. In the name form, nets are created in the order of first reference. Net 0 and the
  empty name give no net. A number missing from the table gives no net, an opaque reference and the
  warning `kicad.board.unknown-net`.
- **Zones and rule areas.** A `zone` with `keepout` becomes a `Keepout` (`not_allowed` → true);
  any other zone a `Zone`, except teardrop zones, which stay opaque root children. One points-only
  `polygon` is the outline; `pts` arcs or several `polygon` children give an empty outline, keep the
  polygons opaque and add the info `kicad.board.zone-outline-opaque`. Each `filled_polygon` is one
  `ZoneFill(layer, polygon, island)` in file order; `island` is true for `(island)` and `(island yes)`.
- **Circuit synthesis.** One `Component` per footprint (reference and value from the `Reference` and
  `Value` properties, `dnp` from the `dnp` attribute), one `Pin` per distinct non-empty pad number
  (name from `pinfunction`, electrical type from `pintype` through the closed table of the twelve
  `PinType` values; any other text gives `unspecified` and stays in `Pin.ext["kicad"]`), and net
  members from the numbered pads.
- **Numbers.** Lengths and angles are read exactly; nothing is rounded. A value that is not a whole
  number of nm or µdeg leaves opaque the smallest item the model can build without it (the child of an
  optional field, otherwise the pad or the root item) and adds `kicad.board.inexact-length` or
  `kicad.board.inexact-angle`.
- **Ids.** Footprint `<fp uuid>`; component `fp:<fp uuid>`; pin `<fp uuid>:pin:<number>`; pad
  `<fp uuid>:<pad uuid>`; padstack `<fp uuid>:<pad uuid>:padstack`; net `net:<name>`; layer
  `layer:<name>`; tracks, arcs, vias, zones, keepouts, graphics and texts their uuid; design header and
  board `kicad_pcb`. An item without a uuid gets a content id; a repeated uuid gets the occurrence
  suffix `:<k>` and the warning `kicad.board.duplicate-uuid`.

## Issue codes

| code | severity | when |
|---|---|---|
| `kicad.board.inexact-length` | info | a length that is not a whole number of nm |
| `kicad.board.inexact-angle` | info | an angle that is not a whole number of µdeg |
| `kicad.board.zone-outline-opaque` | info | a zone or rule-area outline with `pts` arcs or several `polygon` children |
| `kicad.board.duplicate-uuid` | warning | a uuid already used by another item of the file |
| `kicad.board.unknown-net` | warning | a numbered net reference absent from the table |
| `kicad.board.kept-opaque` | info | a modelled or projected child that loses modelled meaning or fails the emitter check |

Board reads also report the `kicad.version.*` codes of `versions.md`.
