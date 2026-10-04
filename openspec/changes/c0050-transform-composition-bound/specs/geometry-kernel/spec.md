## MODIFIED Requirements

### Requirement: Placement transforms
`Transform` SHALL represent `p ↦ R(θ)·M^m·p + t`, where `M` mirrors about the local X axis (`y ↦ −y`) and is applied first, with `θ` normalised to `[0, 360 000 000)`; its properties `dx` and `dy` SHALL return the exact translation as `Fraction`. It SHALL provide `apply`, `apply_angle` (`u ↦ (−u if mirror else u) + θ` modulo a full turn), `apply_segment`, `apply_arc`, `apply_polygon`, `apply_bbox` (outward), `compose(inner)` that applies `inner` first and rounds once (each coordinate within 0.5 nm of the exact composed map), `inverse()`, and `Transform.placement(at, rot_udeg, mirror=False)`. Two successive `apply` calls round twice: for all transforms `a` and `b` and every integer point `p`, each coordinate of `a.apply(b.apply(p))` SHALL be within `(1 + |cos θa| + |sin θa|) / 2` nm of `A(B(p))`, where `A` and `B` are the unrounded maps of `a` and `b` and `cos θa`, `sin θa` are the fixed-point values `a` uses; this is at most `(1 + √2) / 2` nm (about 1.2072 nm) and SHALL NOT be stated as 1 nm. `inverse()` SHALL be exact for multiples of 90° with integer translation; for every other transform `t` and every integer point `p`, `t.inverse().apply(t.apply(p))` SHALL be within 1 nm of `p` per axis. `apply_arc` and `apply_polygon` SHALL raise `GeometryError` with code `geometry.degenerate` when the rounded points no longer form a valid `Arc` or `Polygon`.

#### Scenario: Footprint placement
- **WHEN** `Transform.placement(Point(1000, 2000), 90_000_000).apply(Point(0, 100))` is called
- **THEN** it returns `Point(1100, 2000)`

#### Scenario: Mirror first
- **WHEN** `Transform.placement(Point(0, 0), 0, mirror=True).apply(Point(5, 7))` is called
- **THEN** it returns `Point(5, -7)`

#### Scenario: Relative to absolute angle
- **WHEN** `Transform.placement(Point(0, 0), 90_000_000, mirror=True).apply_angle(30_000_000)` is called
- **THEN** it returns `60_000_000`

#### Scenario: Angle normalisation
- **WHEN** `Transform.rotation(-90_000_000).rot_udeg` is read
- **THEN** it is `270_000_000`

#### Scenario: Composition adds angles
- **WHEN** `Transform.rotation(30_000_000).compose(Transform.rotation(60_000_000))` is compared with `Transform.rotation(90_000_000)`
- **THEN** they are equal

#### Scenario: Exact inverse for quarter turns
- **WHEN** `Transform.placement(Point(1000, 2000), 90_000_000).inverse().apply(Point(1100, 2000))` is called
- **THEN** it returns `Point(0, 100)`

#### Scenario: Inverse round trip at other angles
- **GIVEN** generated transforms whose angle is not a multiple of 90°, with translations and points within ±2^30 nm
- **WHEN** `t.inverse().apply(t.apply(p))` is computed
- **THEN** each coordinate differs from `p` by at most 1 nm

#### Scenario: Mirror reverses orientation
- **GIVEN** the polygon `(0, 0), (10, 0), (10, 10), (0, 10)` with `area2 == 200`
- **WHEN** `Transform.placement(Point(0, 0), 0, mirror=True).apply_polygon` is applied to it
- **THEN** the returned polygon, before normalisation, has `area2 == -200`, and its `normalize()` equals `Polygon((Point(0, -10), Point(10, -10), Point(10, 0), Point(0, 0)))`

#### Scenario: Degenerate after rounding
- **WHEN** `Transform.rotation(30_000_000)` is applied with `apply_arc` to `Arc(Point(0, 0), Point(1, 0), Point(1, 1))` and with `apply_polygon` to the polygon `(0, 0), (0, 1), (-1, 1)`
- **THEN** each call raises `GeometryError` with code `geometry.degenerate` (the rounded `mid` equals the rounded `end`; two rounded vertices coincide)

#### Scenario: Two applies stay within the two-rounding bound
- **GIVEN** generated transforms `a` and `b` and generated integer points `p`
- **WHEN** `a.apply(b.apply(p))` is compared with the exact rational `A(B(p))`
- **THEN** each coordinate differs by at most `(1 + |cos θa| + |sin θa|) / 2` nm, and `(|cos θa| + |sin θa|)² ≤ 2` for the fixed-point values of every generated angle

#### Scenario: Two-rounding bound is tight
- **GIVEN** `b = Transform(0, False, 2**127, 2**127)` (a translation by half a nanometre on each axis), `p = Point(1, 1)`, and `a` a rotation by `45_000_000` whose X translation makes the X coordinate of `A(Point(2, 2))` a half-integer that rounds up
- **WHEN** `a.apply(b.apply(p))` is compared with the exact rational `A(B(p))`
- **THEN** the X coordinates differ by exactly `(1 + cos θa + sin θa) / 2` nm, which is more than 1.2071067811865475 nm

#### Scenario: Two applies exceed 1 nm with integer translations
- **WHEN** `Transform.rotation(315_000_000).apply(Transform.rotation(30_000_000).apply(Point(0, 1_386_483)))` is compared with the exact rational composed map
- **THEN** one coordinate differs by more than 1.206 nm and by no more than `(1 + √2) / 2` nm
