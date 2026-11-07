## ADDED Requirements

### Requirement: Level 2 open nets of one element
Level 2 SHALL read a net whose name starts with `unconnected-(` and whose pads are all pads of one `REF-PIN` element as no net, on both sides, so that a pad on no net equals a pad on the net KiCad derives for its unconnected pin, however many pads share that number.

#### Scenario: Two pads of one number
- **GIVEN** an authored side whose connector `J4` has two pads `0` on no net, and a copy where both are on `unconnected-(J4-0-Pad0)`
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_c0281_levels.py -k open` runs level 2
- **THEN** it reports no difference; a copy where the net also holds a pad of `J5` reports a `net` difference

### Requirement: Level 6 pairs layers by name
Level 6 SHALL match the board layers of the two sides by name. A name on one side only MUST give `layer-missing` with `where` `<kind>:<name>`; a matched layer of another kind MUST give `layer-field` with field `kind`; common layers in another relative order MUST give one `layer-field` with `where` `layers` and field `order`. Ordinals MUST NOT be compared.

#### Scenario: Two user layers missing
- **GIVEN** an authored board and a copy without `Eco1.User` and `Eco2.User`
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_c0281_levels.py -k layers` runs level 6
- **THEN** it reports exactly two `layer-missing` differences, one per missing layer

### Requirement: Level 7 graphic widths
Level 7 SHALL match graphics, of the board and of each footprint pair, by layer, kind, normalised geometry and fill, and a matched pair whose width differs MUST give one `graphic-field` difference with field `width`.

#### Scenario: Outline drawn wider
- **GIVEN** an authored board whose four `Edge.Cuts` lines are 0.2 mm wide and a copy with 0.1 mm lines
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_c0281_levels.py -k width` runs level 7
- **THEN** it reports four `graphic-field` differences with field `width`, `a` `200000`, `b` `100000`, and no `graphic-missing`

### Requirement: Level 7 leaves out the lens property
Level 7 SHALL leave the footprint field `fenolite.path` out of the field comparison (`shapes.LENS_FIELDS`): the build writes it as the lens key of each footprint.

#### Scenario: Built board against an original
- **GIVEN** an authored board and a copy whose footprints carry `fenolite.path`
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_c0281_levels.py -k lens` runs level 7
- **THEN** it reports no `field-pose` difference

### Requirement: Opaque items counted at level 7
The kinds table SHALL hold `(6, "layer-field", "field")`, `(7, "graphic-field", "field")` and `(7, "opaque-count", "item")`; an `opaque-count` difference names a kind of opaque root item in `field` and the counts of each side in `a` and `b`, and the package itself MUST NOT compute it (it names no backend).

#### Scenario: Kinds and codes
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_codes.py` runs
- **THEN** the three kinds are in `KINDS`, their `equiv.*` codes are in `EQUIVALENCE_CODES` and `fenolite explain equiv.opaque-count` exits 0
