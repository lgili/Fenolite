## ADDED Requirements

### Requirement: Drawn font losses stay explicit
The Altium drawn writer SHALL report new explicit fonts or poses it cannot lower through its existing loss policy. Strict conversion MUST refuse those losses. Absent styles MUST keep existing output bytes, and no native acceptance or new Altium hypothesis stem SHALL be inferred from unit readback.

#### Scenario: Unsupported explicit font
- **WHEN** an authored drawn font has no proved Altium lowering
- **THEN** its existing not-lowered diagnostic identifies the item and strict conversion refuses

#### Scenario: Legacy drawing
- **WHEN** an old drawing with no new style is written to Altium
- **THEN** its existing planned bytes remain unchanged
