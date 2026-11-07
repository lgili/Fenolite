## ADDED Requirements

### Requirement: Body and model ledger of an Altium import
`import --to python` of an Altium project SHALL hold every model reference and model file that `convert --to kicad` of it writes, and SHALL report each `body` or `model` loss of that conversion as a `convert.lossy` warning; it MUST NOT lose a body or a model silently.

#### Scenario: The authored fixture imported
- **GIVEN** the authored PCB document of `tests/_altium_models.py`
- **WHEN** `uv run pytest tests/unit/importer/test_altium_models.py -q` converts it and imports it
- **THEN** the imported library and board name the same model paths as the conversion, the imported project holds each of those files, and no `convert.lossy` warning names `body` or `model`

#### Scenario: A loss is reported
- **GIVEN** a body of unknown geometry in the same source
- **WHEN** it is imported
- **THEN** the issues hold one `convert.lossy` warning whose `where` is `body`
