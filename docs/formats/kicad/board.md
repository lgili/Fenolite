# KiCad boards (`.kicad_pcb`)

`fenolite.backends.kicad.pcb` reads a KiCad board into a `fenolite.model.Design` and rebuilds the same
board from it (same-version round trip, RT1); `write_board` writes a design for KiCad 9.0 or 10.0
(section "The writer"). Sources are listed in `docs/evidence/sources.md`; every fact carries a source
id and an evidence label, and the hypotheses are in `docs/hypotheses.md`.

No KiCad C++ source was read for this page. The version-history file S-0030 and the keyword file
S-0033 were consulted for names and dated facts only. The child orders of the writer were observed in
KiCad-written demo boards (S-0058) and in `kicad-cli` 10.0.6 `pcb upgrade --force` copies of them (S-0020),
never taken from KiCad's writer code.

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
| A footprint can carry user properties, each of which can be hidden; KiCad-written boards and the `Mini_v9` footprints write a hidden one as `(property "NAME" "VALUE" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid …) (effects (font (size 1 1) (thickness 0.15))))` after the other properties. A board whose footprints carry a hidden `fenolite.path` property in that form loads on 9.0.9 and 10.0.6, and after `pcb upgrade --force` on 10.0.6 every footprint keeps the value and `(hide yes)` | S-0010, S-0038, S-0058, S-0020 | KICAD-VERIFIED (9.0.x load, 10.0.x re-save) | H-K-BUILD-PATHPROP |
| `attr` holds the type `smd` or `through_hole` and the flags `board_only`, `exclude_from_pos_files`, `exclude_from_bom` | S-0001 | INFERRED | H-K-PCB-READ |
| The demo boards also use the flags `dnp`, `allow_missing_courtyard` and `allow_soldermask_bridges`; the manual names the attributes not in schematic, exclude from position files, exclude from bill of materials and do not populate | S-0024, S-0038 | INFERRED | H-K-PCB-READ |
| A board pad carries `(net N "NAME")`, and optionally `(pinfunction "NAME")` (the symbol pin name) and `(pintype "TYPE")` (the pin electrical type) | S-0001 | INFERRED | H-K-PCB-READ |
| The demo boards use 11 of the 12 pin electrical types and forms `<type>+no_connect` in `pintype` | S-0024 | INFERRED | H-K-PCB-READ |
| A footprint angle θ maps local `(x, y)` to `(x·cosθ + y·sinθ, −x·sinθ + y·cosθ)` in the Y-down file frame | S-0010, S-0019 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-ROT-DIR |
| For a bottom footprint, absolute = `at + R(θ)·stored`, with no further mirror | S-0019 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-BOTTOM-PLACE |
| The stored children of a bottom footprint are the library footprint mirrored about local X (DRC library parity: no mismatch for 12 bottom placements, one for an unmirrored control) | S-0019, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-BOTTOM-STORE |
| Pad angles in board files are absolute: the footprint angle is included (DRC library parity: one mismatch for a control whose stored pad angles leave it out) | S-0019, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-PAD-ANGLE-ABS |
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
| A library footprint placed on the bottom at angle θ is stored at θ with child angles (−φ + θ) mod 360° (φ the library angle): DRC library parity reports no mismatch for 24 placements at 0°, 30°, 90° and 180° on both sides, and one for a control written at −θ | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-FLIP |
| With a project `fp-lib-table` and an empty `KICAD_CONFIG_HOME`, `pcb drc` reports `lib_footprint_mismatch` for a placement that differs from its library footprint, none for an exact one, and `lib_footprint_issues` when the table is absent | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-LIB-DRC |
| Boards whose header has `generator_version` absent, `"9.0"`, `"10.0"` or `"fenolite-x"` load: the target-9 triad on 9.0.9 and 10.0.6, the target-10 triad on 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-GENVER |
| Boards written by `write_board` load: the triad and the created test board (4 copper layers, every created head) for target 9 on 9.0.9 and 10.0.6 and for target 10 on 10.0.6; 9.0.9 rejects the target-10 texts with exit 3 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-WRITE |
| Texts on back layers carry `mirror` in their `justify`: all 236 board texts on `B.*` layers and 8 335 of the 8 338 footprint properties on `B.*` layers of the 10.0.6-written boards (the 10.0.6 demo `pic_programmer` and 10.0.6 re-saves of the 21 other demos) | S-0020, S-0058 | INFERRED | H-G-BOTTOM-STORE |
| KiCad 9.0 and 10.0 releases write `(generator_version "9.0")` and `"10.0"`; nightly builds write `"8.99"` and `"9.99"` | S-0039, S-0058 | INFERRED | H-K-GENVER |
| In `20241229` boards, unconnected zones and rule areas carry `(net 0)` and `(net_name "")` (9 in the demos `multichannel_mixer`, `One-Air-Max` and `RoyalBlue54L-Feather`); pads, tracks and vias without a net carry no `net` child, and the only `(net 0 "")` is the table's row 0 | S-0058 | INFERRED | H-K-PCB-WRITE |
| A 10.0.6 re-save of a `20241229` board writes no net table, no `net` child on unconnected zones and rule areas, and no `net_name`, `filled_areas_thickness`, `hpglpennumber`, `hpglpenspeed`, `hpglpendiameter` or `plotinvisibletext` | S-0020, S-0058 | INFERRED | H-K-TOK-OBSOLETE |
| S-0030 names no format version for the 9.0 layer renumbering; the development board `multichannel_mixer-unrouted` (header `20241030`, tag 10.0.6) already numbers `B.Cu` 2 and `Edge.Cuts` 25, so the renumbering lies after `20240108` and no later than `20241030` | S-0030, S-0058 | INFERRED | H-K-PCB-WRITE |
| Layer tables written by 10.0.6 for two copper layers: `(0 "F.Cu" signal)`, `(2 "B.Cu" signal)`, `(9 "F.Adhes" user "F.Adhesive")`, `(11 "B.Adhes" user "B.Adhesive")`, `(13 "F.Paste" user)`, `(15 "B.Paste" user)`, `(5 "F.SilkS" user "F.Silkscreen")`, `(7 "B.SilkS" user "B.Silkscreen")`, `(1 "F.Mask" user)`, `(3 "B.Mask" user)`, `(17 "Dwgs.User" user "User.Drawings")`, `(19 "Cmts.User" user "User.Comments")`, `(21 "Eco1.User" user "User.Eco1")`, `(23 "Eco2.User" user "User.Eco2")`, `(25 "Edge.Cuts" user)`, `(27 "Margin" user)`, `(31 "F.CrtYd" user "F.Courtyard")`, `(29 "B.CrtYd" user "B.Courtyard")`, `(35 "F.Fab" user)`, `(33 "B.Fab" user)` (6 boards, user copper names aside); four copper layers add `(4 "In1.Cu" signal)` and `(6 "In2.Cu" signal)` after `F.Cu` (3 boards) | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| Root children as 10.0.6 writes them: `version`, `generator`, `generator_version`, `general`, `paper`, `title_block`, `layers`, `setup`, footprints, drawings (`gr_*` interleaved by KiCad's own sort, then `gr_text`, then `dimension`), tracks (`segment`, `arc` and `via` interleaved), zones, `group`, `generated`, `embedded_fonts`, `embedded_files`; 9.0-written boards put the net table after `setup` | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| `paper` holds a size name (`A0` … `A5`, `A` … `E`) with an optional `portrait` atom, or `"User"` with a width and a height in mm; without `portrait` the page is landscape | S-0001, S-0058, S-0020 | INFERRED | H-K-PCB-PAPER-2 |
| KiCad's named pages come out within 0.05 mm of the ISO sizes (an A4 board's SVG page is 297.0022 × 210.0072 mm, A3 419.9890 × 297.0022 mm) | S-0077, S-0020 | INFERRED | H-K-PCB-PAPER-2 |
| A `User` page is each dimension truncated to a whole mil (0.0254 mm): Letter 279.4 × 215.9, Legal 355.6 × 215.9 and Tabloid 431.8 × 279.4 mm are exact, 300 × 200 mm comes out 299.9994 × 199.9996 mm and 300.5 × 200.25 mm comes out 300.4820 × 200.2282 mm | S-0020 | INFERRED | H-K-PCB-PAPER-2 |
| `(paper "Tabloid")` makes the board load fail ("Page type 'Tabloid' is not valid"); KiCad-written demo boards spell a custom page `"User"` | S-0020, S-0058 | INFERRED | H-K-PCB-PAPER-2 |
| `title_block` holds `title`, `date`, `rev`, `company` and `comment N "…"` (N = 1 … 9), each with one string, in that order; KiCad writes it right after `paper` | S-0001, S-0058 | INFERRED | H-K-PCB-WRITE |
| Children of board items as 9.0 and 10.0 write them (no conflicting order in 22 boards per major): `footprint` name, `locked`, `layer`, `uuid`, `at`, `descr`, `tags`, `property`, `path`, `sheetname`, `sheetfile`, …, `attr`, graphics, `pad`, `zone`, `group`, `embedded_*`, `model`; `property` name, value, `at`, `unlocked`, `layer`, `hide`, `uuid`, `effects`; `effects` `font`, `justify`; `font` `face`, `size`, `thickness`, `bold`; `pad` number, type, shape, `at`, `size`, `rect_delta`, `drill`, `property`, `layers`, …, `net`, `pinfunction`, `pintype`, …, `uuid` | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| Children of tracks and zones as 9.0 and 10.0 write them: `segment` `start`, `end`, `width`, `locked`, `layer`, `net`, `uuid`; `arc` `start`, `mid`, `end`, `width`, `layer`, `net`, `uuid`; `via` type atom, `at`, `size`, `drill`, `layers`, …, `locked`, …, `net`, `uuid`; `zone` `net`, `net_name` (9.0), `layer`, `locked`, `layers`, `uuid`, `name`, `hatch`, `priority`, `attr`, `connect_pads`, `min_thickness`, `filled_areas_thickness` (9.0), `keepout`, `placement`, `fill`, `polygon`, `filled_polygon`; `polygon` `pts`; `filled_polygon` `layer`, `pts`; `keepout` `tracks`, `vias`, `pads`, `copperpour`, `footprints` | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| Children of drawings as 9.0 and 10.0 write them: `gr_line` `start`, `end`, `stroke`, `locked`, `layer`, `uuid`; `gr_arc` `start`, `mid`, `end`, `stroke`, `locked`, `layer`, `uuid`; `gr_circle` `center`, `end`, `stroke`, `fill`, `layer`, `uuid`; `gr_rect` `start`, `end`, `stroke`, `fill`, `layer`, `net`, `uuid`; `gr_poly` `pts`, `stroke`, `fill`, `layer`, `net`, `uuid`; `gr_text` text, `at`, `layer`, `uuid`, `effects`, `render_cache`; `stroke` `width`, `type`; `pts` `xy` (and `arc`); fills are spelled `(fill yes)` and `(fill no)` | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| A `property` of a board footprint writes its angle, also when it is 0: `(at X Y ANGLE)` in all 16 054 properties of the 10.0.6-written boards | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| The names `arc`, `attr`, `center`, `copperpour`, `filled_polygon`, `footprints`, `gr_arc`, `gr_circle`, `gr_line`, `gr_poly`, `gr_text`, `island`, `justify`, `keepout`, `locked`, `mid`, `name`, `pads`, `path`, `priority`, `tracks` and `vias` exist in the 8.0 board format | S-0021, S-0033 (tag 8.0.0) | INFERRED | H-K-PCB-WRITE |
| DRC reports a board footprint whose library is in no active library table, or whose library lacks it ("Footprint not found in libraries"), and a board footprint that differs from its library copy ("Footprint doesn't match copy in library"), both as warnings; demo projects list their severity keys `lib_footprint_issues` and `lib_footprint_mismatch` at tags 9.0.9.1 and 10.0.6 | S-0038, S-0058 | INFERRED | H-K-LIB-DRC |

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

## Paper and title block (c0012)

`paper` and `title_block` stay opaque root slots, so the closed list of modelled content, every opaque
count and RT1 are unchanged; their content is projected into `Board.sheet` and `Board.title_block`.

- **Read.** `pcb.project_paper` gives `A0` … `A5` (with `portrait`), and maps `(paper "User" W H)` to
  `Letter`, `Legal` or `Tabloid` when W × H is that size in either orientation (portrait when W < H),
  else to `custom` W × H. Any other name (`USLetter`, `A` … `E`) and a size that is not whole nm give
  `Board.sheet = None` and the info `kicad.board.paper-unmodelled`. `pcb.project_title_block` maps
  `title`, `date`, `rev`, `company` and `comment 1` … `comment 3` through `pcb.TITLE_BLOCK_FIELDS`;
  `comment 4` … `comment 9` and unknown children stay in the fragment.
- **Write.** An unchanged projection keeps its fragment. A changed `paper` is re-emitted whole with
  `pcb.paper_node`: a named A size, or `"User" W H` for the US sizes and custom pages, never KiCad's own
  US names. A changed `title_block` is rewritten in place: changed values replaced, newly set fields
  inserted in the order `title`, `date`, `rev`, `company`, `comment 1` … `comment 3`, emptied fields
  removed, every other child kept; a board read without one gains it right after `paper`.

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

## The writer

`write_board(design, *, target, allow_lossy)` returns the text of a board for KiCad 9.0 or 10.0.
Everything below is a Fenolite choice built on the facts above; `pcb.WRITE_EVIDENCE` is `INFERRED`
(`H-K-PCB-WRITE`), because only the shape of the test boards is checked by `kicad-cli`.

- **Target policy.** A read design keeps its source header in `Board.ext["kicad"]`. It must be
  editable (`FutureFormatError` otherwise), its major must not be newer than the target
  (`DowngradeRefusedError`), and a source of major 8 is refused for every target
  (`LegacyEditRefusedError`, `FEN-7003`): 9.0 renumbered the layers, and layer numbers also live in
  opaque content such as plot layer masks. The refusal is keyed on major 8; no corpus board has a
  development header between `20240108` and `20241030`. A created design (no source header) is
  written for either target.
- **Header.** `(version V)`, `(generator "fenolite")` and `(generator_version "<target>.0")`, the value a
  release of that major writes, for read and created boards alike (`H-K-GENVER`).
- **Created boards.** The root holds the head set of c0007's skeleton: the header,
  `(general (thickness T) (legacy_teardrops no))` with T the sum of the stack-up thicknesses or 1.6 mm,
  `paper` from `Board.sheet` (`(paper "A4")` when it is `None`), `title_block` right after `paper` when
  one of the seven fields of `Board.title_block` is set (c0012), `layers`,
  `(setup (pad_to_mask_clearance 0))` and, for target 9, the net table.
  `layers.created_layers(2)` is the two-copper table above; `created_layers(4)` adds `In1.Cu` (4) and
  `In2.Cu` (6) after `F.Cu`. No `pcbplotparams` is written.
- **Net forms.** For target 9 the root holds `(net 0 "")` and `(net i "NAME")` for the model's nets in
  code-point order of their names, i = 1 … n. Pads write `(net i "NAME")`; other items write `(net i)`;
  zones also write `(net_name "NAME")`. For target 10 every reference is `(net "NAME")`, with no table
  and no `net_name`. An unconnected zone or rule area writes `(net 0)` and `(net_name "")` for target 9
  and no `net` for target 10; other unconnected items write no `net`. The same rules rewrite every
  `net` node inside opaque content: a number is resolved through the source table and a name by itself;
  `(net 0)`, `(net 0 "")` and `(net "")` become `(net 0)` for target 9 and are removed for target 10.
  A 9 → 9 write renumbers nets, so equality is judged on the model.
- **Rows no longer written.** For target 10, nodes of every inventory row with `until_major = 9` are
  removed after the net conversion (the net table, zone `net_name`, `filled_areas_thickness` and the
  plot rows `hpglpen*` and `plotinvisibletext`), with one `kicad.board.obsolete-dropped` info per row id.
- **Gate.** `check_emittable` runs on the final tree. A too-new token inside an opaque slot raises
  `LossyWriteError` with `droppable = True`; with `allow_lossy` the slot is removed with a
  `kicad.board.dropped-too-new` warning. A too-new token in modelled content is never dropped.
- **Child order.** A read item keeps the order of its slots; a field new to it is inserted after the
  last field that comes before it in `CANONICAL_ORDER`. A created item is written in `CANONICAL_ORDER`,
  positional atoms first:

  | head | children in order |
  |---|---|
  | `kicad_pcb` | `version`, `generator`, `generator_version`, `general`, `paper`, `title_block`, `layers`, `setup`, `net`, `footprint`, `gr_line`, `gr_arc`, `gr_circle`, `gr_rect`, `gr_poly`, `gr_text`, `segment`, `arc`, `via`, `zone` |
  | `footprint` | name, `locked`, `layer`, `uuid`, `at`, `property`, `path`, `attr`, `pad` |
  | `property` | name, value, `at`, `layer`, `uuid`, `effects` |
  | `effects` | `font`, `justify` |
  | `font` | `size`, `thickness` |
  | `pad` | number, type, shape, `at`, `size`, `drill`, `layers`, `net`, `uuid` |
  | `segment` | `start`, `end`, `width`, `layer`, `net`, `uuid` |
  | `arc` | `start`, `mid`, `end`, `width`, `layer`, `net`, `uuid` |
  | `via` | type, `at`, `size`, `drill`, `layers`, `net`, `uuid` |
  | `zone` (also rule areas) | `net`, `net_name`, `layer` or `layers`, `uuid`, `name`, `priority`, `keepout`, `polygon`, `filled_polygon` |
  | `polygon` | `pts` |
  | `filled_polygon` | `layer`, `island`, `pts` |
  | `keepout` | `tracks`, `vias`, `pads`, `copperpour`, `footprints` |
  | `pts` | `xy` |
  | `gr_line` | `start`, `end`, `stroke`, `layer`, `uuid` |
  | `gr_arc` | `start`, `mid`, `end`, `stroke`, `layer`, `uuid` |
  | `gr_circle` | `center`, `end`, `stroke`, `fill`, `layer`, `uuid` |
  | `gr_rect` | `start`, `end`, `stroke`, `fill`, `layer`, `uuid` |
  | `gr_poly` | `pts`, `stroke`, `fill`, `layer`, `uuid` |
  | `stroke` | `width`, `type` |
  | `gr_text` | text, `at`, `layer`, `uuid`, `effects` |

  Each order is a sub-sequence of the observed orders above. The root groups follow the observation;
  inside a group KiCad's own sort is not imitated. No demo board writes `island`; its place between
  `layer` and `pts` is a Fenolite choice that the created test board's load checks.
- **Floor names.** `pcb.FLOOR_HEADS` lists the names the writer creates that neither the token
  inventory (whose scope is names introduced after 8.0) nor c0007's skeleton holds: `arc`, `attr`,
  `center`, `copperpour`, `filled_polygon`, `footprints`, `gr_arc`, `gr_circle`, `gr_line`, `gr_poly`,
  `gr_text`, `island`, `justify`, `keepout`, `locked`, `mid`, `name`, `pads`, `path`, `priority`, `tracks`
  and `vias`. Each exists in the 8.0 format (S-0021, S-0033 at tag 8.0.0), and the created test board
  writes each of them.
- **Created items.** A created footprint writes `(locked yes)` when locked, its `Reference` and
  `Value` properties at local (0, 0) with the footprint angle, on `F.SilkS` and `F.Fab` (`B.*` with
  `(justify mirror)` on the bottom), font 1 × 1 mm and thickness 0.15 mm (the skeleton's values),
  then `path` and `attr` when set. A created drawing writes `(stroke (width W) (type solid))`; circles,
  rectangles and polygons also write `(fill yes|no)`. A created text writes
  `(effects (font (size H W) (thickness T)))`, with `(justify mirror)` on a back layer. A created zone
  writes `name` and `priority` only when they are not empty or 0. A created fill writes `(island)` for
  target 9 when it is an island, and `(island yes|no)` for target 10.
- **uuids.** An item keeps `native_ids["kicad"]`; any other item gets
  `uuid5(FENOLITE_NS, "kicad-out:<id>")`, and a part without its own id (an outline edge, a created
  property) `"kicad-out:<owner id>:<part>"`.
- **Outline.** A non-empty `Board.outline` becomes one `gr_line` per edge of the outer ring and of each
  cutout, closing every ring, on `Edge.Cuts` with `(stroke (width 0.1) (type solid))` (the skeleton's
  stroke), parts `outline:<ring>:<k>`. A board with an outline and a graphic on an `edge` layer gives
  `kicad.board.outline-conflict`.
- **Projections.** Before a read item is written, each opaque child that stands for a model field is
  compared with the model value. Reference and Value rewrite only the value atom of their property.
  A modelled child kept opaque for its spelling (`12.000000`, a written zero angle, an unquoted name) is
  written from the model when its value changed. Any other change of a projected value (other
  properties, `locked`, a `stroke` width, a text's font, a padstack, a `layers` list with wildcards, an
  offset drill) gives `kicad.board.projection-read-only`. A property present in the model and absent
  from the footprint is a change; a property only in the footprint is kept.

### Placed footprints

`embed.place_footprint` writes a library definition as a board footprint. The rules for the bottom
side are `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-G-BOTTOM-STORE`, `H-G-FLIP`, `H-G-PAD-ANGLE-ABS`): the flip
oracle finds no library mismatch for 24 placements and one for each of three negative controls, with
the missing-table control firing on both majors (`H-K-LIB-DRC`). `embed.EVIDENCE` carries that level.

- The header children `version`, `generator` and `generator_version` are dropped; the name becomes
  the definition's `lib_id`; `layer`, `uuid` and `at` are set; the value atoms of Reference and Value
  come from the component; `(locked yes)` is written when locked.
- Every node holding a `uuid` gets `uuid5(FENOLITE_NS, "kicad-place:<key>:<locator>")`, the locator
  being the node's place in the emitted definition (`/footprint`, `/footprint/pad[3]`, …).
- **Bottom side.** `layers.flip_layer` maps `F.<x>` to `B.<x>` and back for `Cu`, `Adhes`, `Paste`,
  `SilkS`, `Mask`, `CrtYd` and `Fab`, in every `layer` and `layers` atom; other names (inner copper,
  wildcards, `Edge.Cuts`, user layers) stay. Every node headed in `embed.MIRROR_HEADS` (`at`, `start`,
  `mid`, `end`, `center`, `xy`, and `offset` under `drill`) has its Y negated, which mirrors it about
  local X; the 3D `model` stays as it is. The angle of every child `at` becomes (−φ) mod 360°. Every
  text (`property`, `fp_text`) whose layer was flipped gains or loses `mirror` in its `justify`.
- **Unsupported geometry.** On the bottom side, `embed.FLIP_UNSUPPORTED` heads (`rect_delta`,
  `chamfer`, `dimension`, `image`, `fp_text_box`, `table`, `barcode`) give one
  `kicad.board.flip-unsupported` issue each, and `place_footprint` raises `LossyWriteError`. The list
  grows when a fixture shows another head whose geometry the mirror table does not cover.
- **Both sides.** Child angles are stored absolute: (angle + θ) mod 360° (`pad_angle_to_board`).
- **Extent.** `embed.footprint_extent(defn)` is, in the definition's frame, the box of the modelled
  `F.CrtYd` graphics (arcs and circles boxed exactly), else the union of the pad boxes (each pad's size
  rotated by its angle about its position, rounded outward), else `BBox(0, 0, 0, 0)`. Courtyard pieces
  kept opaque (an `fp_poly` with an `arc` inside `pts`) are not counted.

### Writer issue codes

| code | severity | when |
|---|---|---|
| `kicad.board.dropped-too-new` | warning | `allow_lossy` removed an opaque slot holding a token the target cannot read |
| `kicad.board.obsolete-dropped` | info | target 10: nodes of an `until_major = 9` row removed or converted (one per row id, with the count) |
| `kicad.board.opaque-net-ref` | error | a `net` node in opaque content matches no form, or names a number absent from the source table |
| `kicad.board.projection-read-only` | error | a projected value other than Reference, Value or a spelling-only field differs from its fragment |
| `kicad.board.outline-conflict` | error | a non-empty outline and edge graphics on one board |
| `kicad.board.flip-unsupported` | error | `place_footprint` on the bottom meets a head of `FLIP_UNSUPPORTED` |

Errors raise `LossyWriteError` (`FEN-7001`); `droppable` is true only when every error is a too-new
token inside opaque content.
