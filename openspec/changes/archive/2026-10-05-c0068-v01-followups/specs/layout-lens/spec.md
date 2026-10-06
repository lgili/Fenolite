## ADDED Requirements

### Requirement: Pad zone connections across rebuilds
`lens.build.build_design` SHALL decide the zone connection of every pad that a request names (`design-dsl`, "Pad zone connections in the DSL") when a build merges an existing board, with this precedence: a locked request, then a setting that the pad carries on the board, then an unlocked request, then the pad of the library footprint. A setting made in KiCad therefore wins over the script unless the script locks the request, as for zones ("Zones declared in the script") and fields ("Footprint fields across rebuilds").
- The step MUST run on the `Merged` result of `merge_layout`, after `merge_fields` and before the merged layout is validated and written. The normal-form pass of "Preservation is the build's normal form" MUST NOT run it, because the written board already holds the decided pads.
- **Kept footprints** (the board's own node, "Kept and re-placed footprints"). Each named pad MUST be decided by `fenolite.backends.kicad.zones.keep_pad_connections(kept, requests, *, where, issues=None) -> FootprintInstance`, `where` being the component path:
  - a pad whose `zone_connection` equals the request stays as it is, without an issue;
  - a pad whose `zone_connection` is `None`, that is a pad without a setting of its own on the board, MUST take the request's value, locked or not, without an issue;
  - a pad that carries another value than an unlocked request MUST stay as the board has it, with one `kicad.pad.zone-overridden` (info) naming the part, the pad, both values and the hint "lock the request in the script, edit the pad in KiCad, or re-run with --discard-layout";
  - a pad that carries another value than a locked request MUST take the request's value, with one `kicad.pad.zone-forced` (warning) naming the part, the pad and both values;
  - a request whose number or index the kept footprint does not have MUST give `kicad.pad.zone-unknown-pad`, as on a built copy.
- **Re-placed and new footprints** keep the pads of the built copy: the library's pads with every request applied (`design-dsl`, "Pad zone connections in a build"). A pad edit made in KiCad is not carried to a re-placed footprint.
- A pad that no request names MUST stay as "Kept and re-placed footprints" leaves it: as edited in KiCad on a kept footprint.
- `keep_pad_connections` MUST be pure and MUST change nothing but `Pad.zone_connection` of the named pads. Run again on its own result with the same requests, it MUST return an equal footprint, and a locked request then reports nothing.
- `result.preserved.pad_zones` MUST hold two sorted lists of `"<component path>:<pad number>"`, each entry once: `kept` (unlocked requests that differ from the setting of a board pad) and `forced` (locked requests that replaced the setting of a board pad). Both are empty when no existing board was read; "Layout preservation evidence" allows the key.

#### Scenario: A pad edited in KiCad wins over an unlocked request
- **GIVEN** a confirmed target-10 build of the blink pour variant whose `design.py` calls `d1.zone_connection(1, "solid")`, whose board then gets `(zone_connect 1)` in pad `1` of `D1` by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the written pad holds `(zone_connect 1)`, `issues` holds one `kicad.pad.zone-overridden` naming `D1`, pad `1`, `solid` and `thermal`, and `result.preserved.pad_zones` has `kept == ["D1:1"]` and an empty `forced`

#### Scenario: A locked request wins
- **GIVEN** the same edited board, and the request in `design.py` given `locked=True`
- **WHEN** the build runs again with `--confirm`
- **THEN** the written pad holds `(zone_connect 2)`, `issues` holds one `kicad.pad.zone-forced`, and `result.preserved.pad_zones.forced == ["D1:1"]`

#### Scenario: A request added after the first build
- **GIVEN** a confirmed build of the pour variant without a request, after which `design.py` gains `d1.zone_connection(1, "solid")`
- **WHEN** the build runs again with `--confirm`
- **THEN** `D1` is listed under `result.preserved.kept`, its pad `1` gains `(zone_connect 2)`, `issues` holds no `kicad.pad.*` code, and both lists of `result.preserved.pad_zones` are empty

#### Scenario: Rebuilds of an unedited board are quiet and stable
- **GIVEN** a confirmed target-9 build of the variant with the unlocked request
- **WHEN** the build runs twice more with `--confirm`
- **THEN** both lists are empty, `issues` holds no `kicad.pad.*` code, and both rebuilds write every file with the bytes of the first build

#### Scenario: A re-placed footprint takes the request
- **GIVEN** the edited board of the first scenario, and `D1` given a locked `place()` 2 mm to the right of its board position
- **WHEN** the build runs again with `--confirm`
- **THEN** `D1` is re-placed (`layout.place-forced`), its pad `1` holds `(zone_connect 2)`, and `issues` holds no `kicad.pad.*` code
