## ADDED Requirements

### Requirement: Unnumbered pads in RT-A3
RT-A3 SHALL compare a pad without a number in the component that holds it, as the write keeps it there (`altium-pcb-writer`, "Connector and free pads"): a round or slotted non-plated pad whose copper is its hole stays a pad of its component and is not expected as a board hole. A moved pad without a number MUST remain a difference.

#### Scenario: Round and slotted pads without a number
- **GIVEN** a component footprint with an unnumbered round non-plated pad whose size is its drill and an unnumbered slotted one whose size is (length, drill)
- **WHEN** the document is written, read again and judged by RT-A3
- **THEN** the second reading holds both in the component and no board hole, the trip is equal, and the round pad moved by 0.1 mm makes the trip unequal

## REMOVED Requirements

### Requirement: Detached hole pads in RT-A3
**Reason**: change c0433 writes a pad without a number in its component, so no pad is detached and the reader makes no board hole of one.
**Migration**: none; "Unnumbered pads in RT-A3" states what RT-A3 compares.
