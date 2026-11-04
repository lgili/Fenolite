## ADDED Requirements

### Requirement: Explicit standard technical layers
Design.board SHALL accept optional technical_layers selecting known non-copper standard rows, with Edge.Cuts required. None MUST preserve existing defaults. Unknown, duplicate, copper and User.n names MUST be refused. The selection SHALL use existing Board.layers without new persisted model fields; independent User.n declarations remain supported.

#### Scenario: Omit unused Eco layers
- **GIVEN** an explicit selection containing every standard row except Eco1.User and Eco2.User
- **WHEN** the design is converted and built
- **THEN** the board contains exactly those technical rows and its ordinary copper/User.n rows

#### Scenario: Invalid selection
- **WHEN** the selection has an unknown or duplicate name, a copper/User.n name, or no Edge.Cuts
- **THEN** board() refuses the input before a build can write
