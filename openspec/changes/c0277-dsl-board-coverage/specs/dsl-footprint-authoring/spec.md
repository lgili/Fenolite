## ADDED Requirements

### Requirement: Shaped pads in authored footprints
`Footprint.pad` SHALL accept `shape="trapezoid"` with `delta`, `chamfer` (parts per million, 0 to 500 000) with `corners` on `rect` and `roundrect`, `radius_ratio` on `roundrect`, and `shape="custom"` with `anchor` (`circle` or `rect`) and `primitives` built by `footprint.poly`, `segment`, `circle` and `arc` in pad coordinates. Each value outside these rules MUST raise `DslError` naming the argument.

#### Scenario: Four shaped pads
- **GIVEN** an authored footprint with one trapezoid, one chamfered rectangle, one rounded rectangle and one custom pad
- **WHEN** it is serialised and read back with `read_footprint`
- **THEN** each pad has its shape, `trapezoid_delta`, `chamfer_ratio` and `chamfer_corners`, `corner_ratio`, or `anchor_shape` and primitives as declared, and two serialisations are byte-identical

#### Scenario: Refused shape values
- **WHEN** `fp.pad("1", …, shape="trapezoid")` without `delta`, `fp.pad("2", …, chamfer=600_000, corners=("top_left",))` and `fp.pad("3", …, shape="custom", primitives=())` are called
- **THEN** each raises `DslError` naming `delta`, `chamfer` and `primitives`

#### Scenario: Footprints without the arguments
- **WHEN** every authored footprint of the examples is serialised before and after this change
- **THEN** the bytes are equal
