## ADDED Requirements

### Requirement: A pin stays on the net of the sheets
The Altium import SHALL keep a pin on the net of the sheets only, when the PCB document puts its pad on a
net that no sheet holds; the pad SHALL keep its own net on the board, the import SHALL report
`altium.import.pcb-net-conflict` (warning) naming each such pin with both net names, and no pin SHALL be
a member of two nets of the circuit.

#### Scenario: A board out of sync with its schematic
- **WHEN** a pad's PCB net `SHIELD` is no net of the sheets and its pin is on the sheets' net `Vin`
- **THEN** the circuit's `SHIELD` net does not list the pin, the board pad keeps `SHIELD`
- **AND** `altium.import.pcb-net-conflict` names the pin with `Vin` and `SHIELD`
