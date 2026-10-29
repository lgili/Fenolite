## ADDED Requirements

### Requirement: Generated footprints in a script
`fenolite.dsl.Footprint.from_package(text, *, library="Local", positions=None)` SHALL parse one `fenolite.package.v0` record given as text and return a sealed `Footprint` holding the generated definition, bodies and model path included. Adding a pad or graphic to it MUST raise `DslError`. An error finding MUST raise `DslError` naming its code; the DSL itself MUST read no file.

#### Scenario: A generated footprint is registered
- **GIVEN** a script that reads `packages/soic8.toml` with `Path.read_text()` and calls `design.add_footprint(Footprint.from_package(text))`
- **WHEN** `uv run pytest tests/unit/dsl/test_footprint_from_package.py -k register` builds it
- **THEN** `Local:SOIC8_B4.9x3.9_P1.27` is registered with 8 pads and its bodies, and `.pad("9", ...)` on it raises `DslError`

#### Scenario: Error finding in a script
- **WHEN** `Footprint.from_package` is given a record whose span lies inside its body
- **THEN** `DslError` is raised naming `package.dimensions-inconsistent`
