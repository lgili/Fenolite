## ADDED Requirements

### Requirement: Script copper in a merge
`lens.preserve.merge_layout(built, board, match)` SHALL pass the existing board and the built design to `copper.merge_copper` (`manual-copper`, "Script copper is regenerated") and SHALL keep only the existing tracks, arcs and vias that it keeps; "Copper items follow their nets" then applies to those, and the built design's tracks and vias whose KiCad uuid is a copper uuid MUST follow them in the layout, in the built order.
- This takes out of "Copper items follow their nets" exactly the existing tracks, arcs and vias that `merge_copper` drops: those whose KiCad uuid is a copper uuid, and those without one that equal a script item.
- The issues of `merge_copper` (`kicad.copper.stale`, `kicad.copper.regenerated`, `kicad.copper.duplicate`) MUST join the merge's issues; as `kicad.*` codes they pass through `PRESERVE_ISSUE_CODES` unchanged, as "Layout issue codes" allows, and `result.copper` counts them.
- A footprint moved in KiCad therefore pulls its script copper along on the next build; an intent removed from the script removes its copper; copper drawn in KiCad, whose uuid is not a copper uuid, stays under "Copper items follow their nets".
- `lens.preserve` still never imports `geometry`: `merge_copper` compares points and fields as integers and texts.

#### Scenario: Copper follows a moved footprint
- **GIVEN** a confirmed target-10 build of `examples/blink_routed/design.py` in `B`, whose board had `D1` moved 4 mm to the right by `tests/_layout_edit.py::move_footprint`
- **WHEN** the build runs again with `--confirm` and the written board is read with `read_board`
- **THEN** the `led_a` track that ends at `D1` pad `2` ends at the pad's new position with its uuid unchanged, `issues` hold one `kicad.copper.regenerated` per moved track and no `kicad.copper.stale`

#### Scenario: Removed intent, removed copper
- **GIVEN** the same confirmed build and the stitch intent `gnd_fence` removed from `design.py`
- **WHEN** the build runs again with `--confirm`
- **THEN** the board holds none of its vias, and `issues` hold one `kicad.copper.stale` warning per removed via

#### Scenario: KiCad edit of script copper is replaced
- **GIVEN** the same confirmed build whose `led_drv` segment `seg[0]` was moved 1 mm by token edit, keeping its uuid
- **WHEN** the build runs again with `--confirm`
- **THEN** the segment is back at its pads, and `issues` hold one `kicad.copper.regenerated` naming its uuid

#### Scenario: Copper drawn in KiCad is kept
- **GIVEN** the same confirmed build with one `GND` track added by token edit with a version-4 uuid
- **WHEN** the build runs twice
- **THEN** the track is kept, and the second build writes every file with the bytes of the first
