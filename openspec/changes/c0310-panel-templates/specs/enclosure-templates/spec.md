## ADDED Requirements

### Requirement: Template content
A face template SHALL be drawn in the face's frame as seen from outside and SHALL hold the outer rectangle, the split line on walls, the dashed flat rectangle, a datum corner at the outer rectangle's lowest u and v, and each aperture of the face grown by its clearance with a centre cross, its size and its part's reference.

#### Scenario: Front face of the example
- **GIVEN** `examples/enclosure/fit_box.py` built in `tmp_path`, with `J1` on `front` and `D1` and `SW1` on `top`
- **WHEN** `uv run pytest tests/unit/enclosure/test_templates.py -k front` computes the front template
- **THEN** it holds one opening for `J1` whose centre, from the datum, equals the hand-computed u and v, and whose size is the aperture plus twice its clearance

### Requirement: Template formats at exact scale
The SVG SHALL give `width` and `height` in mm with a millimetre `viewBox`; the PDF SHALL use points of 1/72 inch with `/PrintScaling /None`; the DXF SHALL use millimetres with `$INSUNITS` 4 and only `LINE`, `ARC`, `CIRCLE` and `TEXT`. SVG and PDF MUST carry a 100 mm scale bar and "print at 100 %".

#### Scenario: Sizes in each format
- **WHEN** `uv run pytest tests/unit/enclosure/test_template_formats.py` writes the front template of a fixture whose outer front is 120 mm by 40 mm
- **THEN** the SVG's `width` is `120mm` plus the margins, the PDF's `MediaBox` width is that length times 72/25.4 to 4 decimals, and the DXF's outline lines span 120 mm

### Requirement: Templates are byte-identical
The same board, fit record and options SHALL give the same bytes for every template; no date MAY appear unless `--timestamp` is given, and then only as the PDF's `/CreationDate`.

#### Scenario: Golden files
- **WHEN** `uv run pytest tests/unit/enclosure/test_templates.py -k golden` writes the example's templates twice
- **THEN** both runs equal the golden files under `tests/data/enclosure/templates/` byte for byte, and no file holds a date
