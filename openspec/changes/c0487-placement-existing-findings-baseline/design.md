# Design: c0487

## D1 One baseline per proposal

`propose` runs `check_placement_constraints` once on the design it read, with the same frame, constraints
and rules as `judge`. The baseline is the set of its hard strings (`legality.hard` and the intrinsic
findings) plus a measure per string (D2). It is part of the proposal fingerprint input, so a stale review
still fails.

`judge` splits a candidate's hard strings in two:

- `hard`: strings the baseline lacks, and baseline strings that the candidate makes worse;
- `baseline`: the rest. They do not reject the candidate and are listed in its per-rule outcomes.

The active set of `judge` (fixed parts plus posed parts) is a subset of the board, so a baseline string
about a part outside the active set never shows up in a candidate.

## D2 The measure of "worse"

Each finding gets one integer measure, computed on the board before and on the candidate. A finding is
worse when the measure moves the wrong way. Equal is not worse.

| Finding | Measure | Worse when |
|---|---|---|
| `place.courtyard-overlap`, `gap:A:B:face` with intersecting courtyards | area of the intersection of the two courtyards on that face, nm², from the exact boolean backend (`geometry.boolean.select_backend`) | it grows |
| `gap:A:B:face` without intersection | the smallest distance between the two courtyards, nm | it shrinks |
| `copper:<code>:<where>` with a `gap` | the finding's `gap`, nm | it shrinks |
| any other string | none | it names a moved part |

A finding whose measure cannot be computed (a boolean backend error, an open courtyard) is judged as new.
That keeps the check conservative.

## D3 The same rule in `place --move`

`cmd_place._existing` keeps its key (code, `where`, message). A finding that names a moved part is
`place.existing` when it is a `place.courtyard-overlap` and its area did not grow (D2). The extents come
from the same `placed_extents` calls that the legality check already makes, before and after the move.

## D4 Report

A baseline finding keeps its code, `where` and message. The optimizer report gives it under the
candidate's outcomes as `baseline`. `place --move` keeps the `place.existing` warning and its hint.

## Decisions

- Decision (maintainer, 2026-11-16): the D2 measure is one integer that grows as it gets worse:
  twice the intersection area in nm² when the courtyards intersect, else minus their smallest distance in nm
  (`placement.constrained_legality.overlap_measure`). An overlap that becomes disjoint therefore always
  counts as better, and one comparison (`after > before` is worse) covers both rows of the table. A copper
  finding's measure is minus its smallest `gap` among findings with the same key.
- Decision (maintainer, 2026-11-16): the intersection prefers the `clipper` backend (any ring shape) and
  falls back to the stdlib convex backend; `select_backend()` alone would pick the convex fallback first
  and fail on every non-convex courtyard. A missing face, an invalid ring or no backend gives `None`
  (judged as new).
- Decision (maintainer, 2026-11-16): `place.courtyard-overlap` measures both faces summed (it is judged on
  both); `gap:A:B:face` measures its face only.
- Decision (maintainer, 2026-11-16): "a moved part" in the optimizer is a posed part whose position,
  rotation or side differs from the board; a pose equal to the board's does not move it.
- Decision (maintainer, 2026-11-16): a candidate lists its baseline findings in a new optional field
  `OptimizationCandidate.baseline`, as the same `code:where` keys as hard findings and blockers (code and
  location); the details (message, measures) are those of the board's own check. The v0 schemas are
  regenerated and their frozen hashes recorded again, an additive optional field.
- Decision (maintainer, 2026-11-16): the baseline measures, not only the keys, enter the proposal
  fingerprint (D1), so a review after an old overlap changed gives `FEN-4002`.
- Decision (maintainer, 2026-11-16): `place --move` keeps the c0432 rule for every other finding that
  names a moved part (it is judged); only `place.courtyard-overlap` gets the area rule, as D3 says.
