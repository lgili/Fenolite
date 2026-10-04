## MODIFIED Requirements

### Requirement: Assign authored footprints to parts
The DSL SHALL allow a part's existing `footprint` field to name an authored footprint's library ID. Build resolution SHALL prefer a registered authored definition with the exact ID and otherwise preserve current library resolution behavior. Pin-to-pad assignment SHALL use a part's explicit per-instance map, with identity mapping for unmapped pins. Mappings SHALL be one-to-one and SHALL be validated against resolved symbol pins and footprint pads before any output is written. Nets and no-connects SHALL continue to refer to symbol pin designators.

#### Scenario: Build with an authored footprint
- GIVEN a part assigned to a registered footprint and symbol pins whose numbers exist on that footprint
- WHEN a supported backend build resolves the part
- THEN that exact authored definition is used for placement and library output
- AND no external footprint library lookup is required for that part

#### Scenario: Reject a missing assigned pad
- GIVEN a registered footprint assigned to a part
- WHEN a connected symbol pin number has no matching pad number
- THEN build reports the existing located pin/pad mismatch and writes no partial output

#### Scenario: Build with a remapped pin
- GIVEN a part maps symbol pin `2` to physical pad `3`, and pin `2` is connected to a net
- WHEN the design is built
- THEN pad `3` carries that net while the circuit member remains pin `2`

#### Scenario: Reject invalid mappings
- GIVEN a mapping with duplicate target pads or a source/target absent from the resolved part
- WHEN the design is built
- THEN the build reports a located mapping issue and writes no partial output

## ADDED Requirements

### Requirement: Author slotted through-hole pads
The footprint DSL SHALL support a slot whose drill width is `drill`, whose overall length is `drill_length`, and whose axis is `drill_rotation` relative to the footprint. Slot length SHALL be at least its width. Round drills SHALL remain the default. Writers without evidenced slot serialization SHALL refuse the footprint with a located unsupported-feature issue. The KiCad writer SHALL refuse an axis that its oval drill form cannot encode.

#### Scenario: Serialize a slot to KiCad
- GIVEN an authored through-hole pad with slot width 0.8 mm, length 1.6 mm and `drill_rotation=90`
- WHEN its KiCad footprint is written
- THEN the drill node represents an oval of that width and length

#### Scenario: Refuse slot lowering without evidence
- GIVEN an authored slot footprint built for a target whose writer does not support slots
- WHEN the build is planned
- THEN it reports the target-specific unsupported geometry and writes no incomplete footprint
