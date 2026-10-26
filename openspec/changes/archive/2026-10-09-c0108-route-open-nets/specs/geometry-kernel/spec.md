## ADDED Requirements

### Requirement: Groups of touching thick shapes
`fenolite.geometry.touch_groups(items) -> list[int]` SHALL give, for a sequence of items that each hold `(key, Thick)` pairs, the group of every item as the smallest index of the items of its group: two items are in one group when a shape of one and a shape of the other have equal keys and `thick_touch` is true for them, directly or through other items ("Exact gaps between thick shapes").
- The key is any hashable value: a caller passes the layer, or the net and the layer, so shapes with different keys are never compared.
- Candidate pairs MUST come from `SpatialIndex` over `thick_bbox`, and the result MUST be the same as that of testing every pair of shapes: it MUST NOT depend on the order of the items or of their shapes.
- It MUST use integers and `Fraction` only, read no file, and import nothing outside `core` and `geometry`.
- It is the function that `checks.equivalence.routing.pieces` held privately (`_joined`, change c0089), moved without a change of result: that module MUST call it, and its tests MUST pass unchanged.

#### Scenario: A chain joins its ends
- **GIVEN** three items on the key `F.Cu`: two stadiums 5 mm apart and a third that touches both, and a fourth item whose only shape overlaps the first but has the key `B.Cu`
- **WHEN** `uv run pytest tests/unit/geometry/test_touch_groups.py` calls `touch_groups`, and again with the items reversed
- **THEN** the first three share one group, the fourth is alone, and the reversed call gives the same groups

#### Scenario: Equal to every pair
- **WHEN** `uv run pytest tests/unit/geometry/test_touch_groups.py -k brute` compares, on generated shapes, the groups with those of a union over every pair
- **THEN** they are equal

#### Scenario: The equivalence check is unchanged
- **WHEN** `uv run pytest tests/unit/checks/equivalence -k routing` runs after `pieces` calls `touch_groups`
- **THEN** every test passes without an edit
