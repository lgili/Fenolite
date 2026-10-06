## ADDED Requirements

### Requirement: Altium write of a model
`AltiumBackend.write(design, *, target=None, allow_lossy=False)` SHALL accept a `Design` that holds a circuit and a board and SHALL return the files of an Altium project (project file, schematic documents, PCB document) written from the model alone, through `backends.altium.lower.from_design`.
- The placements, pads, copper, zones, rules, stack and classes MUST come from the model; no script, library path or other file is read.
- What the model holds and the writers cannot carry MUST be reported with the writers' issue codes; an error-level loss MUST need `allow_lossy`.
- The write MUST be deterministic: two calls on equal designs give equal bytes.
- `fenolite build --target altium` MUST produce its files through the same function, from the model it stores in `.fenolite/`.

#### Scenario: A KiCad board written as Altium documents
- **GIVEN** the routed two-layer KiCad sample, read with the KiCad backend
- **WHEN** `AltiumBackend().write(design)` runs and the result is imported
- **THEN** the imported design is equal to the KiCad design at levels 1 to 5 of `equivalent` within the triangle profile's tolerances

#### Scenario: Build and write agree
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k build_agrees` builds each example and writes its stored model with `write`
- **THEN** the two file sets are equal byte for byte
