## ADDED Requirements

### Requirement: Altium round trip keeps the board
An Altium document converted to KiCad and that project converted back to Altium SHALL keep the board's
shape and connections (change c0441): every arc of the board ring comes back as an arc, every via and pad
comes back (a via whose hole equals its diameter included, a rounded-rectangle pad with its corner ratio),
a free copper region of a net comes back with that net,
and every pad and via is its source moved by one translation, to the nanometre.

#### Scenario: Vias and pads come back
- **GIVEN** the authored `routed` sample moved by 1 mm, its first via with a hole equal to its diameter
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k vias` takes it to KiCad and back
- **THEN** the report of the second conversion loses no via and no pad, and the pads and vias of the round
  trip are those of the source moved by one translation

#### Scenario: The board shape comes back
- **GIVEN** the `routed` sample with one corner rounded by a 5 mm arc, written as an Altium document
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k rounded` takes it to KiCad and back
- **THEN** the written outline holds one arc vertex, and `equivalent` at level 7 in the relative frame
  reports no difference of the board shape

#### Scenario: A region of a net comes back with it
- **GIVEN** the `routed` sample with a filled 2 mm square copper region of a net on `F.Cu`, written as an
  Altium document
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k region` takes it to KiCad and back
- **THEN** the copper graphic of the round trip has the same net
