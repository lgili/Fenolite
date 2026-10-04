## Why

`tests/unit/geometry/test_transform.py::test_composition_rounds_once` fails at random. It is a
Hypothesis property, and its last line asserts that `a.apply(b.apply(p))` is within 1 nm per axis of
the exact composed map. That bound is wrong:

- The first `apply` rounds each coordinate, with an error of up to 0.5 nm per axis.
- The second transform rotates that error vector before the second rounding. One output coordinate
  then carries up to `0.5·(|cos θ| + |sin θ|)` nm of it, which is `√2/2` nm at 45°.
- The second rounding adds up to 0.5 nm.

The true bound per axis is `(1 + √2)/2 ≈ 1.2071` nm. Hypothesis found a legitimate input 1.0000257 nm
off (recorded in the tasks of the archived change c0031, task 11.1) and replays it from the local
example database, so `make check` fails on that machine. `docs/geometry.md` states the same 1 nm.
The living spec `geometry-kernel` states no bound for two successive `apply` calls at all.

The transform code is correct: each `apply` rounds the exact image half to even. Only the claimed
bound is wrong.

## What Changes

- `tests/unit/geometry/test_transform.py`:
  - `test_composition_rounds_once` asserts the derived bound `(1 + |cos θa| + |sin θa|)/2` nm per
    axis, exactly, with rationals, and carries an explicit example that is more than 1.206 nm off.
  - It also asserts that the fixed-point `|cos θ| + |sin θ|` never exceeds `√2`, so the bound is at
    most `(1 + √2)/2` nm. A new test checks the four diagonal angles, where the sum is largest.
  - A new test reaches the bound exactly with two ties, and shows an input with integer translations
    more than 1.206 nm off.
- `docs/geometry.md`: the bullet about two successive `apply` calls states `(1 + √2)/2` nm and why;
  the bullet about the inverse round trip states why 1 nm still holds there.
- `openspec/specs/geometry-kernel`: the requirement "Placement transforms" states the bound for two
  successive `apply` calls, with three scenarios.
- `CHANGELOG.md`: one line under "Fixed".

## Capabilities

### Modified Capabilities (no new capability)

- `geometry-kernel`: requirement "Placement transforms" (MODIFIED; one sentence and three scenarios
  added, nothing removed).

## Non-goals

- No change to `src/fenolite/geometry/transform.py` or to any other source file. No behaviour changes.
- No change to the bound of `compose(a, b).apply(p)` (0.5 nm) or of the inverse round trip (1 nm).
  The derivation in `design.md` confirms both.
- No change to the Hypothesis settings, profiles or the example database.
- No Euclidean bound in the spec. The test and the docs speak per axis; `design.md` gives the
  Euclidean figure for reference only.

## Evidence level required

- This is exact integer and rational arithmetic, with no file format and no external tool. No
  evidence label applies and none moves.
- The bound is proved in `design.md` and checked by a property test and by explicit examples that
  reach it.
- No row of `docs/hypotheses.md` or `docs/evidence/sources.md` changes. No source is cited.

## Impact

- Files: `tests/unit/geometry/test_transform.py`, `docs/geometry.md`,
  `openspec/specs/geometry-kernel/spec.md` (at archive), `CHANGELOG.md`.
- `make check` stops failing at random on this test, which the closing task of c0025 needs.
- No public API changes.
