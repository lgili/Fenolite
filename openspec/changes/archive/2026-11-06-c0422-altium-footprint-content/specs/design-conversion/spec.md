## ADDED Requirements

### Requirement: Footprint texts of an imported footprint
A conversion to KiCad SHALL write each footprint's own texts (neither its designator nor its comment) as
`fp_text user` children of the board footprint and of its library footprint, after the footprint's drawings
and before its pads, on the layer the conversion maps, with the text's string, size, stroke, justification
and angle on the board, mirrored on a back layer (change c0422).
- The report MUST count each such text under `footprint-text` and MUST NOT report it lost.
- A text on a layer without a KiCad row MUST stay a `footprint-text` loss with its reason.
- `import --to python` of an Altium source MUST vendor library footprints that hold the texts.

#### Scenario: Texts and drawings of an authored Altium document
- **GIVEN** the authored document of `tests/_fpcontent.py`: footprints with a silkscreen arc, a filled
  silkscreen polygon and rectangle, drawings on three mechanical layers, two free texts on R1 (silkscreen and
  mechanical) and one mirrored free text on the bottom LED
- **WHEN** `uv run pytest tests/unit/convert/test_footprint_content.py -q` converts it to KiCad and imports it
  to Python
- **THEN** the report counts 3 texts and 13 drawings, all written and none lost, with no `convert.lossy`
  warning of a footprint kind; the board footprints hold each drawing on its silkscreen or on the user layer
  named after its mechanical layer, and each text after the drawings and before the pads, the bottom one
  mirrored; the derived and the vendored libraries hold the 3 texts

#### Scenario: KiCad keeps the texts
- **GIVEN** the authored document converted to KiCad for the running major
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/convert/test_footprint_content_oracle.py -q` runs
- **THEN** the board loads, and on 10.0 a re-save keeps every `fp_text` with its string, layer, place, angle
  and mirror

#### Scenario: Public boards lose no footprint text
- **GIVEN** the public rows `altium-third-party-pcbdoc-01` to `-08`
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_convert_altium_census.py -k converted_reports -q`
  converts each to KiCad
- **THEN** the `footprint-text` row of rows `-02`, `-03`, `-04`, `-06`, `-07` and `-08` counts 4, 46, 3, 25,
  12 and 554 texts written and none lost, and every other loss is as before
