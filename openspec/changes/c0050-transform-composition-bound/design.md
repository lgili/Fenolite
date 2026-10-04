## Context

`Transform.apply(p)` computes the exact image of an integer point with the fixed-point table
(`cos θ` and `sin θ` as integers scaled by 2**128) and rounds each coordinate half to even. Write
`A` for the unrounded map of a transform `a`: `A(v) = L·v + t`, where `L = R(θa)·M^m` and

```
R(θ) = |  c  s |      c = cos θa, s = sin θa (the table values, as exact rationals)
       | −s  c |
```

`M` only flips the sign of `y`. `compose(a, b)` builds one transform, so `compose(a, b).apply(p)`
rounds once. `a.apply(b.apply(p))` rounds twice.

## Goals / Non-Goals

- Goal: state and test the true bound of two successive `apply` calls, and show that it is tight.
- Non-goal: any change of behaviour. See the proposal.

## Derivation

### Which norm

The test, the docs and the spec measure the error **per axis**: `|x − x_exact|` and
`|y − y_exact|` separately (the maximum norm). This change keeps that norm. The Euclidean figure is
given at the end for reference.

### Bound

Let `p` be an integer point.

1. `q = b.apply(p) = B(p) + e1`, where `e1 = (e1x, e1y)` is the first rounding error:
   `|e1x| ≤ 1/2` and `|e1y| ≤ 1/2`.
2. `a.apply(q) = A(q) + e2`, with `|e2x| ≤ 1/2` and `|e2y| ≤ 1/2`.
3. `A` is affine, so `A(q) = A(B(p)) + L·e1`. The total error is `E = L·e1 + e2`.
4. With `u = ±e1y` (the sign comes from the mirror):
   - `Ex = c·e1x + s·u + e2x`, so `|Ex| ≤ (|c| + |s|)/2 + 1/2`;
   - `Ey = −s·e1x + c·u + e2y`, so `|Ey| ≤ (|c| + |s|)/2 + 1/2`.

So, per axis, exactly and with no epsilon:

```
|E| ≤ (1 + |cos θa| + |sin θa|) / 2          (bound 1, depends on the outer transform only)
```

For real angles `|cos θ| + |sin θ| ≤ √2`, with equality at 45°, 135°, 225° and 315°. Hence

```
|E| ≤ (1 + √2) / 2 ≈ 1.2071067811865475 nm    (bound 2, for every pair of transforms)
```

The audit's figure is confirmed. The 1 nm of the test and of `docs/geometry.md` was wrong: it adds
the two rounding errors as if the first one passed through unchanged, which is true only when the
outer angle is a multiple of 90°.

### Bound 2 holds for the table values too

The table holds rounded values, so `|c| + |s| ≤ √2` needs a check.

- At 45° + k·90° the table gives `|c| = |s| = r`, where `r` is `√(2**255)` rounded. A probe gives
  `(2r)² − 2·2**256 < 0`, so `|c| + |s| < √2` there. A test asserts this with integers.
- At every other angle the nearest diagonal is at least 1 µdeg away, so the real sum is at most
  `√2·cos(1 µdeg) ≈ √2 − 2.2e-16`. Rounding two table entries adds at most `2**-128 ≈ 2.9e-39`.

So bound 2 holds with no epsilon. The property test asserts `(|c| + |s|)² ≤ 2` on every generated
angle.

### Tightness

Bound 1 is reached exactly when both roundings are ties in the right direction:

- `b = Transform(0, False, 2**127, 2**127)` translates by 0.5 nm on each axis. `B((1, 1)) = (1.5,
  1.5)` rounds half to even to `q = (2, 2)`, so `e1 = (+0.5, +0.5)`.
- `a` rotates by 45° and has `tx_fixed = (3·2**128 + 2**127) − 2·(c + s)`, so the X coordinate of
  `A(q)` is exactly 3.5, which rounds to 4: `e2x = +0.5`.
- `Ex = (c + s)/2 + 1/2`, which is bound 1 exactly and is less than `2**-128` nm below bound 2.
  Measured: 1.2071067811865475 nm.

A translation by a fraction of a nanometre arises from `compose` and from the public constructor.
With integer translations only, a probe of `b = rotation(30°)`, `p = (0, y)` for every odd `y` up to
2 000 000 and `a` a diagonal rotation gives at most **1.2061108782941439 nm**, at `y = 1 386 483`
with `a = rotation(315°)`. Both are examples in the tests.

### The other two statements stay

- `compose(a, b).apply(p)` rounds once: 0.5 nm per axis, plus the rounding of the composed
  translation to 2**-128 nm and the difference between the table entry of the summed angle and the
  product of two table entries. The test keeps its `2**-100` allowance. Unchanged.
- Inverse round trip: `t.inverse().apply(t.apply(p))` has the same real bound of about 1.2071 nm
  (plus terms far below 1e-20 nm from the rounded inverse translation and the table). But here the
  result and `p` are both integer points, so the difference per axis is an integer, and an integer
  that is at most 1.21 in size is at most 1. The stated 1 nm is correct. `docs/geometry.md` gains
  this reason.

### Euclidean figure, for reference

`|L·e1| = |e1| ≤ √2/2` and `|e2| ≤ √2/2`, so the Euclidean error is at most `√2 ≈ 1.4142` nm. The
spec does not state it and no test asserts it.

## Decisions

1. **Assert bound 1, not only bound 2.** Bound 1 is rational, so the test compares `Fraction`s with
   no tolerance, and it is sharper: at multiples of 90° it is the old 1 nm. Bound 2 is asserted
   through `(|c| + |s|)² ≤ 2`, in integers. Rejected: `Fraction(1207107, 10**6)`, which is a rounded
   constant and hides the reason.
2. **Deterministic worst case.** One `@example` on the property (the integer-translation case) and
   one plain test for the exact tie case. Rejected: fixing the Hypothesis seed, which would hide
   other inputs.
3. **Spec.** The living requirement "Placement transforms" states no bound for two `apply` calls.
   The delta is MODIFIED, copies the full living text and adds one sentence and three scenarios. No
   active change modifies this requirement (checked on 2026-10-04), so there is no order to state.
4. **No source change.** The derivation shows no defect in `transform.py`. Its docstrings do not
   state the 1 nm bound for two applies.

## Files and public API

- `tests/unit/geometry/test_transform.py`: changed.
- `docs/geometry.md`: two bullets.
- `CHANGELOG.md`: one line.
- No module is created and no public API changes.

## Sources registered by this change

None.

## Hypotheses registered by this change

None.

## Evidence level per behaviour (before merge)

| Behaviour | Level |
| --- | --- |
| Bound of two successive `apply` calls | proved here and checked by exact rational tests; no evidence label applies (no format fact, no external tool) |

## Risks / Trade-offs

- The tie example uses `Transform(rot, mirror, tx_fixed, ty_fixed)` directly. It is the public
  constructor, and `compose` produces such values.
- The probe for integer translations is a search over one family, not a proof of the maximum. The
  test claims only "more than 1.206 nm and within the bound".

## Open Questions

None.
