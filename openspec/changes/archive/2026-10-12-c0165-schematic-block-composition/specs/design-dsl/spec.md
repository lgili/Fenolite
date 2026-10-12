## ADDED Requirements

### Requirement: Schematic composition declarations
The DSL SHALL provide `Design.schematic_layout(*, mode="blocks", flow="left-to-right")`,
`Design.schematic_block(key, *, members, title=None, anchor=None, after=None)` and
`schematic_composition(design)` to record and extract presentation requests without file access,
environment access or circuit mutation. Flow MUST be `left-to-right` or `top-to-bottom`.
Members MUST be existing parts of the design; every member assigns all its symbol units.

#### Scenario: Declare functional intent without coordinates
- **GIVEN** existing parts in an authored design
- **WHEN** the author declares three blocks and their `after` relationships
- **THEN** extraction returns immutable presentation intent and leaves the electrical model unchanged

#### Scenario: Invalid block declarations
- **GIVEN** duplicate members, an unknown anchor or a cycle in `after` relationships
- **WHEN** the declarations are resolved after script execution
- **THEN** a diagnostic identifies the conflicting declaration and no build output is written

#### Scenario: Unsupported target
- **GIVEN** active block-composition intent and a KiCad build
- **WHEN** the build resolves its presentation requests
- **THEN** it reports unsupported composition rather than silently discarding the intent

### Requirement: Composition selection and backwards compatibility
The Altium build SHALL accept `--altium-layout grid|blocks`. Without that flag it MUST inherit an
explicit DSL mode, or use the existing layout when there is no intent. A flag contradicting declared
intent MUST be refused. Block declarations without an enabled composition mode MUST be reported as
unused intent rather than ignored. Designs without composition MUST keep existing native output bytes.

#### Scenario: Legacy design
- **GIVEN** a design with no schematic composition declarations or selection flag
- **WHEN** its Altium project is built
- **THEN** it uses the existing cell layout and writes unchanged native documents

#### Scenario: Conflicting selection
- **GIVEN** a design declares block composition and the CLI selects `grid`
- **WHEN** build validates its arguments
- **THEN** it reports a usage error instead of silently ignoring the block declarations

#### Scenario: Block declarations without mode selection
- **GIVEN** blocks are declared but neither the DSL nor the build enables composition
- **WHEN** build resolves the presentation requests
- **THEN** it reports unused intent and writes nothing
