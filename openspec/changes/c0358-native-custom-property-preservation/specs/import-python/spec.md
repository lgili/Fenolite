## ADDED Requirements

### Requirement: Source custom properties outside the public DSL remain native-owned
A native custom footprint property excluded by the existing Part.properties validation SHALL retain its original native name, value, pose and identity in the vendored footprint definition. The generated script SHALL NOT silently erase it or relax public DSL validation.

#### Scenario: Multiline native property survives import
- **WHEN** an authored native footprint contains a named custom property with line feeds
- **THEN** import and build retain the exact native field and complete strict geometry comparison equals
- **AND** directly passing that value to Part.properties remains refused

#### Scenario: Distinct retained properties remain distinct
- **WHEN** two source instances differ only in an unrepresentable custom property
- **THEN** their vendored definitions remain distinct exact variants
- **AND** no input, field comparison or public validation is suppressed
