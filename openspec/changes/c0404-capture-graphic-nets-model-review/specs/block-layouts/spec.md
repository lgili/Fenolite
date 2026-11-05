## ADDED Requirements

### Requirement: Captured copper graphics keep their nets
`fenolite blocks capture` SHALL give every copper item it reads from the user's board that names a net, a copper graphic included, the id of the same-named net of the recorded circuit. A graphic without a net MUST stay without one.

#### Scenario: A copper polygon read from the board
- **GIVEN** a built bench board whose read nets have other ids than the recorded ones, with one copper
  polygon on a net and one silk line
- **WHEN** the capture builds its current model
- **THEN** the polygon carries the recorded id of its net and the silk line carries no net
