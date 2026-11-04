## ADDED Requirements

### Requirement: Scoped bus resolution
Drawn bus resolution MUST preserve the native-validated pin partition for
authored bus, alias and hierarchy controls. Corrections SHALL preserve raw label
text, drawing geometry, generic/Altium literal semantics and existing strict
errors. An entry without a defining member label MUST NOT acquire a guessed net.

#### Scenario: Reproduced bus member join
- **GIVEN** an authored control reproduces a measured bus partition difference
- **WHEN** the resolver and the actual native KiCad CLI resolve it
- **THEN** their complete pin partitions agree after the bounded correction
- **AND** native evidence names only the version actually executed

#### Scenario: Unnamed or unrelated member
- **WHEN** a bus entry has no defining label, or a literal label is unrelated
- **THEN** the resolver keeps the existing refusal/unknown-member behavior
- **AND** raw labels, geometry and unrelated backend semantics remain unchanged

### Requirement: Bus contacts retain their layer
A bus label at a bus-side entry endpoint or bus-only junction SHALL remain a
bus label when no wire or pin meets its anchor. Real wire and pin contacts MUST
retain their existing meaning. The correction MUST preserve raw labels and
geometry and MUST NOT guess an unnamed member connection.

#### Scenario: Hierarchical bus label meets an entry
- **WHEN** an authored hierarchical bus label stands at the bus end of an entry with no wire or pin there
- **THEN** vector, group and alias members retain the native-validated partition
- **AND** the drawn source is unchanged

### Requirement: Bus definitions retain their scoped identity
Native-validated corresponding members on one connected bus SHALL join without
rewriting their qualified scalar labels. Unrelated bus groups and literal nets
MUST remain separate. Overbar spans in member names MUST remain literal and
MUST NOT be confused with group delimiters. The exact correspondence SHALL be
proved by authored native controls before implementation.

#### Scenario: Qualified bus members meet
- **WHEN** authored renamed or reordered bus definitions share a physical bus
- **THEN** their complete pin partition follows the measured native correspondence
- **AND** disconnected buses and raw label spellings remain unchanged

### Requirement: Native scalar label scopes stay bounded
KiCad scalar labels of the same literal text on one sheet SHALL follow the
native-measured local, hierarchical and global scope aliases. Unequal names
and other instances MUST retain their scope. Generic/Altium defaults and
unmatched sheet-pin diagnostics MUST remain unchanged.

#### Scenario: Local and hierarchical names meet on a sheet
- **WHEN** authored scalar labels of different scopes share exact text on one sheet
- **THEN** their pin partition follows the actual native control
- **AND** unequal names, unrelated instances and unmatched-port errors remain visible
