## ADDED Requirements

### Requirement: Literal formatted group prefixes
Drawn group-bus parsing SHALL recognize natively measured balanced formatting spans in the prefix without mistaking them for group delimiters. The complete literal prefix SHALL remain part of each expanded member name, and expansion SHALL retain the existing member cardinality and native scoped identity policy. Malformed spans and unsupported nested groups SHALL NOT be guessed into connectivity. Standalone port diagnostics and the published reader floor SHALL remain independent.

#### Scenario: A formatted group crosses a hierarchy boundary
- **GIVEN** an original authored hierarchy whose group prefix contains a measured formatting span and whose actual port/member spellings agree
- **WHEN** its complete pin partition is resolved
- **THEN** it agrees with the native export without omitted pins or altered source names

#### Scenario: Formatting does not erase literal identity
- **GIVEN** scalar members whose spelling differs from the formatted prefix expansion
- **WHEN** the resolver compares those names
- **THEN** no visual flattening or invented alias joins them

#### Scenario: Unsupported braces do not invent members
- **GIVEN** malformed formatting, an unsupported nested group or trailing invalid content
- **WHEN** bus parsing is requested
- **THEN** it retains strict refusal/diagnostics and does not invent a member count
