## ADDED Requirements

### Requirement: Empty texts of a component
The PCB document writer SHALL write the comment text record of a component whose model holds a placed
`Value` field (`PlacedComponent.comment_place`) also when the comment is empty, with that place and its
shown flag, as a saved document holds it (change c0451; four records of `altium-third-party-pcbdoc-01`). A
component without a placed field and without a comment MUST get no comment record, as before. A text of a
footprint without characters MUST be written (`pcbdoc.text_problem_of(text, footprint=True)` is `None` for
it); a board text without characters MUST stay refused.

#### Scenario: Empty value and empty text
- **GIVEN** the authored `routed` sample whose component `R1` has an empty value and a hidden `Value` field,
  and whose footprint `U1` holds a text without characters on `F.SilkS`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower_empty_texts.py -n 0 -q` writes it with
  `lower.write_design(..., rewrite=True)` and reads it back
- **THEN** `R1` holds a hidden `Value` field at its place, `U1` holds the empty text, and a board text
  without characters is counted under `text` as not written

### Requirement: Derived libraries named by the source
`lower.derived_library` SHALL put the derived footprint of a footprint whose link names an Altium library
(`project.is_altium_footprint`: its library part ends with `.PcbLib`) into a library of that file name, and
every other derived footprint into `<name>.PcbLib`, one definition per file and pattern; each component
links the file of its footprint (`footprint_library`, and the schematic part's footprint link).
`lower.write_design` and `project.write_project(..., extra_footprints=...)` MUST write each such file and
list it in the project file (change c0451). A design without such a link writes `<name>.PcbLib` alone, as
before.

#### Scenario: A source library comes back as a file
- **GIVEN** the KiCad project of the conversion of the authored `routed` sample whose `D1` links `Lib_A`
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_texts.py -n 0 -q -k links` converts it to Altium
- **THEN** the written project holds `Lib_A.PcbLib` with `Mini_LED_THT_3mm` and `Sym_A.SchLib`, the project
  file lists both, and `D1` links them
