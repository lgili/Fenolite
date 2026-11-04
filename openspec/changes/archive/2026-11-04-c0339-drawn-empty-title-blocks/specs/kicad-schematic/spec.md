## ADDED Requirements

### Requirement: Native blank title intent
KiCad extraction SHALL preserve empty native sheet title metadata as explicit blank drawn metadata rather than authored board inheritance. Nonempty values and existing authored inheritance SHALL remain unchanged.

#### Scenario: Dated board with blank child
- **GIVEN** an authored board and parent with a date and a native child with no title block
- **WHEN** strict import, build and full fidelity proof run
- **THEN** the child remains visibly blank, all nine levels are equal and the source remains byte-identical

#### Scenario: Authored inheritance retained
- **WHEN** an authored DrawnSheet omits title metadata
- **THEN** its existing board-title inheritance and default writer bytes remain unchanged
