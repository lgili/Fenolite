## ADDED Requirements

### Requirement: 3D models of an Altium import
`import --to python` of an Altium project SHALL write the same 3D models as `convert --to kicad` of it: the vendored footprints hold the `(model` entries and the import writes the model files they name (change c0409, B9).

#### Scenario: A placed STEP body
- **GIVEN** the committed blink sample whose top-side LED footprint gets an authored body naming an authored STEP file
- **WHEN** `uv run pytest tests/unit/importer/test_altium_models.py -q` converts it and imports it
- **THEN** the converted board and library and the imported library hold one `(model` per placed body, at the same `${KIPRJMOD}` path, and the imported project holds the model file at that path
