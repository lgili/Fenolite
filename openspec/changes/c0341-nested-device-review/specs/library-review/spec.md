## ADDED Requirements
### Requirement: Direct nested device review resolves declared library dependencies
The review loader SHALL resolve a nested device's sibling symbol and footprint
from the same enclosing library when its adjacent valid manifest binds the
selected record to that device. Discovery SHALL be bounded and SHALL preserve
the exact-content sheet/plan and stale-dependency checks.

#### Scenario: Review a selected nested device
- **WHEN** a matching device manifest lists the selected nested record and its dependencies exist in the enclosing library
- **THEN** the device can be checked and explicitly accepted using its exact sheet
- **AND** changing a dependency invalidates that acceptance

#### Scenario: Do not trust an unrelated manifest
- **WHEN** the adjacent manifest is invalid or identifies another device
- **THEN** it does not authorize discovery of an enclosing support tree
- **AND** missing local dependencies remain an error
