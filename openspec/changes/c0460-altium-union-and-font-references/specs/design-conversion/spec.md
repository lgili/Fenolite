## ADDED Requirements

### Requirement: Union members travel through KiCad

A conversion of an Altium design to KiCad that carries `UnionNames` SHALL write the union index of every
union member it writes as a board property `Fenolite.Altium.UnionMembers`, keyed by the member's KiCad
uuid. A conversion back SHALL give each member that the KiCad board still holds its index. It SHALL count
`SmartUnions` lost under `altium-storage` when it holds data, as a frame-bound storage.

#### Scenario: A stitching via comes back in its union

- **GIVEN** an Altium document whose `UnionNames` names the union 1048581 and one of whose vias is a member
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the written via record holds 1048581 at offset 70, and `UnionNames` holds the source's bytes

#### Scenario: A smart union stays behind

- **GIVEN** an Altium document whose `SmartUnions` storage holds a record
- **WHEN** it is converted to KiCad
- **THEN** the report counts `SmartUnions` lost under `altium-storage`
