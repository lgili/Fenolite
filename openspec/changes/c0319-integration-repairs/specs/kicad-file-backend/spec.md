## ADDED Requirements

### Requirement: Moved footprint field font preservation
Re-placing a footprint on the same side SHALL retain its existing field `bold`, `italic` and `face` values beside the other placement/appearance fields. Native write/read MUST retain those values. A side change MUST keep the existing library-default policy. Default fields and native byte pins MUST remain unchanged.

#### Scenario: Rotate a manually styled field
- **GIVEN** an authored board with a manually styled reference field
- **WHEN** the footprint rotates on the same side and is written and read
- **THEN** its field position, visibility and font values survive, while a flip retains the existing definition policy
