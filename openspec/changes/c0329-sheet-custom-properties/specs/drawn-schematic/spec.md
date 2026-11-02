## ADDED Requirements

### Requirement: Typed custom sheet properties
Drawn sheet references SHALL preserve ordered custom property names, texts and supported poses/fonts as typed values. Names MUST be unique, nonempty and distinct from code-owned Sheetname/Sheetfile. Empty properties MUST preserve ordinary defaults.

#### Scenario: A custom property round trip
- **GIVEN** an authored sheet reference with a custom property
- **WHEN** the closed drawn file is written and read
- **THEN** its text, order and supported effects are preserved exactly
- **AND** reserved names, duplicates and malformed records refuse

### Requirement: Custom sheet property fidelity
Supported native custom sheet properties MUST survive strict import and lowering and participate in level S and scene output. Unsupported property data SHALL refuse before staging. Electrical connectivity, source bytes, default output bytes and comparison tolerances MUST remain unchanged.

#### Scenario: A property is removed by a defective writer
- **GIVEN** a passing authored all-nine-level control with visible custom sheet text
- **WHEN** its custom property is removed from the rebuilt sheet
- **THEN** S and presentation detect the loss with no accepted difference
- **AND** the electrical comparison and original source remain unchanged

#### Scenario: Native readers disagree on legacy tilde
- **GIVEN** custom sheet text `~` in a format-9 source
- **WHEN** extraction or rendering would require choosing between conflicting native meanings
- **THEN** the operation refuses explicitly instead of substituting empty or literal text
