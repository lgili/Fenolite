## ADDED Requirements

### Requirement: Straight arcs and generated holes in a written document
The Altium lowering SHALL write an arc whose middle point lies on the segment between its two distinct ends
as the track from start to end with the arc's width, layer, net and lock, counted `changed` under `arc`
(`ARC_STRAIGHT`), and SHALL NOT leave it out. It SHALL write a footprint of the generated hole library
(`Fenolite_Holes`) without a reference and with one unplated pad as a free pad at the pad's board position,
counted `changed` under `footprint`, and SHALL NOT write a component for it (change c0435).

#### Scenario: A flat arc
- **WHEN** `uv run pytest tests/unit/backends/altium/test_straight_arc.py -q` writes the committed two-layer board whose first track is replaced by an arc through its middle
- **THEN** the write reports no loss, counts the arc changed, the read-back document holds one arc fewer and a track in its place, and `equivalent` reports no `equiv.route-length`

#### Scenario: Flow B with free holes
- **WHEN** `uv run pytest tests/unit/convert/test_flow_b_fidelity.py -k equivalent -q` converts an authored Altium document with two free holes to KiCad and back
- **THEN** the result holds the two free holes and no component for them, and `equivalent` of source and result exits 0
