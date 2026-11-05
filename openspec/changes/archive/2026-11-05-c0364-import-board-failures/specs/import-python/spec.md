## ADDED Requirements

### Requirement: Imported empty values stay empty
`import --to python` SHALL emit `value=""` for a source component whose value is empty, except a
board-only part, which keeps its own value without it. The import self-check SHALL NOT report
`import.unequal` for the value of such a component.

#### Scenario: An imported part with an empty value
- **WHEN** a source board holds a part with an empty value whose vendored symbol's Value is its name
- **THEN** the emitted `Part` call has `value=""`
- **AND** the rebuilt footprint's Value is empty and the self-check reports no value difference
