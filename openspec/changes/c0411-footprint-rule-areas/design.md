# Design: c0411

## Decisions (task 1.1)

1. **Frame.** A definition's rule area is in the footprint's frame, like its pads and graphics. An
   instance's area is in its pad frame, as `FootprintInstance.graphics` since c0126: a board point is
   `position + R(rotation)·p` (`Transform.placement`, as a pad), and a bottom footprint holds mirrored
   points. `model.board.placed_keepout` places one area.
2. **Layers.** Placing on the bottom swaps `F.Cu` and `B.Cu`, as for graphics. A definition's area on every
   copper layer is on `*.Cu`, as a Multi-Layer pad of a definition; placing it names the board's copper
   layers (`lens.altium._instance_keepout`). KiCad's `fp upgrade` writes such an area with its 32 copper
   layers; the KiCad reader of a definition folds them to `*.Cu`, and the writer unfolds `*.Cu` to them.
   An instance read from a KiCad board keeps the layers its zone names.
3. **Checks** (approved by the coordinator, 2026-11-05). `model.board.rule_areas(board)` gives the
   board's areas and every instance's, placed. The copper, placement, pour, crossing, router, DSN, test
   point, scene and report consumers read it. Level 7 of `equivalent` compares an instance's areas per
   footprint, in its pad frame (coordinator's ruling: KiCad stores them inside the footprint, and level 7
   is about the native file); the geometric checks see them in the board frame. Tools that edit the board's own areas (roles, copper commands, preserve, generate, importers) keep
   `Board.keepouts`. `Design.by_layer` and `layers.item_layer_counts` leave instance areas out: a KiCad
   footprint's zone names 32 copper layers on any board.
4. **Own footprint (oracle, 2026-11-05, local `kicad-cli` 10.0.6).** KiCad's DRC reports a footprint's own
   pad in its area that forbids pads, and never the footprint itself in its area that forbids footprints.
   So the copper check judges own pads, and `model.board.area_owners` lets the legality checks skip the
   area's own footprint.
5. **KiCad frame (oracle, same day).** A `.kicad_pcb` holds a footprint zone's points in the board's
   frame, not offset or turned by the footprint's `at`; a `.kicad_mod` holds them relative to the
   footprint. Hence:
   - the board reader projects a zone through the inverse placement (`fpzones.board_to_pad`);
   - `embed.placed_tree` places the zones of an embedded library tree, which it left at library
     coordinates before (a bug of every KiCad build of a footprint with a rule area);
   - `embed.local_footprint` brings them back to the footprint's frame;
   - the board writer writes a created footprint's zones placed, and for a read footprint keeps the bytes
     while its areas project unchanged, rewrites only the points when only its placement changed, and
     refuses any other change (`projection-read-only`).
6. **KiCad read.** A footprint `zone` with `keepout`, allowed/not_allowed settings, no net and one plain
   polygon is projected; the zone stays an opaque slot, as the net-tie groups. Every other footprint zone
   stays opaque. A created definition writes its areas in `fp upgrade`'s form after its graphics.
7. **Altium.** The library adapter makes rule areas of keep-outs on copper and of polygon cut-outs with
   the shapes and restrictions of the board import; a cut-out on every copper layer is on `*.Cu`. The
   board adapter keeps a component's keep-outs on its instance, in its pad frame. Drawings of the Keep-Out
   layer stay graphics of `Altium.KeepOut` in both, and `convert` makes their areas, a footprint's on the
   footprint. The PcbLib writer and the PcbDoc writer write an area as keep-out regions (the Keep-Out
   layer when it lies on every copper layer of the board, else one per layer), the PcbDoc's of the
   component, placed and flipped as the definition's graphics (`lower._library_keepout`).
8. **Proof.** The authored library and the expectations of c0410's oracle test are reused unchanged. The
   new tests compare Fenolite's import and its `.kicad_mod` with `fp upgrade`'s for the three areas on
   copper, and place the written footprint turned on a board whose DRC reports a track at the placed band.
9. **Areas the writers cannot hold (lote-23 CI, 2026-11-05).** A KiCad footprint's zone may name a
   courtyard (`BT1` of `-06`: `B.Cu`, `B.CrtYd`) or the inner layers of KiCad's stack beyond the board's
   (`U1` of `-13`). An Altium keep-out lies on a copper layer or the Keep-Out layer and restricts copper
   objects only (`pcb-records.md`, "Regions and keep-outs"; S-1711). So `lower._written_keepouts` keeps the
   board's copper layers an area names (all of them: `*.Cu`, one Keep-Out region), leaves out a copper
   layer the board lacks (it holds nothing there), counts a non-copper layer changed under `keep-out` and
   an area without a copper layer, or one the record cannot hold, lost; written areas count under
   `keep-out`. The library writer puts `In<n>.Cu` on Mid-Layer n (layer byte n + 1). The footprint reader
   takes a file's zones through its `at` whatever the root, as the writer's check does, so a definition
   read from a board and written as read round-trips its areas (`test_footprint_rt`, `-13`).

## Changed expectations

- `test_keepout_primitives.py`: a component's keep-out is a rule area of its footprint, not of the board
  (c0407 asserted the board), and a library footprint's three keep-outs are its rule areas, with no
  `altium.import.unmapped` (c0410 asserted the loss). The decision of the proposal.
- `test_roundtrip.py::test_scope_documented`: the new field `keepouts` of a footprint is written and not
  compared by RT-A2; `docs/altium.md` says so, and `test_footprint_keepouts.py` covers the round trip.
- `test_convert_altium_census.py::test_baseline_layers` (`-04`) and
  `test_altium_import.py::test_footprint_items_conserve_the_census`: the region of a component of `-04` on
  the Keep-Out layer with `KEEPOUTRESTRICTIONS` (no pads) is a rule area of its footprint on every copper
  layer, no longer a graphic of `Altium.KeepOut`. The PcbDoc and PcbLib writers write an area on every
  copper layer as such a region, so the adapter reads one back as an area; the conservation sum counts it
  as a rule area. A region of the Keep-Out layer without that flag, and every free one, stays a graphic.
- `test_convert_census.py::test_not_written_per_kind` and `test_conversion_is_explained` (`-11`, `-14`) and
  the ledger of `docs/evidence/conversion.md`: the `copper-shape` losses (2 on `One-Air-Max`, 4 on
  `RoyalBlue54L-NFC-Antenna`) are gone, because c0412 (B12) writes those shapes as regions; c0412 left
  these expectations as they were, and the integrated batch's CI measured them first.
