# schematic-composition Specification

## Purpose
TBD - created by archiving change c0165-schematic-block-composition. Update Purpose after archive.
## Requirements
### Requirement: Functional blocks without electrical changes
The system SHALL compose named functional blocks within existing electrical sheets, preserving every
component unit, stable identity, pin assignment, net and hierarchy. Blocks MUST NOT change the circuit.

#### Scenario: Explicit input to output flow
- **GIVEN** an authored input, core and output block on one sheet, ordered with `after`
- **WHEN** block composition is requested
- **THEN** blocks follow the declared reading order and every symbol unit appears exactly once

#### Scenario: A block spans electrical sheets
- **GIVEN** members of one block belong to different module sheets
- **WHEN** the intent is resolved
- **THEN** an error names the block and members and no output is written

### Requirement: Deterministic automatic grouping and ordering
The system SHALL use explicit memberships first, module grouping second and connectivity-based
automatic groups for remaining symbols. Power/global and high-fanout nets MUST NOT collapse unrelated
automatic groups. Grouping rules, thresholds, search budgets and tie-breakers MUST be versioned.

#### Scenario: Shared supply does not make one enormous block
- **GIVEN** two otherwise independent authored signal paths share a power-interface net
- **WHEN** automatic groups are formed
- **THEN** the shared supply does not merge the paths into one group

#### Scenario: Declaration order does not change geometry
- **GIVEN** equivalent intent and circuit declarations with different insertion order
- **WHEN** they are composed using the same algorithm version
- **THEN** block order, geometry, report and native output are byte-identical

### Requirement: Automatic local arrangement
The system SHALL arrange each block in its requested reading direction, align compatible connected
pins and place eligible two-pin branches near their connected anchor pins. It MUST retain all units,
support safe quarter-turn transforms and keep reference/value text horizontal and clear.

#### Scenario: Passive branches around an anchor
- **GIVEN** an authored anchor device and two eligible two-pin branches on adjacent pins
- **WHEN** their block is composed
- **THEN** branches are placed near their pin endpoints with enough separation for bodies and text

#### Scenario: Ambiguous topology
- **GIVEN** a feedback loop or multiple possible branch attachments
- **WHEN** placement candidates are selected
- **THEN** the choice is deterministic and explained in the report without claiming circuit function

### Requirement: Usable sheet area and collision constraints
The system SHALL budget symbol primitives, pins, visible text, labels, wires, ports, buses, harnesses
and block titles against the usable sheet region and template exclusions. Geometry MUST be checked
after native quantization. A fixed paper MUST NOT grow silently to accommodate overflow.

#### Scenario: Title block and long text
- **GIVEN** a fixed sheet with an authored title block, logo and long component values
- **WHEN** it is composed
- **THEN** accepted geometry avoids all reserved regions and computed visible envelopes

#### Scenario: Insufficient space
- **GIVEN** blocks that cannot fit the selected fixed paper
- **WHEN** composition exhausts its deterministic candidate budget
- **THEN** an error identifies overflowing blocks and no files are written

#### Scenario: Unverifiable template occupancy
- **GIVEN** template content whose occupied area cannot be bounded
- **WHEN** composition is requested
- **THEN** it reports that limitation as an error rather than asserting collision-free placement

### Requirement: Safe local wiring with explicit fallback
The system SHALL attempt bounded orthogonal local wires within blocks and retain labelled connections
when safe candidates cannot be found. It MUST avoid accidental junctions, foreign pins and obstacles.
Inter-block, bus and harness connections MAY retain their existing labelled representations.

#### Scenario: Short eligible connection
- **GIVEN** an aligned same-net pin pair inside a block with a clear local route
- **WHEN** connection candidates are evaluated
- **THEN** a wire joins the endpoints and its electrical readback equals the original circuit

#### Scenario: Route blocked
- **GIVEN** every allowed local route would intersect a foreign pin or occupied region
- **WHEN** the candidate budget is exhausted
- **THEN** labelled stubs retain the net and the report records a fallback reason and endpoint locators

### Requirement: Electrical proof before writes
The system SHALL read back every composed native sheet set and compare its electrical signature with
the source circuit before returning writable outputs. A difference MUST refuse the complete transaction.

#### Scenario: Accidental connection detected
- **GIVEN** a deliberately defective synthetic plan joins different nets
- **WHEN** the composed output is checked
- **THEN** the build reports an electrical error with net/pin locators and writes nothing

### Requirement: Agent report and schematic preview
The system SHALL publish a versioned structured report and SVG previews through the reviewed build
transaction. Reports MUST identify blocks, units, emitted bounds, constraint findings, fallback
connections, estimated text limits and evidence. SVGs MUST show planned symbol geometry and text,
escape input text and avoid external assets. Diagnostics MUST include a corrective action.

#### Scenario: Agent can locate a layout problem
- **GIVEN** an overflowing or conflicting block in an authored design
- **WHEN** build returns its diagnostic result
- **THEN** the agent can identify the sheet, block and affected unit paths without opening a GUI

#### Scenario: Preview corresponds to the plan
- **GIVEN** a successful composed plan
- **WHEN** its report, SVG and native bytes are emitted
- **THEN** coordinates and unit identities correspond after normalization to the native writer frame

### Requirement: Native layout replay remains authoritative
The system SHALL retain c0164 baseline checks and exact native replay. Composition changes MUST NOT
override saved native layout, including with `--discard-layout`. Generated previews MUST identify
their baseline origin and which sheets were replayed from saved native documents.

#### Scenario: Compatible composed rebuild after manual editing
- **GIVEN** a composed sheet edited and synced in Altium without electrical changes
- **WHEN** an unchanged build is confirmed
- **THEN** its native bytes are replayed exactly and its preview is identified as generated-baseline output

#### Scenario: Blocks change after native sync
- **GIVEN** a saved native sheet whose block declaration or composed baseline changes
- **WHEN** it is rebuilt
- **THEN** `build.altium-layout-conflict` prevents all writes and preserves the snapshot and project
