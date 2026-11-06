## ADDED Requirements

### Requirement: Altium round trip keeps free pads
An Altium document converted to KiCad and that project converted back to Altium SHALL keep each free pad
as a free pad (change c0447): the KiCad footprint the first conversion makes for it (link
`<project>:FREE_<footprint id>`, no reference, one pad) is written back with no component, so the document
holds as many components as its source and no Designator or Comment text of an unnamed component.

#### Scenario: A free pad comes back free
- **GIVEN** the authored `routed` sample with one more free pad of a net, written as an Altium
  document
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -n 0 -q -k free_pad` takes it to KiCad
  and back
- **THEN** the KiCad footprint of the pad is linked `routed:FREE_…`, and the round trip holds the source's
  components, one free pad at the pad's place (moved by the round trip's translation) with its net, and
  no component without a designator
