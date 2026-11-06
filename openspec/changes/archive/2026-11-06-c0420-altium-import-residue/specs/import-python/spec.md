## RENAMED Requirements

- FROM: `### Requirement: TAB values of non-KiCad sources are declared losses`
- TO: `### Requirement: TAB values of non-KiCad sources`

## MODIFIED Requirements

### Requirement: TAB values of non-KiCad sources
`import --to python` of a source whose backend is not KiCad reads the board of the source's in-memory KiCad conversion. A component property whose value holds U+0009 TAB, and whose footprint holds exactly one field of that name, SHALL be kept natively in the vendored footprint, as the KiCad native TAB contract (c0363) keeps it, so the import needs no `--allow-lossy` (change c0420). A property without exactly one such field SHALL be counted as the unexpressed kind `property-tab`, and the import SHALL go on (change c0379). In both cases the emitted code SHALL NOT hold the property, and the public `Part.properties` contract and the KiCad native TAB contract SHALL NOT change.

#### Scenario: An Altium parameter with a TAB
- **WHEN** `uv run pytest tests/unit/importer/test_native_tab_property.py -k another_backend -q` imports a converted board whose part holds a parameter with a TAB as one footprint field
- **THEN** nothing is unexpressed, the emitted code holds neither the TAB nor the parameter, and exactly one vendored `.kicad_mod` holds the property

#### Scenario: A parameter without its field
- **WHEN** the same test imports that board with the parameter's field removed from the footprint
- **THEN** the import plans its files instead of exiting 3
- **AND** `result.unexpressed` lists `property-tab` with that reference and parameter name
