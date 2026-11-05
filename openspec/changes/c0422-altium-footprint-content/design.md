# Design: keep everything an Altium footprint draws

## Context

- The Altium import (`adapter.copper.footprint_items`, change c0126) gives each component's tracks, arcs,
  fills and regions as footprint `Graphic`s and its texts, beyond the first designator and comment, as
  footprint `Text`s, in the pad frame, with a text's angle relative to the footprint.
- `convert --to kicad` maps their layers (`altium_to_kicad.map_layers`: an overlay to its silkscreen,
  `Mech.<n>` to a `User.<k>` row whose user name is `Mech.<n>`) and writes the board with created footprints.
  c0409 made a created footprint write its graphics; its texts were dropped with a ledger loss.
- The derived library (`footprint_files`) is the board footprint read back and rewritten, so a child of the
  board footprint reaches the library.
- `import --to python` of an Altium source converts to KiCad in memory first (`cmd_import._read`) and vendors
  the converted library.
- `equivalent` reads a KiCad board with `read_board`, which keeps a footprint's `fp_*` children in slots;
  `fpitems.with_footprint_items` projects them on request (c0126), and nothing in `equivalent` asked.

## Decisions

1. **Where a text goes.** After the drawings and before the pads: in the 18 boards of the 10.0.6 demos, all
   2 175 footprints with `fp_text` children (4 720 texts) place them so (S-0058, census of 2026-11-05).
   `CANONICAL_ORDER["footprint"]` gains `fp_text` there, and `_WRITE_FIELDS["footprint"]` maps it to `texts`.
   A read footprint writes no new text node (its texts stay in their slots), as for graphics.
2. **What a text writes.** The node a created board text writes, with the leading word `user`: the angle on
   the board (`pad_angle_to_board`, `H-K-PCB-FPGFX` and the field rows), the font size and stroke, the
   justification of the model, `bold`, `italic`, `face` and `knockout` when set, `(justify mirror)` on a back
   layer. The import gives an Altium text the centred anchor and no mirror of its own, as it gives a free text
   (the Altium writer holds the same convention: `lower._items` writes only a centred text), so the
   conversion is consistent with the board texts it already writes.
3. **The ledger.** The blanket `footprint-text` drop goes. A text on a layer without a KiCad row is still
   dropped by `map_layers` with its reason, and `WARNED_LOSSES` keeps both footprint kinds.
4. **`equivalent` is c0421's.** A prototype here prepared the KiCad side of an Altium against KiCad
   comparison (projected footprint items, `User.<n>` named `Mech.<n>` renamed to `Mech.<n>`). Change c0421
   (`equivalent-pairing-noise`, on its own branch) completes a cross-backend KiCad side with the same
   projection and pairs layers by user name, so the prototype was withdrawn to keep one implementation. This
   change proves what c0421 relies on: the KiCad side of the authored conversion projects all 13 drawings and
   3 texts on the expected layers (`test_the_kicad_side_projects_every_footprint_item`).

## Measured

- Row `-06` (`cobra.PcbDoc`), level 7 before: 1 027 `graphic-missing`, 27 `text-missing`, 54 footprint items
  compared. With the footprint texts written and the withdrawn prototype of decision 4: 1 072 footprint items
  compared; the only differences left are the two keep-out regions of `USB301`, which the conversion reports
  as changed into rule areas (change c0411).
- Census rows `-02`, `-03`, `-04`, `-06`, `-07`, `-08`: 4, 46, 3, 25, 12 and 554 footprint texts, all written,
  none lost; every other loss unchanged.
- `kicad-cli` 10.0.6: the converted fixture loads, and a re-save keeps its three texts with string, layer,
  place, angle and mirror. 9.0.9 (pinned image): the target-9 board loads (`pcb drc` exits 0).

## Risks

- A board whose footprints hold many texts now writes them; DRC's silkscreen checks may report texts that
  were never written before. That is the board's content, not a regression.
- The derived library compares instances by their written text: two instances of one pattern whose texts
  differ now count as "differs from the library footprint", as instances whose drawings differ already did.
