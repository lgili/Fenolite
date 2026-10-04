## ADDED Requirements

### Requirement: Define and register footprints
The DSL SHALL let a design declare a footprint using safe library and footprint identifiers, supported pads and graphics, and integer-nanometre geometry. Registration SHALL reject duplicate library IDs and invalid geometry before writing output. Authored definitions SHALL remain outside the canonical model and `.fenolite` persistence.

#### Scenario: Register a valid footprint
- GIVEN a design and a footprint with a safe ID, one valid pad, and supported graphics
- WHEN the footprint is registered
- THEN the design exposes its `FootprintDef` by library ID for building
- AND the canonical model contains no library definition

#### Scenario: Reject invalid or duplicate definition
- GIVEN a design with an authored footprint
- WHEN another definition has the same library ID, an unsafe name, non-positive pad size, or invalid drill
- THEN registration or construction raises `DslError` before any files are written

### Requirement: Assign authored footprints to parts
The DSL SHALL allow a part's existing `footprint` field to name an authored footprint's library ID. Build resolution SHALL prefer a registered authored definition with the exact ID and otherwise preserve current library resolution behavior. Pad numbers SHALL be mapped by the existing pin-to-pad rules.

#### Scenario: Build with an authored footprint
- GIVEN a part assigned to a registered footprint and symbol pins whose numbers exist on that footprint
- WHEN a supported backend build resolves the part
- THEN that exact authored definition is used for placement and library output
- AND no external footprint library lookup is required for that part

#### Scenario: Reject a missing assigned pad
- GIVEN a registered footprint assigned to a part
- WHEN a connected symbol pin number has no matching pad number
- THEN build reports the existing located pin/pad mismatch and writes no partial output

### Requirement: Serialize deterministic backend footprints
KiCad build SHALL serialize authored definitions into a project `.pretty` library and use the same geometry on the board. The experimental Altium build SHALL lower the documented supported subset into its PCB library. Unsupported geometry SHALL be refused with a located issue rather than silently omitted. Repeated builds from equal inputs SHALL produce byte-identical authored footprint files.

#### Scenario: Write a supported footprint
- GIVEN an authored footprint composed only of supported pads and graphics
- WHEN a dry-run build is planned and then confirmed
- THEN the output plan includes the corresponding generated library files and board placement
- AND the generated footprint bytes are deterministic

#### Scenario: Refuse unsupported geometry
- GIVEN an authored footprint containing a feature outside the supported subset
- WHEN a backend build is requested
- THEN it reports an actionable unsupported-feature issue
- AND it does not write an incomplete footprint
