## ADDED Requirements

### Requirement: Only measured open-pin characters become supported
An open or no-connect-marked pin name containing `#` SHALL be written with its exact native derived name only after authored native9/10 controls prove that spelling. Other unmeasured characters SHALL retain the existing refusal/unnamed-pad behavior. Native class membership comparison SHALL remain strict.

#### Scenario: A marked open pin uses a measured hash character
- **WHEN** the pin is named `RESET#`
- **THEN** its generated native net name equals the actual native export and the pad retains that named-net assignment
- **AND** no accepted difference or class-comparison exclusion is added
