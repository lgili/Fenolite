## ADDED Requirements

### Requirement: Native root hierarchical ports retain standalone connectivity
The KiCad drawn resolver SHALL preserve native root hierarchical labels as
same-sheet connections without requiring an invented parent sheet pin. This
exception MUST apply only to the root instance through the KiCad adapter.
Unmatched child labels or parent pins MUST retain their errors. Generic model
resolution MUST retain its existing strict absent-parent diagnostic.

#### Scenario: Root port is native standalone source
- **WHEN** authored root labels and the complete source pin universe are compared against native9/10
- **THEN** pins, partitions and names agree and no false parent requirement blocks lowering

#### Scenario: Child mismatch remains an error
- **WHEN** a child hierarchical label has no matching pin on its actual parent reference
- **THEN** drawn.sheet-pin-unmatched still refuses and repeated children remain isolated
