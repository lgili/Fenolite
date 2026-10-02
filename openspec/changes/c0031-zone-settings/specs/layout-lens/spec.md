## ADDED Requirements

### Requirement: Zones declared in the script
`lens.preserve.merge_layout(built, board, match)` SHALL merge the zones of the built design, which `design-dsl` "Zones in the DSL" declares, with the zones of the existing board through `fenolite.backends.kicad.zones.merge_zones(built, board)`. For the board zones that match a built zone, and those whose uuid is a script-zone uuid (below), it replaces the zone rule of "Copper items follow their nets"; every other zone of the board follows that requirement.
- A built zone and a board zone MUST match when the board zone's KiCad uuid (`native_ids["kicad"]`) equals `pcb.kicad_uuid` of the built zone.
- The values compared for a matched pair are `outline`, `layers`, the net name, `priority`, `locked` and `settings.effective()`.
- A matched board zone MUST be kept with all its slots, and take the built design's net of its name, when the built zone is not locked or the compared values are equal. When they differ and the built zone is not locked, `kicad.zone.overridden` (info) MUST name the zone and the values that differ, with the hint "lock the zone in the script, edit it in KiCad, or re-run with --discard-layout".
- When they differ and the built zone is locked, the built zone MUST replace the board zone and take its `fills` and `filled`, which "Zone fills and the staleness digest" then judges, and `kicad.zone.forced` (warning) MUST name the zone and the values that differ.
- A built zone without a match MUST be added after the board's zones, in name order.
- A board zone without a match whose uuid equals `zones.script_zone_uuid(<its name>)`, the uuid that `pcb.kicad_uuid` gives a zone with the id `derived_id("zon", "dsl", "zone:<its name>")`, was written by the script for a zone that it no longer declares. It MUST be removed, with `kicad.zone.orphan` (warning) naming its name and uuid.
- Zone names alone MUST NOT match zones.
- `merge_zones` SHALL report only the codes of the closed table `zones.MERGE_ISSUE_CODES`. They are `kicad.*` codes, so they pass through `lens.preserve.PRESERVE_ISSUE_CODES` and `lens.build.BUILD_ISSUE_CODES` unchanged, as "Layout issue codes" and `design-dsl` "Build issue codes" allow.

| code | severity | when |
|---|---|---|
| `kicad.zone.forced` | warning | a locked `zone()` replaced a board zone that differed from it |
| `kicad.zone.orphan` | warning | a zone the script wrote for a `zone()` that it no longer declares was removed |
| `kicad.zone.overridden` | info | an unlocked `zone()` differs from the kept board zone |

#### Scenario: Clearance edited in KiCad wins
- **GIVEN** a confirmed target-10 build of the blink pour variant of "Zones in a build", whose zone `GND` gets the clearance 0.5 mm in its `connect_pads` by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the written zone node is tree-equal to the edited one, and `issues` holds `kicad.zone.overridden` naming `GND` and `settings`

#### Scenario: A locked zone wins
- **GIVEN** the same edited build, and the script's zone declared with `locked=True`
- **WHEN** the build runs again with `--confirm`
- **THEN** the written zone has the clearance 0.3 mm and holds `(locked yes)`, and `issues` holds `kicad.zone.forced` naming `GND`

#### Scenario: Zone added to the script
- **GIVEN** a confirmed build of the pour variant, after which `design.py` declares a second zone `VIN_TOP` on `F.Cu`
- **WHEN** the build runs again
- **THEN** the board holds `GND` and then `VIN_TOP`, and `issues` holds no `kicad.zone.*` code

#### Scenario: Zone removed from the script
- **GIVEN** a confirmed build with the zones `GND` and `VIN_TOP`, after which `VIN_TOP` is removed from `design.py`
- **WHEN** the build runs again
- **THEN** the board holds only `GND`, and `issues` holds `kicad.zone.orphan` naming `VIN_TOP`

#### Scenario: Zone drawn in KiCad
- **GIVEN** a confirmed build of the pour variant whose board gets, by token edit, a second zone on `GND` that is also named `GND`, with the uuid `00000000-0000-4000-8000-0000000000a1`
- **WHEN** the build runs again
- **THEN** both zones are written, and `issues` holds no `kicad.zone.*` code

#### Scenario: Fresh builds report no zone code
- **WHEN** the pour variant is built into an empty folder for targets 9 and 10
- **THEN** `issues` holds no `kicad.zone.*` code

#### Scenario: Zone merge codes are closed
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_zone_merge.py -k closed_set` collects every issue code that `merge_zones` produces in its tests
- **THEN** each is a key of `MERGE_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

## MODIFIED Requirements

### Requirement: Zone fills and the staleness digest
A rebuild SHALL keep the fills of a kept zone only when `zone_digest` of that zone and `fill_inputs_digest` of the board are both equal for the existing board and for the layout to be written; otherwise `lens.preserve.drop_stale_fills` SHALL drop that zone's fills, set its `filled` to false, and report `zone.fill-stale` (warning).
- `zone_digest(design, zone) -> str` MUST be the SHA-256 hex digest of a canonical text of: the outline points, or, when the outline is empty, the texts of the zone's opaque `polygon` slots; the net name; the layers; the priority; the canonical JSON of `zone.settings.effective()`; and the texts of the zone's other opaque slots (among them fill settings that the reader kept opaque). Fills, `filled`, `locked`, uuids and net forms MUST NOT enter it.
- `fill_inputs_digest(design, *, project, rules) -> str` MUST be the SHA-256 hex digest of a canonical text of: every footprint's `lib_ref`, position, rotation, side and modelled pad fields; every track, arc and via's modelled fields; every zone's `zone_digest`; every rule area; every graphic on a layer of kind `edge` and the outline; the classes, patterns and assignments that c0010's `pro.read_project` gives for `project` (none when `None`); and the texts of the rule items of c0018's `parse_rules(rules)` (none when `None`). Nets MUST enter by name; ids, uuids, provenance and slots MUST NOT enter it, and each collection MUST be sorted.
- The existing board MUST be digested with the existing project and rules texts, and the layout with the texts this build writes.
- The digests are text only: `lens` never imports `geometry`.

#### Scenario: Unchanged rebuild keeps fills
- **GIVEN** a confirmed blink build whose board gets, by token edit, a zone on `GND` on `B.Cu` holding two authored `filled_polygon` lists
- **WHEN** the build runs again
- **THEN** both fills are written unchanged and `issues` holds no `zone.fill-stale`

#### Scenario: A removed part drops fills
- **GIVEN** the same filled board and `R1` removed from `design.py`
- **WHEN** the build runs again
- **THEN** the zone is kept without fills and with `filled == False`, and `issues` holds `zone.fill-stale` naming it

#### Scenario: A class change drops fills
- **GIVEN** the same filled board and the clearance of class `PWR` changed from 0.2 mm to 0.3 mm in `design.py`
- **WHEN** the build runs again
- **THEN** the zone is kept without fills and `issues` holds `zone.fill-stale`

#### Scenario: A zone setting change drops fills
- **GIVEN** a confirmed build of the blink pour variant whose zone `GND` is declared with `locked=True` and gets, by token edit, `(fill yes …)` and two authored `filled_polygon` lists, after which `design.py` changes the zone's clearance to 0.4 mm
- **WHEN** the build runs again
- **THEN** the zone is written with the clearance 0.4 mm, without fills and without the `yes` atom of `fill`, and `issues` holds `zone.fill-stale` and `kicad.zone.forced`

#### Scenario: Digests ignore ids and formats
- **GIVEN** the filled board of a target-9 build read with `read_board`, and the same board written by `write_board` for target 10 and read again
- **WHEN** `fill_inputs_digest` and `zone_digest` are computed for both with the same project and rules texts
- **THEN** the digests are equal
