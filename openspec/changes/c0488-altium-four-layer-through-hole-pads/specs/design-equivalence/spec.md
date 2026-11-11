## MODIFIED Requirements

### Requirement: Tolerances and normalisation
`Tolerances(length_nm=0, angle_udeg=0, length_ppm=0)` SHALL hold three non-negative integers; a negative value or a non-integer MUST raise `ValueError`. The rules of `norm.py` MUST be these, in integer arithmetic only:
- **Length.** Two lengths are equal when the absolute value of their difference is at most `length_nm`. Two points are equal when both coordinates are; no Euclidean distance is taken. Two sizes are equal when both axes are.
- **Routed length.** Two routed lengths `p` and `q` of level 5 are equal when the absolute value of their difference is at most `max(length_nm, max(p, q) × length_ppm // 1_000_000)`. `length_ppm` applies to nothing else.
- **Angle.** `normalise(angle)` is `angle mod 360_000_000`, in `[0, 360_000_000)`. `angle_distance(a, b, period)` is `min(d, period - d)` with `d = (a - b) mod period`. Two angles are equal when their distance is at most `angle_udeg`. The period is `360_000_000` unless a rule below says otherwise.
- **Side.** `top` and `bottom` are compared exactly. No tolerance applies.
- **Text.** Values, references, pin numbers and footprint names are compared as exact strings; no case folding and no trimming.
- **Footprint name.** The compared name is the part of `FootprintInstance.lib_ref` after its last `:`, or the whole text when it has none.
- **Pad rotation by shape.** A `circle` pad, and an `oval` pad whose two sizes are equal within the tolerance, has no rotation: the field is not compared. A `rect`, `oval` or `roundrect` pad is compared with period `180_000_000`, and it MUST also be equal to a pad whose size axes are swapped and whose rotation differs by `90_000_000` modulo `180_000_000`; in that case neither `pad-size` nor `pad-rotation` is reported. A `trapezoid` or `custom` pad is compared with period `360_000_000`. When the two pads of a pair have different shapes, the field is not compared if either has no rotation, and the smaller of the two periods applies otherwise.
- **Pad shape.** `shape_class(pad, tolerances)` is `circle` for an `oval` pad whose two sizes are equal within `length_nm`, and `Pad.shape` otherwise. `pad-shape` MUST compare the two classes, so an equal-sized `oval` and a `circle` of that size are the same shape; their sizes are still compared.
- **Copper span.** A pad's copper span is the subset of `{top, inner, bottom}` its `layers` reach: a layer name is looked up in `Board.layers`; a `copper` layer with the lowest ordinal among copper layers is `top`, with the highest `bottom`, any other `inner`. Layers of another kind are ignored. A layer name that `Board.layers` lacks makes the span unknown, and an unknown span is not compared and is counted in the level summary as `copper_unknown`. A plated pad with a hole whose layers name every copper layer of its board (by name or by a wildcard such as `*.Cu`) has the span `all` (change c0488). `all` equals `all` whatever the number of copper layers of each board, so a through-hole pad of a 2-layer board and one of a 4-layer board compare equal. `all` differs from any other span, and `span_text` writes it as `all`.
- **Frame.** With `frame="absolute"` the translation is `(0, 0)`. With `frame="relative"` the translation is `(median_low(dx), median_low(dy))` over the components compared at level 4, with `dx` and `dy` the position of side `b` minus that of side `a`; it is `(0, 0)` when no component is compared. A position differs when `b - a - translation` exceeds the length tolerance on either axis. The report MUST hold the translation.
- No rotation or mirror of a whole board is removed.

#### Scenario: Angle wraps
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_norm.py -k angle` runs
- **THEN** `angle_distance(359_999_999, 0, 360_000_000)` is 1, `normalise(-90_000_000)` is `270_000_000`, and two rotations of `-90_000_000` and `270_000_000` are equal at tolerance 0

#### Scenario: Length tolerance is per coordinate
- **GIVEN** two points that differ by 10 nm on x and 10 nm on y
- **WHEN** they are compared with `Tolerances(length_nm=10)` and with `Tolerances(length_nm=9)`
- **THEN** they are equal in the first case and different in the second

#### Scenario: Rectangular pad turned by a quarter
- **GIVEN** a `rect` pad of `1000000x500000` at rotation 0 and a `rect` pad of `500000x1000000` at rotation `90_000_000`
- **WHEN** level 3 compares them at tolerance 0
- **THEN** no `pad-size` and no `pad-rotation` difference is reported, and the same pads at rotations 0 and `45_000_000` give one `pad-rotation` difference

#### Scenario: Equal-sized oval is a circle
- **GIVEN** an `oval` pad of `1600000x1600000` on side `a` and a `circle` pad of `1600000x1600000` with the same number on side `b`
- **WHEN** level 3 runs at tolerance 0
- **THEN** no `pad-shape` difference is reported, and the same `oval` of `1600000x1700000` gives one `pad-shape` difference `oval`/`circle`

#### Scenario: Board moved as a whole
- **GIVEN** a design with three footprints and a copy with every footprint moved by `(5_000_000, -3_000_000)` and one of them moved by a further `(1_000_000, 0)`
- **WHEN** level 4 runs with `frame="relative"` and then with `frame="absolute"`
- **THEN** the first run reports the translation `(5_000_000, -3_000_000)` and exactly one `position` difference, for the footprint moved further, and the second run reports a `position` difference for every footprint

#### Scenario: Bad tolerance
- **WHEN** `Tolerances(length_nm=-1)` is built
- **THEN** it raises `ValueError`

#### Scenario: Through-hole pads of a 2-layer and a 4-layer board
- **GIVEN** an authored through-hole pad on `*.Cu` in a 4-layer board on side `a`, and the same pad on `F.Cu` and `B.Cu` in a 2-layer board on side `b`
- **WHEN** level 3 compares them
- **THEN** no `pad-copper` difference is reported

#### Scenario: A pad that misses an inner layer
- **GIVEN** an authored plated pad on `F.Cu`, `In1.Cu` and `B.Cu` of a 4-layer board on side `a`, and the same pad on every copper layer of a 4-layer board on side `b`
- **WHEN** level 3 compares them
- **THEN** one `pad-copper` difference is reported, `top,inner,bottom`/`all`
