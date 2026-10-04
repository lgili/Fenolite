## 1. Test

- [x] 1.1 In `tests/unit/geometry/test_transform.py`, make `test_composition_rounds_once` assert the per-axis bound `(1 + |cos θa| + |sin θa|) / 2` nm for `a.apply(b.apply(p))` with exact rationals and `(|cos θa| + |sin θa|)² ≤ 2` in integers, and add the `@example` `rotation(315°)`, `rotation(30°)`, `(0, 1_386_483)`. Add `test_two_applies_reach_the_bound` (the tie case equals the bound exactly and is above 1.2071067811865475 nm; the integer-translation case is above 1.206 nm and within the bound) and `test_diagonal_table_entries_stay_below_sqrt2`. Covers the three new scenarios. Proof: `uv run pytest tests/unit/geometry/test_transform.py -q`.

## 2. Documents

- [x] 2.1 In `docs/geometry.md`, section "Transform": state `(1 + |cos θ| + |sin θ|)/2`, at most `(1 + √2)/2 ≈ 1.2071` nm per axis, for `a.apply(b.apply(p))`, and give the reason the inverse round trip stays within 1 nm. Proof: `grep -n "1.2071" docs/geometry.md`; `grep -c "rounds twice: within 1 nm" docs/geometry.md` prints 0.

## 3. Closing

- [x] 3.1 Run the test file 20 times with different Hypothesis seeds, then the fast gate (which includes the residue scan). Proof: `for n in $(seq 1 20); do uv run pytest tests/unit/geometry/test_transform.py -q --hypothesis-seed=$n || break; done` ends with 20 passing runs; `make check-fast`.
- [x] 3.2 Evidence labels: confirm that no label moves and no source file changes. Proof: `git diff --stat origin/main -- src docs/hypotheses.md docs/evidence docs/formats` prints nothing.
- [x] 3.3 Add to `CHANGELOG.md` under `## [Unreleased]`, section "Fixed", one line about the corrected bound. Proof: `git diff origin/main -- CHANGELOG.md`; `openspec validate c0050-transform-composition-bound --strict`.
