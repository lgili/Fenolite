## ADDED Requirements

### Requirement: Unmeasured body records stay declared
The Altium import SHALL give a component body known heights only when its projection side, model type and
heights match a case that public files or a saved kit file prove. Every other body SHALL be kept with
unknown heights and an `altium.import.body-unknown` warning that names its reasons.

#### Scenario: A body projected from the other side
- **WHEN** a top component holds a body whose `BODYPROJECTION` is 1 and no saved kit file measures that case
- **THEN** the body is kept with unknown heights and the import warns `altium.import.body-unknown`

#### Scenario: A measured case
- **WHEN** a saved kit file proves the meaning of a body record that was unknown
- **THEN** the import gives such bodies their heights and the fact is recorded with its source and label
