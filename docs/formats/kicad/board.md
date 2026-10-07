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
| The lock of a `segment`, an `arc` and a `via` is `(locked yes)`: after `width` in a segment and an arc, after `layers` in a via; an unlocked item has no `locked` child. KiCad 10.0.6 saves a lock there wherever it was written (`pcb upgrade --force` on a bench with the lock as the first child), with the uuids kept, and judges the board as without the locks. A board written by KiCad 9 holds its segment and via locks at the same places (7 and 5 on one corpus board); where 9.0 writes an arc's lock is not observed, because its `kicad-cli` has no `pcb upgrade` | S-0020, S-0058 | KICAD-VERIFIED (10.0.x) | H-K-LOCK-FORM |
| A footprint can carry user properties, each of which can be hidden; KiCad-written boards and the `Mini_v9` footprints write a hidden one as `(property "NAME" "VALUE" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid …) (effects (font (size 1 1) (thickness 0.15))))` after the other properties. A board whose footprints carry a hidden `fenolite.path` property in that form loads on 9.0.9 and 10.0.6, and after `pcb upgrade --force` on 10.0.6 every footprint keeps the value and `(hide yes)` | S-0010, S-0038, S-0058, S-0020 | KICAD-VERIFIED (9.0.x load, 10.0.x re-save) | H-K-BUILD-PATHPROP |
| Further hidden user properties appended after `fenolite.path`, in code-point order of names, load on 9.0.9 and 10.0.6 without a `lib_footprint_mismatch`; a bottom part's are on `B.Fab` with a mirrored text; a 10.0.6 re-save keeps their names, decoded values (`"`, `\` and `µ` included) and `(hide yes)` | S-0058, S-0038, S-0020 | KICAD-VERIFIED (9.0.x load, 10.0.x load and re-save) | H-K-VENDOR-PROPS |
| A 10.0.6 re-save merges a second property node named `Datasheet` into the field, keeping one node with the later value, and keeps `datasheet` and `reference` (other letter case) as separate properties | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-VENDOR-DUPNAME |
| A footprint moved by token edit keeps its uuid and its `fenolite.path` property through a `pcb upgrade --force` re-save on 10.0.6 | S-0022 | KICAD-VERIFIED (10.0.x) | H-K-LENS-KEEP |
| Fenolite's rewrite of a board edited by token edit (a moved footprint, a route and a via) keeps its DRC report: the same (type, severity) multiset and `unconnected_items` count | S-0022, S-0037, S-0055, S-0056 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-LENS-KEEP |
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
| `pcb drc --format json --severity-all --refill-zones --save-board` on a copy of a target-9 or target-10 board saves the copy in the running 10.0.6 board format (`20260206`, generator `pcbnew`) and writes its zone fills; the original file is not changed | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-FILL-SAVE |
| The same refill of the authored project keeps each zone uuid and gives the GND zone one filled polygon with 16 points | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-FILL-SAVE |
| A second 10.0.6 refill of a board written for its original target with the lifted fills gives the same fill polygons by layer, island flag and point | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-FILL-LIFT |
| 9.0.9 loads the lifted target-9 fills; without `(filled_areas_thickness no)` it reports that the legacy zone fill strategy is unsupported and will be converted on a best-effort basis | S-0020, S-0029 | KICAD-VERIFIED (9.0.x) | H-K-FILL-LOAD9 |
| A zone with a `keepout` child is a rule area; its settings `tracks`, `vias`, `pads`, `copperpour`, `footprints` take `allowed` or `not_allowed` | S-0001 | INFERRED | H-K-PCB-READ |
| Rule areas gained a `placement` child in 9.0 (`20241009`) | S-0030, S-0050 | INFERRED | H-K-PCB-READ |
| Teardrops are zones carrying `(attr (teardrop (type …)))` and a name such as `$teardrop_padvia$` | S-0024 | INFERRED | H-K-PCB-READ |
| A `pts` list may hold `(arc (start)(mid)(end))` in zone polygons | S-0018 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-PTS-ARC |
| A fill island is marked by the bare `(island)` up to 9.0 and by `(island yes)` or `(island no)` from `20250801` | S-0030 | INFERRED | H-K-PCB-READ |
| A `uuid` is a version 4 UUID meant to be globally unique | S-0001 | INFERRED | H-K-PCB-UUID |
| `pcb upgrade --force` re-saves its input in place, in the current format; it exists in 10.0 only | S-0022, S-0037 | KICAD-VERIFIED (10.0.x) | H-K-FMT-RESAVE |
| A 10.0.6 re-save keeps the uuid of every item it keeps; it removes teardrop zones and a footprint's `Footprint` property, and replaces `fp_text` items by properties with new uuids | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-UUID-KEEP-2 |
| A root `group` lists its members by uuid in a `members` child; a board whose footprint uuids and group members were changed together loads on 9.0.9 and 10.0.6 with an unchanged DRC report, and a 10.0.6 re-save keeps the group, its uuid and its members, written sorted by uuid | S-0020, S-0022, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-LENS-RENAME |
| `pcb export pos --format csv --units mm` prints `Ref,Val,Package,PosX,PosY,Rot,Side` with 6 decimals of mm; without `--use-drill-file-origin`, `PosX` is the stored x and `PosY` minus the stored y; bottom X is not negated without `--bottom-negate-x` | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-POS |
| `pcb export pos` prints `Rot` as the stored footprint angle modulo 360° on both sides, 270° as `-90.000000` (the 21 corpus demos on 10.0.6; a bottom footprint at 30° on 9.0.9 and 10.0.6) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-POS |
| `pcb export ipcd356` writes `317` (through-hole) and `327` (surface) pad records in units of 0.0001 in, Y up, with an `R` field; non-plated holes are `367` records | S-0019, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-POS |
| IPC-D-356 records have fixed columns: net name 14 characters (the tail of a longer name), reference 6 and pin 4 (longer values truncated); vias are `317` records with reference `VIA`, a blank pin and the midpoint flag `M`; the access code is `A00` for a through pad, `A01` for a top pad and `A02` for a bottom pad | S-0020 | INFERRED | H-K-PCB-POS |
| The IPC-D-356 `R` field of a pad equals (−stored absolute pad angle) mod 360° | S-0020 | INFERRED | H-G-PAD-ANGLE-ABS |
| `pcb export ipcd356` lists each numbered pad of a board at most once, labelled with its net name or the last 14 characters of it, so the pads it lists fall into the same blocks as on the board | S-0019, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NET-IPC |
| In IPC-D-356, all pads on no net share the label `N/C`, as c0009's comparison over the demos found. Since c0061 the comparison reads that label as "no net", and a pad on no net is a block of its own on every side: two such pads are not connected to each other, and a board that names the net of each unconnected pin (KiCad's `unconnected-(…)` nets) then equals a model that leaves those pins on no net | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NET-IPC |
| When two net names share their last 14 characters, 9.0.9 and 10.0.6 still give them distinct labels: the first keeps the 14-character tail and the next gets a shorter tail followed by `#1` (`/A/LONG_SIGNAL_NAME` gives `NG_SIGNAL_NAME`, `/B/LONG_SIGNAL_NAME` gives `IGNAL_NAME#1`; probe `netlist-label-collision` = `different`). Fenolite does not rely on that numbering: it reports the pads of such nets as `net-label-ambiguous` coverage | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NET-IPC |
| Records are paired with pads by key (reference cut to 6 characters, pad number to 4) and by position relative to an anchor record whose key is unique in the export and in the board, within 2 export units per axis; the matcher is `backends/kicad/padnets.py` | S-0019, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PCB-POS |
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
| KiCad's named pages come out within 0.05 mm of the ISO sizes (an A4 board's SVG page is 297.0022 × 210.0072 mm, A3 419.9890 × 297.0022 mm) | S-0077, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-PAPER-2 |
| A `User` page is each dimension truncated to a whole mil (0.0254 mm): Letter 279.4 × 215.9, Legal 355.6 × 215.9 and Tabloid 431.8 × 279.4 mm are exact, 300 × 200 mm comes out 299.9994 × 199.9996 mm and 300.5 × 200.25 mm comes out 300.4820 × 200.2282 mm | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PCB-PAPER-2 |
| `(paper "Tabloid")` makes the board load fail ("Page type 'Tabloid' is not valid"); KiCad-written demo boards spell a custom page `"User"` | S-0020, S-0058 | INFERRED | H-K-PCB-PAPER-2 |
| `title_block` holds `title`, `date`, `rev`, `company` and `comment N "…"` (N = 1 … 9), each with one string, in that order; KiCad writes it right after `paper` | S-0001, S-0058 | INFERRED | H-K-PCB-WRITE |
| Children of board items as 9.0 and 10.0 write them (no conflicting order in 22 boards per major): `footprint` name, `locked`, `layer`, `uuid`, `at`, `descr`, `tags`, `property`, `path`, `sheetname`, `sheetfile`, …, `attr`, graphics, `pad`, `zone`, `group`, `embedded_*`, `model`; `property` name, value, `at`, `unlocked`, `layer`, `hide`, `uuid`, `effects`; `effects` `font`, `justify`; `font` `face`, `size`, `thickness`, `bold`; `pad` number, type, shape, `at`, `size`, `rect_delta`, `drill`, `property`, `layers`, …, `net`, `pinfunction`, `pintype`, …, `uuid` | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| Children of tracks and zones as 9.0 and 10.0 write them: `segment` `start`, `end`, `width`, `locked`, `layer`, `net`, `uuid`; `arc` `start`, `mid`, `end`, `width`, `layer`, `net`, `uuid`; `via` type atom, `at`, `size`, `drill`, `layers`, …, `locked`, …, `net`, `uuid`; `zone` `net`, `net_name` (9.0), `layer`, `locked`, `layers`, `uuid`, `name`, `hatch`, `priority`, `attr`, `connect_pads`, `min_thickness`, `filled_areas_thickness` (9.0), `keepout`, `placement`, `fill`, `polygon`, `filled_polygon`; `polygon` `pts`; `filled_polygon` `layer`, `pts`; `keepout` `tracks`, `vias`, `pads`, `copperpour`, `footprints` | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| Children of drawings as 9.0 and 10.0 write them: `gr_line` `start`, `end`, `stroke`, `locked`, `layer`, `uuid`; `gr_arc` `start`, `mid`, `end`, `stroke`, `locked`, `layer`, `uuid`; `gr_circle` `center`, `end`, `stroke`, `fill`, `layer`, `uuid`; `gr_rect` `start`, `end`, `stroke`, `fill`, `layer`, `net`, `uuid`; `gr_poly` `pts`, `stroke`, `fill`, `layer`, `net`, `uuid`; `gr_text` text, `at`, `layer`, `uuid`, `effects`, `render_cache`; `stroke` `width`, `type`; `pts` `xy` (and `arc`); fills are spelled `(fill yes)` and `(fill no)` | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| A `property` of a board footprint writes its angle, also when it is 0: `(at X Y ANGLE)` in all 16 054 properties of the 10.0.6-written boards | S-0020, S-0058 | INFERRED | H-K-PCB-WRITE |
| The X and Y of a footprint property's `at` are footprint-local: the anchor of the text on the board is `at + R(θ)·local`, θ being the footprint angle, on both sides, with no further mirror on the bottom (a footprint at (6, 38) and 30° on the bottom with local (−5, 0) has its anchor at (1.669873, 40.5)) | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-FIELD-FRAME |
| The angle of a footprint property's `at` is the angle of the text on the board, not an angle relative to the footprint: on a footprint at 90°, a stored 0 draws the text horizontal and a stored 90 vertical | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-FIELD-FRAME |
| `(justify …)` of a property works in the reading frame of the text: from the anchor a `left` text runs to +X and a `right` one to −X, a `bottom` text lies above the anchor and a `top` one below; `mirror` reverses the horizontal sense, on a front and on a back layer alike; without the words the text is centred on its anchor | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-FIELD-JUSTIFY |
| Keep-upright: without `(unlocked yes)` a property stored at 180° (or 270°) is drawn as at 0° (or 90°), its justification unchanged; with `(unlocked yes)` it is drawn at the stored angle | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-FIELD-JUSTIFY |
| `pcb drc` reports a `Reference` or `Value` property on a silkscreen layer that crosses the board edge as `silk_edge_clearance`, with an item whose uuid is the property's, whose position is the anchor and whose description is `Reference field of <reference>` or `Value field of <reference> (<value>)`; a hidden property is not checked | S-0020, S-0029, S-0055, S-0056 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-FIELD-DRC |
| With the board's `min_silk_clearance` at 0, 9.0.9 reports no `silk_edge_clearance` for a crossing field and 10.0.6 reports one; at 0.1 mm both report it | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-FIELD-DRC |
| A 10.0.6 re-save (`pcb upgrade --force`) keeps visible `fp_text user` items and turns each hidden one into a hidden property named `Field<N>` with a new uuid, written after the other properties: in the 16 non-heavy 10.0.6 demos only the 4 hidden `fp_text user "${REFERENCE}"` items of one board change, and its 67 visible ones stay. This narrows the `fp_text` clause of the re-save row above | S-0020, S-0022, S-0058 | KICAD-VERIFIED (10.0.x) | H-K-FIELD-RESAVE |
| A third-party 7.0 board writes the reference as `(fp_text reference "…" (at X Y A) (layer "F.SilkS") hide (effects …) (tstamp U))`, with a bare `hide`; `pcb upgrade` on 10.0.6 turns it into `(property "Reference" "…" (at X Y A) (layer "F.SilkS") (hide yes) (uuid U) (effects …))` | S-0020, S-0027 | KICAD-VERIFIED (10.0.x) | H-K-FIELD-RESAVE |
| 8.0 boards hold fields as `property` nodes: the format notes date footprint properties to 20200808 and board fields to 20230620, both older than the 8.0 format 20240108. `hide` is described as a bare optional word of `fp_text` and of `effects`; whether 8.0 writes a hidden property with a bare `hide` or with `(hide yes)` is not stated, and no 8.0 board was observed | S-0001, S-0021, S-0030 (tag 8.0.0), S-0120 | INFERRED | H-K-FIELD-V8 |
| Census of the 21 readable corpus boards (1 674 footprints): 15 759 properties, of which 14 953 are placed (`at` with its angle, `layer`, `uuid` and `effects` with a font `size`) and 806 are bare (`ki_fp_filters`); hiding is always `(hide yes)` (12 451); `(unlocked yes)` on 10 458; 114 placed properties have no font `thickness` (`Datasheet`, `Description`); `justify` holds only `mirror` (8 369); 6 fonts hold `bold`; no footprint repeats a property name; 572 properties of one board write the angle `-90` where the others write `270`; all 1 281 `fp_text` items are `user` texts. Read by Fenolite: 14 953 fields, 806 properties kept as footprint slots, and 578 field children kept as written (the 572 `at` with `-90` and the 6 `effects` with `bold`) | S-0058 | CORPUS-VERIFIED | H-K-PCB-READ |
| The names `arc`, `attr`, `center`, `copperpour`, `filled_polygon`, `footprints`, `gr_arc`, `gr_circle`, `gr_line`, `gr_poly`, `gr_text`, `hide`, `island`, `justify`, `keepout`, `locked`, `mid`, `name`, `pads`, `path`, `priority`, `tracks` and `vias` exist in the 8.0 board format | S-0021, S-0033 (tag 8.0.0) | INFERRED | H-K-PCB-WRITE |
| The names `mode`, `smoothing`, `radius`, `island_removal_mode`, `island_area_min`, `hatch_thickness`, `hatch_gap`, `hatch_orientation`, `hatch_smoothing_level`, `hatch_smoothing_value`, `hatch_border_algorithm`, `hatch_min_hole_area` and `zone_connect` exist in the 8.0 board format | S-0033 (tag 8.0.0) | INFERRED | H-K-PCB-WRITE |
| `connect_pads` holds an optional atom and `(clearance C)`: no atom means thermal reliefs, `yes` a solid connection, `no` no connection, and `thru_hole_only` thermal reliefs on through-hole pads and solid connections on the others | S-0001, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-ZONE-CONNECT |
| `(min_thickness T)` is the smallest width of copper a fill keeps: a 0.2 mm channel is filled with 0.15 mm and removed with 0.25 mm | S-0001, S-0010, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-ZONE-GEOM |
| A 10.0.6 re-save writes the `fill` children in this order: the atom `yes`, `mode`, `thermal_gap`, `thermal_bridge_width`, `smoothing`, `radius`, `island_removal_mode`, `island_area_min`, `hatch_thickness`, `hatch_gap`, `hatch_orientation`, `hatch_smoothing_level`, `hatch_smoothing_value`, `hatch_border_algorithm`, `hatch_min_hole_area` | S-0020 | CORPUS-VERIFIED | H-K-ZONE-FORM |
| The atom `yes` of `fill` is a flag of its own: a zone written with fill polygons and no `yes` is re-saved without `yes`, and a zone may hold `(fill yes …)` with no fill polygon (18 zones of the upgraded third-party copies) | S-0020, S-0058 | CORPUS-VERIFIED | H-K-ZONE-FORM |
| `(mode hatch)` marks a hatched fill; a solid fill writes no `mode`. The hatch children are written only for a hatched fill | S-0001, S-0020 | INFERRED | H-K-ZONE-FORM |
| `(smoothing chamfer)` or `(smoothing fillet)` with `(radius R)` smooth the corners of the fill; a zone without smoothing writes neither child | S-0001, S-0020 | INFERRED | H-K-ZONE-FORM |
| `island_removal_mode` 0 removes every island, 1 keeps them, and 2 keeps those of at least `island_area_min` square millimetres; a kept island is written `(island yes)` | S-0001, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-ZONE-GEOM |
| 9.0-written zones (`20241229`) write `island_removal_mode` only when it is not 0, and then also `island_area_min`; 10.0-written zones (`20250513`, `20260206`) always write `island_removal_mode`, and `island_area_min` only for mode 2 | S-0058 | CORPUS-VERIFIED | H-K-ZONE-FORM |
| `hatch_smoothing_level` and `hatch_smoothing_value` are written only for a level above 0; `hatch_border_algorithm` takes `hatch_thickness` or `min_thickness` only | S-0020 | INFERRED | H-K-ZONE-FORM |
| A zone without `connect_pads`, `min_thickness` and `fill` loads in 10.0.6 as clearance 0.5 mm, minimum thickness 0.25 mm, thermal reliefs, thermal gap 0.5 mm, spoke width 0.5 mm and island mode 0 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-ZONE-DEFAULTS |
| A bare `(mode hatch)` loads in 10.0.6 as thickness 1 mm, gap 1.5 mm, orientation 0°, border `hatch_thickness` and minimum hole area 0.15 | S-0020 | INFERRED | H-K-ZONE-DEFAULTS |
| The new-project save of the 10.0.6 GUI stores the zone defaults under `board.design_settings.defaults.zones`: `min_clearance` 0.5, `min_thickness` 0.25, `pad_connection` 1, `thermal_relief_gap` 0.5, `thermal_relief_spoke_width` 0.5, `fill_mode` 0, `remove_islands` 0, `min_island_area` 10, `hatch_thickness` 1.0, `hatch_gap` 1.5, `hatch_orientation` 0, `hatch_smoothing_level` 0, `hatch_smoothing_value` 0.1, `corner_smoothing` 0, `corner_radius` 0, `border_display_style` 2 and `border_hatch_pitch` 0.5 | S-0020 | INFERRED | H-K-ZONE-DEFAULTS |
| `(locked yes)` of a zone sits between `net` (and `net_name`) and `layer` | S-0020, S-0058 | INFERRED | H-K-ZONE-FORM |
| A pad's `(zone_connect N)` overrides the zone's connection for that pad: 0 no connection, 1 thermal relief, 2 solid, 3 thermal relief for through-hole pads only (the format page states 0 to 2). It overrides a footprint-level `zone_connect`, which overrides the zone | S-0001, S-0038, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-ZONE-CONNECT |
| Thermal reliefs give four spokes per pad: on the axes for a rectangular SMD pad, at 45° for a round through-hole pad. The spoke width is `thermal_bridge_width` and the gap of the relief is `thermal_gap` | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-ZONE-CONNECT |
| A fill keeps the larger of the zone's clearance and the clearance that the net class or a custom rule gives, plus about 0.5 µm | S-0010, S-0038, S-0020 | KICAD-VERIFIED (10.0.x) | H-K-ZONE-GEOM |
| `pcb drc` without a refill applies the zone's clearance to its existing fills: a fill 0.3 mm from a pad of another net is reported with a zone clearance of 0.5 mm, and not with 0.1 mm | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-ZONE-GEOM |
| A `20241229` zone without `(filled_areas_thickness no)` has its fill polygons read as outlines drawn with a pen of `min_thickness`: 9.0.9 plots and 10.0.6 re-saves the fill grown by `min_thickness / 2` on each side. With the flag the fill is kept as written. KiCad 9 always writes the flag (53 of 53 zones in 9.0-format demo files) | S-0020, S-0029, S-0058 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ZONE-FAT9 |
| `kicad-cli` 9.0.9 loads every zone setting form listed here; it has no `--refill-zones`, so what a setting does to a fill is not observed on 9.0 | S-0029, S-0037 | KICAD-VERIFIED (9.0.x) | H-K-ZONE-LOAD9 |
| DRC reports a board footprint whose library is in no active library table, or whose library lacks it ("Footprint not found in libraries"), and a board footprint that differs from its library copy ("Footprint doesn't match copy in library"), both as warnings; demo projects list their severity keys `lib_footprint_issues` and `lib_footprint_mismatch` at tags 9.0.9.1 and 10.0.6 | S-0038, S-0058 | INFERRED | H-K-LIB-DRC |
| In KiCad's own boards the inner copper rows are `(2k + 2 "In<k>.Cu" signal)` after `F.Cu` and before `(2 "B.Cu" signal)`, without a user name: `In1.Cu` 4 to `In4.Cu` 10 in a six-layer demo (header `20250513`), and to `In6.Cu` 14 in an eight-layer demo (header `20241229`) | S-0058 | CORPUS-VERIFIED | H-K-PCB-LAYERS |
| A layer table of 2, 4, 6 or 8 copper layers with those inner rows loads on 10.0.6 in the target-9 and the target-10 text (`pcb drc` writes its report), `pcb export gerbers` writes one Gerber per copper layer, named after it, and `pcb upgrade --force` keeps every copper row (number, name, type, no user name, in order) | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-PCB-LAYERS |
| 10.0.6 refuses a table of three copper layers (`F.Cu`, `In1.Cu`, `B.Cu`) in both texts: no DRC report and no Gerber | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PCB-LAYERS |
| 9.0.9 loads the target-9 text of the same tables of 2, 4, 6 and 8 copper layers, gives one Gerber per copper layer and refuses the table of three; its `kicad-cli` has no `pcb upgrade`, so the re-save is judged on 10.0.6 only | S-0029, S-0037 | INFERRED | H-K-PCB-LAYERS |

## What the reader models

Each child is *modelled* (represented completely and re-emitted from the model), *projected* (its
representable value copied into a field while the child stays an opaque slot) or *opaque* (kept
verbatim). Opaque and projected children keep their position, so a rebuild writes them back in place.

| head | modelled | projected | opaque (examples) |
|---|---|---|---|
| `kicad_pcb` | `version`, `generator`, `generator_version` (values in `Board.ext["kicad"]`), `layers`, net rows N ≥ 1, `footprint`, `segment`, `arc`, `via`, `zone` (not teardrop), `gr_line`, `gr_arc`, `gr_circle`, `gr_rect`, `gr_poly`, `gr_text` | — | `general`, `paper`, `title_block`, `setup`, `(net 0 "")`, teardrop zones, `group`, `dimension`, `generated`, `image`, `table`, `barcode`, `point`, `target`, `embedded_fonts`, `embedded_files`, unknown heads |
| `footprint` | name → `lib_ref`, `layer` → `side`, `at` → `position` and `rotation`, `uuid`, `attr` → `attributes`, `pad`, `path` → `Component.path`, placed `property` → `fields` (c0030) | a `property` that is not a field (bare, or a repeated name) → `Component.ref`, `value`, `properties`; `locked` → `locked` | `descr`, `tags`, `sheetname`, `sheetfile`, `fp_*`, `model`, `zone`, `group`, `units`, clearances, `embedded_*` |
| `property` (a field, c0030) | name, `at` → `position` and `rotation`, `layer`, `hide` → `visible`, `uuid`, `effects` with `font` `size` and `thickness` and `justify` → `size`, `thickness`, `h_justify`, `v_justify`, `mirrored` | the value atom → `Component.ref`, `value`, `properties`; an `effects` the emitter does not reproduce (`bold`, a font `face`) | `unlocked`, a bare `hide` atom, unknown heads |
| `pad` | number, type, shape, `at`, `size`, `layers` without wildcards, `drill` with one diameter, `uuid`, `net`, `zone_connect` 0 to 3 → `zone_connection`, `property` with one of the eight fabrication tokens → `fab_property` (c0118) | `layers` with wildcards, `padstack`, offset drill, `pinfunction`, `pintype` | `roundrect_rratio`, `chamfer*`, margins, `tenting`, `teardrops`, `primitives`, `options`, `zone_connect` outside 0 to 3, `thermal_bridge_width`, `thermal_gap`, `thermal_bridge_angle`, `remove_unused_layers` |
| `segment`, `arc` | `start`, `mid`, `end`, `width`, `locked` → `locked` (c0108), `layer`, `net`, `uuid` | — | unknown heads; a `locked` child that is not `(locked yes)` |
| `via` | type atom, `at`, `size`, `drill`, `layers`, `locked` → `locked` (c0108), `net`, `uuid`, and the protection children `tenting`, `capping`, `covering`, `plugging`, `filling` → `protection` ("Via protection") | a protection child in a form that the board's major does not write ("Via protection") | `free`, `remove_unused_layers`, `padstack`, `teardrops`; a `locked` child that is not `(locked yes)` |
| `zone` | `net`, `layer` or `layers`, `uuid`, `name`, `priority`, one points-only `polygon`, `filled_polygon`, `keepout`; on a copper zone also `locked`, `connect_pads`, `min_thickness` and `fill` (section “Zone settings”) | `layers` with wildcards; a setting child that the emitter does not reproduce | `net_name`, `hatch`, `filled_areas_thickness`, `placement`, `attr`; on a rule area also `locked`, `connect_pads`, `min_thickness` and `fill` |
| `filled_polygon` | `layer`, `island`, points-only `pts` | — | unknown heads |
| `gr_*` | as `fp_*` in footprint libraries (`libraries.md`) | `stroke` (width) | hatch fills, `net`, `locked` |
| `gr_text` | text atom, `at`, `layer` with one atom, `uuid` | `effects` (font size and thickness) | `render_cache`, `locked` |

A modelled child that the emitter does not reproduce exactly (a spelling such as `12.000000`, a
written zero pad or footprint angle, an extra atom such as `knockout`) becomes a projected slot with
the info `kicad.board.kept-opaque`. This is a Fenolite rule that keeps the rebuild exact. The
emitters omit a zero footprint or pad angle and always write the text angle, as the demo boards do.

### Footprint fields (c0030)

A placed `property` of a board footprint is a `FootprintField` of `FootprintInstance.fields`, in file
order. These are Fenolite rules built on the fact rows above (`H-K-FIELD-FRAME`, `H-K-FIELD-JUSTIFY`),
both `KICAD-VERIFIED (9.0.x, 10.0.x)` by the field oracle; `fields.EVIDENCE` stays `INFERRED`, because
`place_outside` (`H-K-FIELD-OUTSIDE`) is checked for the bench references only):

- **Which properties.** A property is placed when it holds `at`, `layer` and an `effects` whose `font`
  holds `size`. Only the first property of a name is a field; a later one stays an opaque slot of the
  footprint with `kicad.board.kept-opaque` (a re-save merges duplicate names, `H-K-VENDOR-DUPNAME`). A bare
  property (`ki_fp_filters`) and every `fp_text` are read as before.
- **Text.** The value stays in the component (`Component.ref`, `value`, `properties`). The value atom is
  an opaque slot of the field, projected into the component.
- **Frame.** `position` is the stored X and Y, the pad frame. `rotation` is relative to the footprint:
  `(stored − footprint) mod 360°`, as a pad's, so rotating the footprint leaves it unchanged. The file
  holds the board angle.
- **Values.** `visible` is false for `(hide yes)` and for a bare `hide` atom in the node or in its
  `effects` (older spellings; such an atom stays an opaque slot). `size` is `Size(W, H)` of the font's
  `(size H W)`; `thickness` is `None` without a font `thickness`; `h_justify`, `v_justify` and `mirrored`
  come from the atoms of `justify`.
- **Slots.** The footprint's slot for the node is modelled (`fields`); the field carries its own slot
  list. `unlocked`, knockout and unknown children stay opaque in place. An `effects` with anything the
  emitter does not write (`bold`, a font `face`) stays a projected slot, so that field's size cannot be
  edited. An inexact `at` or font keeps the whole property a projected slot of the footprint
  (`kicad.board.inexact-length`, `kicad.board.inexact-angle`).
- **Ids.** `derived_id("fld", "kicad", "<key>:field:<name>")`, `<key>` being the native id behind the
  footprint's pad ids; `native_ids["kicad"]` is the property's uuid. A field keeps its id when KiCad gives
  the property a new uuid.

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

## Zone settings (c0031)

A copper zone carries `Zone.settings` (a `ZoneSettings`), `Zone.filled` and `Zone.locked`; a pad carries
`Pad.zone_connection`. The codec is `fenolite.backends.kicad.zones`.

- **Reading.** `connect_pads` gives `connection` (no atom → `thermal`, `yes` → `solid`, `no` → `none`,
  `thru_hole_only`) and `clearance`. `min_thickness` gives `min_thickness`. `fill` gives `Zone.filled` (the
  atom `yes`), `fill_mode` (`(mode hatch)` → `hatched`), `thermal_gap`, `thermal_spoke_width`
  (`thermal_bridge_width`), `smoothing` and `smoothing_radius`, `island_removal` (0, 1, 2 → `always`,
  `never`, `below_area`), `min_island_area` (square millimetres, converted exactly to square nanometres)
  and the fields of `hatch`. `(locked yes)` gives `Zone.locked`.
- **Absent children.** A zone without one of these children has the defaults of the table below for that
  part, and no slot. The defaults are what KiCad assumes for an absent child and what its GUI gives a new
  zone.
- **Forms per major.** A child is a modelled slot only when `zones.emit_settings` reproduces it tree-equal
  for the major of the file. For major 9 the emitter writes `island_removal_mode` and `island_area_min`
  only when the mode is not `always`; for major 10 it writes `island_removal_mode` always and
  `island_area_min` only for `below_area`. `smoothing` and `radius` are written only with smoothing, the
  hatch children only for a hatched fill, and the two hatch smoothing children only for a level above 0.
- **Opaque fallback.** A child that the emitter does not reproduce, that is repeated, or that holds an
  unknown atom, child or value stays an opaque slot with the info `kicad.board.kept-opaque`. The values it
  holds are still copied into the model (a projected slot), and a value that cannot be read keeps its
  default. A model change to such a child is refused on write with `kicad.board.projection-read-only`,
  except the fill flag: an opaque `fill` child whose atoms are the plain form (none, or `yes`) is
  written with its `yes` atom set from `Zone.filled` and its lists as read, so stale fills can be
  cleared on any zone.
- **Rule areas.** A rule area keeps these children opaque. `hatch` (the outline display),
  `filled_areas_thickness`, `attr` and `placement` stay opaque on every zone.
- **Pads.** `(zone_connect N)` with N from 0 to 3 gives `none`, `thermal`, `solid` and `thru_hole_only`;
  any other value stays opaque. A footprint-level `zone_connect` and a pad's `thermal_bridge_width`,
  `thermal_gap` and `thermal_bridge_angle` stay opaque.

| value | default | observed in |
|---|---|---|
| clearance, minimum thickness | 0.5 mm, 0.25 mm | the GUI save `defaults.zones`; a 10.0.6 re-save of absent children (S-0020) |
| connection | `thermal` | `pad_connection` 1; the re-save writes no atom (S-0020) |
| thermal gap, spoke width | 0.5 mm, 0.5 mm | `defaults.zones`; the re-save (S-0020) |
| island removal, minimum island area | `always`, 10 mm² | `remove_islands` 0, `min_island_area` 10; the re-save writes mode 0 (S-0020) |
| smoothing, radius | `none`, 0 | `corner_smoothing` 0, `corner_radius` 0 (S-0020) |
| fill mode; hatch thickness, gap, orientation, smoothing level and value | `solid`; 1 mm, 1.5 mm, 0°, 0, 0.1 | `defaults.zones`; the re-save of a bare `(mode hatch)` (S-0020) |
| hatch border, minimum hole area | `hatch_thickness`, 0.15 | the re-save of a bare `(mode hatch)` (S-0020) |
| outline display of a created zone | `(hatch edge 0.5)` | `border_display_style` 2, `border_hatch_pitch` 0.5 (S-0020) |

The values are observations of `kicad-cli` 10.0.6 and of a project saved by its GUI (`H-K-ZONE-DEFAULTS`);
none is taken from KiCad's source code.

- **Writing a created zone.** A created zone holds, in order: `net` (and `net_name` for target 9),
  `locked` when set, `layer` or `layers`, `uuid`, `name` when set, `(hatch edge 0.5)`, `priority` when
  not 0, `connect_pads`, `min_thickness`, `(filled_areas_thickness no)` for target 9 only, `fill`,
  `polygon` and the `filled_polygon` lists.
- **The target-9 pitfall.** A `20241229` zone without `(filled_areas_thickness no)` is plotted with its
  fill grown by half the minimum thickness (`H-K-ZONE-FAT9`), so a created zone always writes the flag for
  target 9. A read zone is written as it was read: KiCad 9 always writes the flag, and a zone without it
  was made by another tool, whose fills mean what that tool meant.
- **Writing a read zone.** A modelled child is emitted from the model in the target's form. A child that
  the zone does not have is inserted at its canonical position only when its part of the model differs
  from the defaults (`filled == True` counts), so an unchanged zone gains no child.
- **Clearance.** KiCad keeps the larger of the zone's clearance and the class or rule clearance
  (`H-K-ZONE-GEOM`), so Fenolite writes the zone's clearance as given and lowers no rule for it.

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

## Stack-up (c0101)

The `stackup` child of `setup` holds the board's build-up. `fenolite.backends.kicad.stackup` projects it
into `Board.stackup` (`project_stackup`), completes and writes it (`complete`, `stackup_node`,
`rewrite_setup`) and decides it across rebuilds (`merge_stackup`); `setup` itself stays an opaque root
slot. Measurements and the corpus census: `docs/evidence/kicad-stackup.md`.

| fact | source | label | hypothesis |
|---|---|---|---|
| The `stackup` section of `setup` holds `layer` entries and then `copper_finish`, `dielectric_constraints`, `edge_connector`, `castellated_pads` and `edge_plating`; a `layer` entry holds its name (a canonical copper or technical layer name, or `dielectric <id>`) and the children `type`, `color`, `thickness`, `material`, `epsilon_r` and `loss_tangent`; `general` holds a `thickness` that the page calls the overall board thickness | S-0021 | INFERRED | H-K-PCB-READ |
| KiCad-written boards hold one row per layer `F.SilkS`, `F.Paste`, `F.Mask`, `B.Mask`, `B.Paste`, `B.SilkS` with the types `Top Silk Screen`, `Top Solder Paste`, `Top Solder Mask`, `Bottom Solder Mask`, `Bottom Solder Paste`, `Bottom Silk Screen`, one row of type `copper` per copper layer, named after it, and rows named `dielectric <n>` of type `core` or `prepreg` between them; the children come in the order `type`, `color`, `thickness`, `material`, `epsilon_r`, `loss_tangent` | S-0058 | CORPUS-VERIFIED | H-K-PCB-READ |
| A dielectric row with several sheets holds, after the first sheet's children, the atom `addsublayer` and then that sheet's `color`, `thickness`, `material`, `epsilon_r` and `loss_tangent` | S-0058 | CORPUS-VERIFIED | H-K-PCB-READ |
| A solder mask row of a KiCad-written board may hold `(loss_tangent 0)`; a dielectric constant of 0 was not seen | S-0058 | CORPUS-VERIFIED | H-K-PCB-READ |
| For a complete node the Gerber job file states one entry per row and sheet with its thickness, material and colour; the dielectric constant and loss tangent only under `(dielectric_constraints yes)`, which also sets `ImpedanceControlled`; `copper_finish` as `Finish`; and the `thickness` of `general` as `BoardThickness`. A mask row with `(thickness 0)` is stated with the thickness 0 | S-0020, S-0029, S-0125 | INFERRED | H-K-STACKUP-JOB |
| KiCad uses a node only when its rows named after layers are exactly the board's silkscreen, paste and mask layers and all its copper layers, each with its layer's type, the copper rows in table order, with exactly one dielectric row between neighbouring copper rows; otherwise the board loads and the job file states no thickness. The order of the outer rows of one side does not matter, and a table without paste layers takes a node without paste rows | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-STACKUP-COMPLETE |
| Without a node the job file states 0.035 mm copper, 0.01 mm masks and n − 1 equal FR4 dielectrics of (T − 0.02 − 0.035 n) / (n − 1) mm for `general` thickness T, and the finish `None` | S-0020, S-0029 | INFERRED | H-K-STACKUP-DEFAULT |
| A re-save by 10.0.6 gives a copper row without a thickness 0.035 mm, a mask row 0.01 mm, a dielectric row without a type the type `core`, a dielectric sheet without them the material `FR4`, 4.5 and 0.02, and a node without its tail `(copper_finish "None") (dielectric_constraints no)` | S-0020 | INFERRED | H-K-STACKUP-DEFAULT |
| A re-save by 10.0.6 keeps a node in the form Fenolite writes, and keeps the `thickness` of `general` as written; `pcb export ipc2581` states the sum of the rows as `overallThickness`, also where `general` states another thickness | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-STACKUP-RESAVE |

- **Reading.** A row whose name is a layer of the board's table is that layer's row; every other row is a
  dielectric row, with `dielectric_kind` `core` or `prepreg` from its type (another type's text is kept as
  the pair `type` of the entry's `kicad` bag). `thickness` is 0 for a silkscreen or paste row without one;
  `material`, `epsilon_r`, `loss_tangent` and `color` are kept as written. Each sheet of a dielectric row
  is one entry, the sheets sharing the row's name. The outer entries of a side are ordered silkscreen,
  paste, mask from the outside in, whatever the row order. `Stackup.finish` is the `copper_finish` text
  (`""` for `None`), and `impedance_controlled` is true for `(dielectric_constraints yes)`.
  `edge_connector`, `castellated_pads`, `edge_plating` and unknown children stay in the fragment only.
- **Complete nodes only.** A node that KiCad does not use gives no stack-up and
  `kicad.board.stackup-unused`. A complete node whose values the model cannot hold exactly (a thickness
  that is not a whole number of nanometres; a copper, dielectric or mask row without a thickness; an
  `epsilon_r` that is not a plain decimal above 0 or a `loss_tangent` that is not a plain decimal; a
  dielectric row outside the outer copper rows) gives no stack-up and `kicad.board.stackup-unmodelled`.
- **Two thickness sources.** The model keeps the sum of the rows. A `general` thickness that differs from
  it gives `kicad.board.stackup-thickness`: the job file states the first, the IPC-2581 export the second.
- **Writing.** `complete` adds an entry of thickness 0 for each silkscreen, paste and mask layer of the
  table that the stack-up lacks. `stackup_node` writes one row per entry in KiCad's order of children, the
  consecutive dielectric entries of a gap as one row with `addsublayer`, a `(thickness T)` on every
  copper, dielectric and mask row (also for 0: KiCad would count 0.01 mm for a mask row without one), then
  `(copper_finish "<f>")` (`"None"` for an empty finish) and `(dielectric_constraints yes|no)`. Targets 9
  and 10 get the same node. On a created board the node is the first child of `setup` and the `thickness`
  of `general` is the sum; a board without a stack-up keeps `(general (thickness 1.6) …)` and
  `(setup (pad_to_mask_clearance 0))`.
- **Read boards.** The node of a read board is rewritten only when `Board.stackup` differs from the
  projection of its `setup` (compared by `stackup.values`: without ids, provenance and every bag pair but
  `type`). Every other child of `setup` stays at its place, `edge_connector`, `castellated_pads` and
  `edge_plating` of the replaced node follow `dielectric_constraints`, and only the `thickness` of
  `general` is rewritten. `kicad.board.stackup-rewritten` names the children of replaced rows that the
  model does not hold (for example a `locked` thickness).
- **What a script leaves out.** Fenolite writes no dielectric constant the script does not give. KiCad
  adds `(epsilon_r 4.5) (loss_tangent 0.02)` to such a dielectric when it saves the board; a later build
  then sees a board stack-up that differs from the script's and keeps it (`kicad.stackup.overridden`).
- **Created names.** `stackup`, `color`, `material`, `epsilon_r`, `loss_tangent`, `copper_finish` and
  `dielectric_constraints` are in `pcb.FLOOR_HEADS`: the format page documents each (S-0021), the boards
  of the corpus hold each (S-0058), and the created test board writes each for both majors. `type`,
  `layer` and `thickness` are in the skeleton already; `addsublayer` is an atom.

| code | severity | when |
|---|---|---|
| `kicad.board.stackup-unused` | warning | a `stackup` node that KiCad does not use (not complete) |
| `kicad.board.stackup-unmodelled` | info | a complete node with a value the model cannot hold exactly |
| `kicad.board.stackup-thickness` | warning | the `thickness` of `general` differs from the sum of the rows |
| `kicad.board.stackup-invalid` | error | on write: a stack-up with a `model.stackup-*` finding, or whose copper entries are not the table's copper layers in order; `allow_lossy` does not drop it |
| `kicad.board.stackup-rewritten` | info | on write: the replaced node of a read board held children that the model does not hold |

## Via protection (c0112)

A via may be tented, covered, plugged, capped and filled. `fenolite.backends.kicad.via_protection` reads
and writes the protection children of a via into `Via.protection` (`project_via`, `emit_via`), projects the
board's default from `setup` into `Board.via_protection` (`project_setup`) and rewrites it
(`setup_children`, `rewrite_setup`), and decides the default across rebuilds (`merge_default`); `setup`
itself stays an opaque root slot. Measurements: the design of change c0112 (2026-10-05), repeated by the
probes `via-prot-*` of `tests/kicad/vias/` on 2026-10-07; corpus census:
`docs/evidence/kicad-board-read.md`, "Via protection".

| fact | source | label | hypothesis |
|---|---|---|---|
| A via of a KiCad-written board of the 10.0 format holds, after `layers` (and after `free`), the children `(tenting (front V) (back V))`, `(capping V)`, `(covering (front V) (back V))`, `(plugging (front V) (back V))` and `(filling V)`, in that order, V being `yes`, `no` or `none`; `setup` holds `tenting`, `covering`, `plugging`, `capping` and `filling`, in that order after `allow_soldermask_bridges_in_footprints`, with `yes` or `no` | S-0058 | CORPUS-VERIFIED | H-K-PCB-READ |
| In the 21 native demo boards, 444 vias of one board of format 20250513 hold the five children with `none` values only, 6 vias of one 20260206 board hold `(capping no) (covering (front no) (back no)) (plugging (front no) (back no)) (filling no)` and no `tenting`, and 2 vias of one 9.0 board hold `(tenting front back)`; `setup` holds `(tenting front back)` on the 19 boards of the 9.0 format and the five 10.0 children (tented on both sides, the others `no`) on 2 | S-0058 | CORPUS-VERIFIED | H-K-PCB-READ |
| `none` on a via means the board's value. A re-save by 10.0.6 keeps a child that Fenolite writes: a child is written when one of its values is not `none`, a two-sided child with both sides (`(tenting (front no) (back none))` stays as written), in the order above; `setup` keeps its five children | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-VIAPROT-FORMS |
| A re-save by 10.0.6 gives a `setup` without protection children `(tenting (front yes) (back yes)) (covering (front no) (back no)) (plugging (front no) (back no)) (capping no) (filling no)`: the default of a board that states none is tented on both sides and nothing else | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-VIAPROT-FORMS |
| The mask plot (`pcb export gerbers -l F.Mask,B.Mask`) holds a flash at a via's centre on a side exactly when the via's effective tenting there is false: the via's own value, else the board's default, else tented. Covering, plugging, capping and filling open and close nothing | S-0020, S-0029, S-0125 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-VIAPROT-MASK |
| In a board of the 9.0 format a via holds at most `(tenting …)` with the atoms `front`, `back`, both, or `none`; 9.0.9 plots the named sides tented and the others open (`none` and a child without an atom: both open), a via without the child follows the board, and `setup` is read the same way (no child, or `front back`: both tented) | S-0029 | KICAD-VERIFIED (9.0.x) | H-K-VIAPROT-NINE |
| 9.0.9 does not load a board that holds a 10.0 protection form: `pcb drc` exits 3 on a 9.0 board whose via holds `(plugging (front yes) (back yes))` | S-0029 | KICAD-VERIFIED (9.0.x) | H-K-VIAPROT-NINE |
| The spelling KiCad 9 itself writes for a via tented on neither side is not observed: 9.0.9 has no headless re-save (`pcb upgrade` does not exist there). `(tenting none)` loads and plots as meant on 9.0.9 | S-0029, S-0037 | INFERRED | H-K-VIAPROT-NINE |
| 10.0.6 reads a 9.0 via child with the sides it does not name as `none`, in a 9.0 and in a 10.0 file: under a default that tents both sides it plots `(tenting front)`, `(tenting back)`, `(tenting none)` and `(tenting)` tented on both sides, where 9.0.9 leaves the unnamed sides open. It reads the 9.0 `setup` forms as 9.0.9 does | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-VIAPROT-UPGRADE |
| On 10.0.6, `pcb export drill --format gerber --generate-tenting` writes, beside the drill file, one Gerber file per feature and side that some via carries (`-tenting-front`, `-tenting-back`, `-covering-front`, `-covering-back`, `-plugging-front`, `-plugging-back`, `-filling-front-back`, `-capping-front-back`), and `pcb export ipc2581` one layer per feature and side (`COATINGNONCOND` for tenting and covering, `HOLEFILL` for plugging and filling, `COATINGCOND` for capping). Each holds exactly the vias whose own value is `yes` | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-VIAPROT-OUTPUTS |
| A board default of `yes` for all five `setup` children adds no via to those files and layers: on 10.0.6 a default of covering, plugging, capping or filling reaches no fabrication file | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-VIAPROT-OUTPUTS |

- **The model.** `ViaProtection` holds eight values, each `True`, `False` or `None`: `tenting_front`,
  `tenting_back`, `covering_front`, `covering_back`, `plugging_front`, `plugging_back`, `capping`,
  `filling`. On a via, `None` is KiCad's `none`: the board's value. `KICAD_DEFAULT` is tented on both
  sides and nothing else; `effective_default(default)` fills the `None` fields of a board default with it,
  and `effective(protection, default)` gives the eight booleans of one via. Effective values are computed,
  never stored.
- **The meaning is the file's major.** A board of the 9.0 format is read as 9.0.9 reads it: the named
  sides of a `tenting` child are `True` and the others `False`; no child is `None`. A board of the 10.0
  format is read as 10.0.6 reads it; a 9.0 child in it gives `True` for the named sides and `None` for
  the others. In `setup`, `tenting` is read in either form on boards of either major (a 9.0 child: named
  sides `True`, the others `False`); covering, plugging, capping and filling are read on 10.0 boards.
- **Slots.** Each protection child is a modelled slot of its own name. A child that the emitter for the
  board's major does not reproduce tree-equal (a 9.0 child in a 10.0 board, a 10.0 child in a 9.0 board,
  `(tenting)`, a two-sided child with one side, a child with an unknown value) stays an opaque projected
  slot with `kicad.board.kept-opaque`; a child that no form reads leaves its fields `None`. A 10.0 child
  whose values are all `none` is written again by the emitter: the via's `kicad` bag names such children
  in the pair `protection_none` (heads separated by spaces), so RT1 holds without an opaque slot.
- **Writing for target 10.** A child is written when one of its values is not `None`, with both sides, in
  KiCad's order between `locked` (c0108) and `net`. A re-save by 10.0.6 orders the children of a via
  `layers`, `remove_unused_layers`, `keep_end_layers`, `locked`, `free`, `zone_layer_connections`, the
  protection children, `net`, `uuid`; `free` and `zone_layer_connections` stay opaque, and a protection
  child added to a read via that holds them is placed after them (`pcb.OPAQUE_BEFORE`; probe
  `via-prot-order`, `equal` on 10.0.6).
- **Writing for target 9.** Only `tenting`: `(tenting front back)`, `(tenting front)`, `(tenting back)` or
  `(tenting none)`; nothing when both sides are `None`. A side that is `None` beside a stated one takes its
  value from the effective board default, so that 9.0.9 plots what the model means. A covering, plugging,
  capping or filling of `True`, on a via or in the board default, is refused with
  `kicad.board.via-protection-too-new`; `False` and `None` of those fields write nothing.
- **A 9.0 board written for target 10** gets the 10.0 form of 9.0.9's meaning (`(tenting front)` becomes
  `(tenting (front yes) (back no))`), a child kept as written included (`(tenting)` becomes
  `(tenting (front no) (back no))`): copied as it is, KiCad 10 would tent the unnamed sides. Opening a
  target-9 board in KiCad 10 itself changes the mask of vias whose child names one side or none: that is
  KiCad's conversion, not the written file.
- **The default.** A created board whose model holds a default writes the children right after
  `pad_to_mask_clearance`: the five 10.0 children with the effective values, or the 9.0 `tenting` child. A
  read board keeps its `setup` fragment while the model's default equals the projection in effect; a
  changed default rewrites the protection children in place (missing ones after the last protection child,
  else after `allow_soldermask_bridges_in_footprints`, else after `pad_to_mask_clearance`, else first), a
  default of `None` removes them, and every other child of `setup` stays at its place. The stack-up
  projection (c0101) rewrites its own child of the same fragment.
- **Projected via children.** A protection child kept as written keeps its fragment while the model agrees
  with it and the target is the board's major; otherwise it is written from the model in the target's
  form, or removed when its values are all `None`.
- **Inventory.** The token inventory holds `tenting` (9), `tenting/front`, `tenting/back`, `covering`,
  `plugging`, `capping` and `filling` (10). It holds no row for the `front` and `back` children of
  `covering` and `plugging`: such a row cannot be exercised alone above KiCad 9 (its parent is itself a
  row of KiCad 10), and the parent row already refuses the child for target 9.
- **Not modelled.** The `tenting` child of a pad stays opaque. Nothing is checked: KiCad's DRC reports
  nothing about protection.

| code | severity | when |
|---|---|---|
| `kicad.board.via-protection-too-new` | error | on write for target 9: a via, or the board default (`where` is `setup`), holds a covering, plugging, capping or filling of `True`; `allow_lossy` does not drop it |
| `kicad.via.protection-forced` | warning | build: a locked `via_protection()` replaced a board default that differed from it |
| `kicad.via.protection-overridden` | info | build: an unlocked `via_protection()` differs from the kept board default |
| `kicad.via.protection-not-exported` | info | build: vias take a covering, plugging, capping or filling of `True` from the board default only, which 10.0.6 writes to no fabrication file |

## Pad fabrication properties (c0118)

A pad may carry one fabrication mark: `(property <token>)`, a child of the pad. `_fpmap` maps it to
`Pad.fab_property` for board pads and for the pads of a footprint file (`FAB_PROPERTY_TOKENS`,
`read_fab_property`, `fab_property_node`). Measurements: the design of change c0118 (2026-10-05, 10.0.6
and 9.0.9), repeated on 2026-10-08 with `kicad-cli` 10.0.6 by the probes `pad-fabprop-*` and `asm-*` of
`tests/kicad/assembly/`; the 9.0.9 outcomes are not recorded yet.

| `fab_property` | KiCad token | aperture function of the pad's copper flash |
|---|---|---|
| `bga` | `pad_prop_bga` | `BGAPad,CuDef` |
| `fiducial_global` | `pad_prop_fiducial_glob` | `FiducialPad,Global` |
| `fiducial_local` | `pad_prop_fiducial_loc` | `FiducialPad,Local` |
| `test_point` | `pad_prop_testpoint` | `TestPad` |
| `heatsink` | `pad_prop_heatsink` | `HeatsinkPad` |
| `castellated` | `pad_prop_castellated` | `CastellatedPad` |
| `mechanical` | `pad_prop_mechanical` | `SMDPad,CuDef` on an SMD pad, as without the mark |
| `press_fit` | `pad_prop_pressfit` | `ComponentPad` on a through-hole pad, as without the mark |

| fact | source | label | hypothesis |
|---|---|---|---|
| A pad holds its fabrication mark as `(property <token>)` after `drill`, or after `size` when it has no drill, and before `layers`; `pcb upgrade --force` of 10.0.6 writes every one of the eight tokens back in that place | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PAD-FABPROP |
| The mark changes the `.AperFunction` attribute of the pad's flash in the copper Gerber, as the table above lists; `mechanical` on an SMD pad and `pressfit` on a through-hole pad keep the function of an unmarked pad (`SMDPad,CuDef`, `ComponentPad`) | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PAD-FABPROP |
| `pcb export pos --format csv` and the pad records of `pcb export ipcd356` are equal with and without the marks | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PAD-FABPROP |
| DRC reports `padstack` for `castellated` and for `mechanical` on an SMD pad, and not on a plated through-hole pad | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PAD-FABPROP |
| `pad_prop_pressfit` is a token of the 10.0 format (inventory row `pad-property-pressfit`); 9.0.9 loads the pad and drops the mark | S-0020, S-0029 | INFERRED | H-K-PAD-FABPROP |
| A mark on the placed copy of a library footprint whose library pad has none gives one `lib_footprint_mismatch` for the footprint; a footprint whose library file carries the same mark gives none | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-PAD-FABPROP-LIB |
| A fiducial made of two unnumbered SMD pads, a marked copper pad on `F.Cu` and `F.Mask` and an aperture pad on `F.Mask` only (`B.Cu` and `B.Mask` on the bottom), loads with no violation that names it, flashes a circle of the aperture pad's diameter on its mask layer, and is one `327` record on the net `N/C` in IPC-D-356 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-FIDUCIAL-FORM |
| A keep-out on the fiducial's copper layer that forbids tracks, vias and pours and allows pads gives `items_not_allowed` for a track inside it and nothing for the fiducial's pads; the refilled pour of 10.0.6 stays at the apothem of an octagonal outline, to the micrometre | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-FIDUCIAL-KEEPOUT |
| In IPC-D-356 a pad marked `testpoint` is one record on its net: `327` with the access `A01` for an SMD pad on `F.Cu` and `A02` on `B.Cu`, `317` with `A00` for a through-hole pad. The field `S` after the rotation names the sides whose solder mask covers the pad: `S0` none, `S1` the top, `S2` the bottom, `S3` both. A top pad with `F.Mask` is `S2`, a bottom pad with `B.Mask` is `S1`, a through-hole pad with both mask layers is `S0`, and a top SMD pad without a mask layer is `S3` | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-TESTPOINT-D356 |

- **Reading.** One `property` child with a token of the table is modelled: the pad has `fab_property` and
  a modelled slot. A token outside the table keeps the child opaque with `fab_property` `None` and the
  info `kicad.board.kept-opaque` (`kicad.lib.kept-opaque` in a footprint file). Several `property`
  children are each kept opaque with that info, and `fab_property` is projected from the first.
- **Writing.** A created pad writes the child after `drill` (or `size`) and before `layers`
  (`CANONICAL_ORDER["pad"]`, `PAD_CANONICAL`). A read pad without the child gains it when the model sets a
  mark, and loses it when the model clears one. A model value that differs from an opaque child gives
  `kicad.board.projection-read-only` (the read-only error of `mod.write_footprint` in a footprint file).
- **Authored and placed.** `mod.prepare_authored_definition` gives an authored pad with a mark a modelled
  slot between `drill` and `layers`, and none otherwise, so a footprint without marks keeps its bytes.
  `embed.place_footprint` keeps the mark of each pad of the definition.
- **Target 9.** `press_fit` written for target 9 is modelled content newer than the target:
  `LossyWriteError` with `kicad.token.too-new` (row `pad-property-pressfit`), with and without
  `allow_lossy`. The seven other tokens are written for both targets.
- **Not modelled.** A pad's own clearance and mask margin stay opaque, as before.

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
  `layers.created_layers(2)` is the two-copper table above. For the counts of
  `layers.CREATED_COPPER_COUNTS`, 2, 4, 6 and 8, `created_layers(n)` inserts the rows of
  `layers.inner_rows(n)` right after `F.Cu`: one row `(2k + 2 "In<k>.Cu" signal)` without a user name
  per inner layer k = 1 … n − 2, so `In1.Cu` is 4, `In2.Cu` 6, `In3.Cu` 8, `In4.Cu` 10, `In5.Cu` 12 and
  `In6.Cu` 14. The rows are the same for targets 9 and 10, and are those of KiCad's own boards (the
  layer facts above, `H-K-PCB-LAYERS`). Any other count, an odd one included, raises `ValueError`:
  KiCad refuses a table of three copper layers. `layers.created_count(names)` gives the count whose
  table has exactly these copper names. No `pcbplotparams` is written.
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
  | `property` | name, value, `at`, `layer`, `hide`, `uuid`, `effects` |
  | `effects` | `font`, `justify` |
  | `font` | `size`, `thickness` |
  | `pad` | number, type, shape, `at`, `size`, `drill`, `property`, `layers`, `net`, `zone_connect`, `uuid` |
  | `segment` | `start`, `end`, `width`, `locked`, `layer`, `net`, `uuid` |
  | `arc` | `start`, `mid`, `end`, `width`, `locked`, `layer`, `net`, `uuid` |
  | `via` | type, `at`, `size`, `drill`, `layers`, `locked`, `net`, `uuid` |
  | `zone` (also rule areas) | `net`, `net_name`, `locked`, `layer` or `layers`, `uuid`, `name`, `hatch`, `priority`, `connect_pads`, `min_thickness`, `filled_areas_thickness`, `keepout`, `fill`, `polygon`, `filled_polygon` |
  | `connect_pads` | connection atom, `clearance` |
  | `fill` (of a zone) | `yes` atom, `mode`, `thermal_gap`, `thermal_bridge_width`, `smoothing`, `radius`, `island_removal_mode`, `island_area_min`, `hatch_thickness`, `hatch_gap`, `hatch_orientation`, `hatch_smoothing_level`, `hatch_smoothing_value`, `hatch_border_algorithm`, `hatch_min_hole_area` |
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
  `gr_text`, `hide`, `island`, `justify`, `keepout`, `locked`, `mid`, `name`, `pads`, `path`, `priority`,
  `tracks` and `vias`, and the zone setting names `mode`, `smoothing`, `radius`, `island_removal_mode`,
  `island_area_min`, `hatch_thickness`, `hatch_gap`, `hatch_orientation`, `hatch_smoothing_level`,
  `hatch_smoothing_value`, `hatch_border_algorithm`, `hatch_min_hole_area` and `zone_connect` (c0031).
  Each exists in the 8.0 format (S-0021, S-0033 at tag 8.0.0), and the created test board writes each
  of them.
- **Created items.** A created footprint writes `(locked yes)` when locked, its `Reference` and
  `Value` properties at local (0, 0) with the footprint angle, on `F.SilkS` and `F.Fab` (`B.*` with
  `(justify mirror)` on the bottom), font 1 × 1 mm and thickness 0.15 mm (the skeleton's values),
  then `path` and `attr` when set. A created drawing writes `(stroke (width W) (type solid))`; circles,
  rectangles and polygons also write `(fill yes|no)`. A created text writes
  `(effects (font (size H W) (thickness T)))`, with `(justify mirror)` on a back layer. A created zone
  writes `name` and `priority` only when they are not empty or 0, and its setting children as section
  "Zone settings" describes; a created rule area writes none of them. A created fill writes `(island)` for
  target 9 when it is an island, and `(island yes|no)` for target 10.
- **Fields (c0030).** A field is written as name, value, `(at X Y A)` with the board angle
  `A = (rotation + footprint rotation) mod 360°`, always written, `(layer "L")`, `(hide yes)` only when it
  is hidden, `(uuid "U")` and `(effects (font (size H W) (thickness T)) (justify …))`; `thickness` is left
  out when it is `None`, and `justify` holds `left` or `right`, then `top` or `bottom`, then `mirror`, each
  only when set. A read field is rebuilt from its slots, so an unchanged node stays tree-equal and
  `unlocked` keeps its place. A created footprint takes the placement of each property it writes from the
  field of that name, with the uuid `kicad_uuid(field)`; a property without a field keeps the defaults
  of "Created items". A field without a slot list on a read footprint, a field of a created footprint
  whose name the component lacks, and a second field of one name raise `ValueError`: a new property node
  would make a property value writable. A read field removed from the model leaves its node out, and the
  component's property then gives `kicad.board.projection-read-only`.
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
- **Mandatory fields (c0077).** Every placed footprint holds a `Reference` and a `Value` property. A
  definition that lacks one gets it from `embed.default_fields(defn)`, before its first `property` child
  (after `at` when it has none) and before the bottom-side pass: `Reference` on `F.SilkS` at
  `FIELD_GAP` (1 mm) above `footprint_extent(defn)`, `Value` on `F.Fab` at `FIELD_GAP` below it, both on
  the centre of the box's X range, visible, at angle 0, with `(size 1 1)` and `(thickness 0.15)`. Its
  uuid is `placement_uuid(key, "/footprint/property:<name>")`. The placement is a Fenolite choice with
  no evidence label; the `property` syntax is the one recorded above (S-0001), and that KiCad accepts the
  project is `H-K-FP-FIELDS`. `mod.prepare_authored_definition` gives a definition without a file the
  same two properties as slots, so they are also in the vendored `.kicad_mod`, with the uuid
  `uuid5(FENOLITE_NS, "kicad-place-field:<lib id>:<name>")`.
- **Extent.** `embed.footprint_extent(defn)` is, in the definition's frame, the box of the modelled
  `F.CrtYd` graphics (arcs and circles boxed exactly), else the union of the pad boxes (each pad's size
  rotated by its angle about its position, rounded outward), else `BBox(0, 0, 0, 0)`. Courtyard pieces
  kept opaque (an `fp_poly` with an `arc` inside `pts`) are not counted.

### Board outline as rings (c0022)

`outline.board_outline(design)` gives the board outline as closed rings in the board frame. A design
with a model outline gives its points and cut-outs (`source` `model`). A read board gives the root
graphics on the layer of kind `edge`, chained by exact endpoint equality with `geometry.assemble_rings`
(`source` `edge`); a circle is a ring by itself. The ring of largest area is the board and the others are
its cut-outs. When no ring closes, `problem` is `open-contour`, `branching-contour`, `no-edge-content` or
`footprint-edges-only` (edge items exist only inside footprints, whose children stay opaque). Arcs and
circles are polygonised with the kernel's tolerance, and `exact` is then false.

| fact | source | label | hypothesis |
|---|---|---|---|
| The board outline is the set of closed shapes drawn on `Edge.Cuts`; root `gr_line`, `gr_arc`, `gr_rect`, `gr_poly` and `gr_circle` items on that layer, and the edge items of footprints, chain into rings | S-0010, S-0021, S-0058 | INFERRED | H-G-PLACE-OUTLINE |
| KiCad closes an outline across a gap between two endpoints below 10 µm and reports `invalid_outline` above it: a rectangle whose last line stops 9.999 µm short of its corner is closed, and 10.001 µm short is open, on 9.0.9 and 10.0.6; at exactly 10 µm, 10.0.6 closes it and 9.0.9 reports `invalid_outline` | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-OUTLINE-CHAIN |
| `fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly` items of a footprint on `Edge.Cuts` are part of the board outline: an `fp_line` that closes an opening of the root edge lines removes `invalid_outline`, and a track across an `fp_circle` on that layer inside the board gets `copper_edge_clearance` | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-OUTLINE-FPEDGE |
| A via inside a rule area whose `keepout` has `(vias not_allowed)` is reported as `items_not_allowed`, and a via closer to the board edge than the edge clearance as `copper_edge_clearance`, each naming the via | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-STITCH-AVOID |

### Moved footprints (c0022)

`replace.move_footprint` moves one footprint of a read board. A translation changes only the footprint's
`at` position: pads, graphics and fields are stored relative to it. A new rotation or side re-places the
footprint from its library definition with `embed.place_footprint`, keeping the uuid, the Reference and
Value, the user properties, the lock and each pad's net by pad number. Without a definition the rotation
or side change is refused (`place.no-definition`).

| fact | source | label | hypothesis |
|---|---|---|---|
| A footprint whose `at` position changed, with every child unchanged, is read by `kicad-cli` at the new position with the same rotation, side and pad nets | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PLACE-MOVE |
| A footprint re-placed from its library definition at a new rotation or side, with the old uuid and pad nets, is read by `kicad-cli` at the requested placement | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PLACE-MOVE |
| Two courtyards that share an edge or a corner, with disjoint interiors, give no `courtyards_overlap` violation | S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PLACE-TOUCH |

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
