## ADDED Requirements

### Requirement: Copper fills and regions of a net
The Altium reader SHALL import a free fill or region on a copper layer as a filled graphic whose `net_id`
is the net of its record (none for a record without a net), keeping the net's name in the extension bag. A
KiCad conversion SHALL write such a graphic on its net, and the copper check SHALL judge it as copper of
that net. A fill or region off copper SHALL have no net.

#### Scenario: A region and a fill on the net of a pad
- **WHEN** an Altium document holds a region and a fill on a copper layer of net `GND`
- **THEN** both graphics carry the id of `GND` as `net_id`
- **AND** the converted KiCad board writes them with `(net "GND")` and verifies without unexplained differences
