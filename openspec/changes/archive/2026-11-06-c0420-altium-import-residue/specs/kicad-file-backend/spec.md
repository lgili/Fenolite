## ADDED Requirements

### Requirement: Net-tie groups of a created footprint
`write_board` SHALL write the `net_ties` of a footprint it creates whole (one without slots, such as a converted Altium footprint) as one `net_tie_pad_groups` child after `attr`, one string per group with its numbers joined by `", "`, instead of refusing them; the projection rules for a read footprint are unchanged (change c0420, N1).

#### Scenario: A created net tie
- **WHEN** `uv run pytest tests/kicad/convert/test_a2k_load.py -k net_tie -q` writes a converted footprint with the group `("1", "2")`
- **THEN** the board holds `(net_tie_pad_groups "1, 2")` after the footprint's `attr`, and `read_board` gives the footprint that group
