## ADDED Requirements

### Requirement: Footprint graphics of an imported footprint
A conversion to KiCad SHALL write each footprint's own lines, arcs, circles, rectangles and regions as `fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly` children of the board footprint and of its library footprint, on the layer the conversion maps, and SHALL NOT lose one in silence (change c0409, B8).
- The report MUST count `footprint-graphic` and `footprint-text` items of the source.
- A footprint text that the target does not write MUST be a `footprint-text` loss with its reason.
- A `footprint-graphic` or `footprint-text` loss MUST give one `convert.lossy` warning per kind, without refusing the conversion.

#### Scenario: Lines, arcs, circles and regions reach the board and the library
- **GIVEN** the blink sample with one authored filled region on `Mech.13` and one authored text added to a footprint
- **WHEN** `uv run pytest tests/unit/convert/test_footprint_graphics.py -k convert -q` converts it to KiCad
- **THEN** the board footprints hold 24 `fp_line`, 2 `fp_arc`, 1 `fp_circle` and 1 filled `fp_poly` on the user layer named `Mech.13`, the library footprints hold the same, the report counts 28 graphics written and 1 text lost, and one `convert.lossy` warning names `footprint-text`

### Requirement: Polygon connect styles of an Altium board
A conversion of an Altium board SHALL give each zone the connection, thermal gap and spoke width of the PolygonConnect rule that governs the pads of its net, and SHALL give a pad whose narrower rule differs its own zone connection (change c0409, B5).

#### Scenario: A board-wide style and a narrower one
- **GIVEN** the committed `board6` sample (two GND zones) with authored PolygonConnect records `All` (relief, gap 0.3 mm, spoke 0.4 mm) and a higher-ranked `InComponent('D1')` (direct)
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -q` converts it to KiCad
- **THEN** both zones have thermal reliefs with `(thermal_gap 0.3)` and `(thermal_bridge_width 0.4)`, the GND pad of D1 alone has `(zone_connect 2)`, and without records the zones keep their connection

### Requirement: Governing zone clearance
A conversion of an Altium board SHALL write as each zone's clearance the value of the Altium clearance rule that governs the polygon against any item, not the default (change c0409, B6).

#### Scenario: A class clearance governs the polygon
- **GIVEN** the `board6` sample, whose polygons are on GND in the class `PWR`, with its class x All clearance set to 0.35 mm above the board clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -k clearance -q` converts it to KiCad
- **THEN** the zone's clearance is 0.35 mm

### Requirement: Project parameters and special strings
A conversion of an Altium project SHALL write its `[Parameter<n>]` entries whose names are variable names as project text variables, report the others, and write a board text that is the special string `.NAME` of a project parameter, or holds it as `'.NAME'` inside other text, with `${NAME}` in its place; every other special string SHALL be written as typed with a `text` change in the report (change c0409, B10).

#### Scenario: A parameter on the silkscreen
- **GIVEN** a copy of the blink sample whose project holds `[Parameter1]` `Name=REV_CODE`, `Value=B2` and `[Parameter2]` `Name=Made By`, and whose board holds the texts `.REV_CODE`, `Rev '.REV_CODE' on '.Print_Date'` and `.Comment`
- **WHEN** `uv run pytest tests/unit/convert/test_project_parameters.py -q` converts and imports it
- **THEN** the `.kicad_pro` holds the text variable `REV_CODE` = `B2` alone, `Made By` gives `altium.import.unmapped`, the board texts are `${REV_CODE}`, `Rev ${REV_CODE} on '.Print_Date'` and `.Comment` with `text` changes in the report, and the imported code declares the variable and keeps `${REV_CODE}`
