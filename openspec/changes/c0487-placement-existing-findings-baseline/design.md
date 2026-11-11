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
