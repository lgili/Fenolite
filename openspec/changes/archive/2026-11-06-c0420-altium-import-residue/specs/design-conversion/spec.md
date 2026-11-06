## ADDED Requirements

### Requirement: Named polygon connect scopes
A conversion of an Altium board SHALL read a Polygon Connect Style scope of named polygons (`IsNamedPolygon('n')`, or such terms joined by `Or` or `||`, one pair of parentheses round the whole allowed) as the pours of those names, compared without case, and SHALL give each zone the connection of the record that governs it by its own name. A pad whose governing records give it one style, other than its zones give, for every zone of its net SHALL get that style as its own zone connection; a pad whose records give different styles between the zones of its net MUST keep its setting, with a `pad` change in the report (change c0420, B5).

#### Scenario: A named polygon
- **GIVEN** the committed `board6` sample (GND pours `GND_L01_P000` and `GND_L06_P001`) with authored records `All` (relief) and a higher-ranked `All` × `IsNamedPolygon('gnd_l01_p000')` (direct)
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -k named -q` resolves the connections
- **THEN** `GND_L01_P000` is solid, `GND_L06_P001` thermal, and no zone or pad has a change

#### Scenario: Pad styles differ between zones
- **GIVEN** the same sample with `All` (relief) and a higher-ranked `InComponent('D1')` × `IsNamedPolygon('GND_L06_P001')` (direct)
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -k differ -q` resolves them
- **THEN** both zones are thermal, the GND pad of D1 keeps no own connection, and the report holds its `pad` change

### Requirement: Smallest governing zone clearance
A conversion of an Altium board SHALL write as each zone's clearance the smallest `min` of the Altium clearance rules that govern a pair of its polygon and an item: in Altium's order, every rule with a scope matching the polygon, up to and with the first whose other scope is `All`. Ignored rules MUST NOT count. Without such a rule against any item, the zone MUST keep its clearance with a `zone` change; a zone whose written clearance differs from the one it was read with MUST also have a `zone` change (`CLEARANCE_FROM_RULES`). KiCad lets a matching custom rule decide a fill's gap and takes the larger of the zone's clearance and a netclass clearance (`H-K-ZONE-CLEARANCE`), so the written DRU rules carry every wider value (change c0420, B6; it replaces the first-rule value of change c0409).

#### Scenario: A narrower pad rule ranks above the class rule
- **GIVEN** the `board6` sample with its class × All clearance set to 0.35 mm and an authored higher-ranked `IsPad` × All clearance of 0.25 mm
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -k smaller -q` converts it to KiCad
- **THEN** both zones have the clearance 0.25 mm, and the report holds a `zone` change for each

#### Scenario: KiCad's rule over the zone's clearance
- **GIVEN** an authored board with a zone of net `A` round a track of net `B`
- **WHEN** `uv run pytest tests/kicad/fill/test_zone_clearance_oracle.py -q` refills it with KiCad 10.0.6
- **THEN** a zone clearance of 1.0 mm with a custom rule of 0.2 mm on `B` gives a 0.2 mm gap, a zone of 0.2 mm with a rule of 1.0 mm a 1.0 mm gap, and without a rule the larger of the zone's and the netclass clearance

### Requirement: Keep-out restrictions of the Keep-Out layer
A conversion of an Altium board SHALL give the rule area of a keep-out of the Keep-Out layer (second flag byte 2) the restrictions of its own value: a region's `KEEPOUTRESTRICTIONS`, or the byte of a track, arc or fill. 1 forbids vias, 2 tracks, 4 poured copper, and 8 with 16 pads. The conversion MUST read the value from the drawing's record in the source document, found by its locator, and MUST add no model field or extension key. A drawing of the Keep-Out layer without the flag, or whose record or document cannot be read unchanged, MUST forbid all four, as before (change c0420, N2 and N3).

#### Scenario: A keep-out forbids what its value forbids
- **GIVEN** four authored Keep-Out-layer polygons with the values 7, 24, 8 and none
- **WHEN** `uv run pytest tests/unit/convert/test_to_kicad.py -k restrictions -q` converts them
- **THEN** their rule areas forbid vias, tracks and pours; pads alone; nothing; and all four

#### Scenario: The value is read from the source record
- **GIVEN** the authored keep-out document with four keep-out tracks of value 31 on the Keep-Out layer
- **WHEN** `uv run pytest tests/unit/convert/test_to_kicad.py -k source_records -q` reads their restrictions, then reads them again after one byte is added to the document
- **THEN** the first read gives 31 for each of the four drawings and the second gives none

### Requirement: Net-tie components of an Altium board
An import of an Altium board SHALL give a component whose `COMPONENTKIND` is 3 (net tie in the BOM) or 4 (net tie) one net-tie group of its distinct pad numbers in pad order, and none when it has fewer than two numbers. A conversion to KiCad SHALL write the group (change c0420, N1).

#### Scenario: A net-tie kind
- **WHEN** `uv run pytest tests/unit/backends/altium/test_net_tie_kind.py -q` imports authored component records of every kind
- **THEN** kinds 3 and 4 give one group of the distinct numbers, the other kinds none

#### Scenario: A converted net tie in KiCad's DRC
- **GIVEN** the blink sample with one two-pad footprint given a net-tie group and a copper line joining its pads
- **WHEN** `uv run pytest tests/kicad/convert/test_a2k_load.py -k net_tie -q` converts it and runs KiCad's DRC
- **THEN** the board holds one `net_tie_pad_groups`, reads back with the group, and has the violations of the board without the line; without the group the line adds `clearance` and `solder_mask_bridge`

### Requirement: Board holes counted as changed
A conversion to KiCad SHALL count each board `Hole` that it writes as a board-only generated footprint under `hole` as changed: an unplated hole with `HOLE_REASON`, a plated one with `PLATED_REASON`. KiCad holds no hole outside a footprint (change c0167), so no hole changes kind without an entry (change c0420).

#### Scenario: An unplated hole
- **WHEN** `uv run pytest tests/unit/convert/test_convert_slots.py -k unplated -q` converts the committed slots document
- **THEN** the `hole` row counts every hole of the source as changed, with `HOLE_REASON`, and none as written or lost
