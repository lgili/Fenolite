## ADDED Requirements

### Requirement: Union members travel through KiCad

A conversion of an Altium design to KiCad that carries `UnionNames` SHALL write the union index of every
union member it writes as a board property `Fenolite.Altium.UnionMembers`, keyed by the member's KiCad
uuid. A conversion back SHALL give each member that the KiCad board still holds its index. It SHALL count
`SmartUnions` lost under `altium-storage` when it holds data, as a frame-bound storage. An import of the
KiCad board to Python SHALL name each track, arc and via of the property by the uuid its table row takes in
the build, and each board text by the uuid the build gives its key, so the members survive flow A.

#### Scenario: A stitching via comes back in its union

- **GIVEN** an Altium document whose `UnionNames` names the union 1048581 and one of whose vias is a member
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the written via record holds 1048581 at offset 70, and `UnionNames` holds the source's bytes

#### Scenario: Union members survive flow A

- **GIVEN** the public row `-07`, whose five unions hold 27 tracks and 20 arcs
- **WHEN** it is imported to Python, built and converted to Altium
- **THEN** the written tracks and arcs hold the source's union indices, member for member

#### Scenario: A smart union stays behind

- **GIVEN** an Altium document whose `SmartUnions` storage holds a record
- **WHEN** it is converted to KiCad
- **THEN** the report counts `SmartUnions` lost under `altium-storage`

### Requirement: Stroke text fonts travel through KiCad

A conversion of an Altium design to KiCad SHALL write the `stroke_font` of every text and field it writes
that holds one as a board property `Fenolite.Altium.StrokeFonts`, keyed by the item's KiCad uuid. A
conversion back SHALL give each text and field of a uuid in the map its `stroke_font` again.

#### Scenario: Stroke comments come back with their font

- **GIVEN** the public row `altium-third-party-pcbdoc-04`, whose 15 stroke comments name `Arial`
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the written document's 15 stroke texts name `Arial`, and every text record holds the font type,
  name, bold and italic of the source's
