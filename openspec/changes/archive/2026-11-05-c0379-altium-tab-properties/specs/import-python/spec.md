## ADDED Requirements

### Requirement: TAB values of non-KiCad sources are declared losses
`import --to python` of a source whose backend is not KiCad SHALL count each component property whose
value holds U+0009 TAB as the unexpressed kind `property-tab` and SHALL go on with the import. The
emitted code SHALL NOT hold the property. The KiCad native TAB contract (c0363) SHALL NOT change.

#### Scenario: An Altium parameter with a TAB
- **WHEN** an Altium project holds a component parameter whose value contains a TAB
- **THEN** the import plans its files instead of exiting 3
- **AND** `result.unexpressed` lists `property-tab` with that reference and parameter name
