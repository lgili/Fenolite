## ADDED Requirements

### Requirement: Import exposes the conversion report
`import --to python` of an Altium source SHALL give `result.report`: the report of the conversion it
imports, with the same rows `convert` gives for that source, and the conversion's issues. A KiCad source
MUST give `report` `null`. Without `--allow-lossy` an import of a source whose conversion refuses MUST exit 7
with `FEN-7001` and the same `convert.lossy` issues as `convert`.

#### Scenario: Same rows as convert
- **GIVEN** an authored Altium project
- **WHEN** it is converted to KiCad with `--allow-lossy` and imported with `--to python --allow-lossy`
- **THEN** the import's `result.report` rows equal the conversion's, and every row with lost items has a
  `convert.lossy` issue in the import
