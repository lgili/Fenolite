## ADDED Requirements

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

## MODIFIED Requirements

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
