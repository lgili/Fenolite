## ADDED Requirements

### Requirement: Footprint copper keeps its net

A created footprint SHALL write a graphic on a copper layer with a `net_id` as an `fp_*` node with a
`(net …)` child after its `layer`; a graphic on any other layer SHALL hold no net. `with_graphic_nets` SHALL
set `net_id` on each copper graphic of a footprint read from a board whose drawn child names a net of the
circuit.

#### Scenario: A footprint copper polygon round trip

- **GIVEN** a footprint whose filled polygon on `F.Cu` holds the net `5V`
- **WHEN** the board is written and read back, and `with_graphic_nets` is applied
- **THEN** the `fp_poly` holds `(net "5V")` and the footprint's graphic holds the id of `5V`
