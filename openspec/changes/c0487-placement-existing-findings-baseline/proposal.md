# c0487: findings a board already has are a baseline for placement

## Why

The c0477 design says: "Retain unchanged baseline findings outside the affected scope and recheck them for
new or worsened effects", and its evaluation table asks that a candidate "introduce no new or worsened hard
finding". The code does not do this.

- The judge of `fenolite place --strategy optimize` (`cli.place_optimize.propose`, `judge`) puts every hard
  finding of `check_placement_constraints` into the candidate's `hard` list. A board that has a clearance or
  courtyard finding before any move therefore rejects every candidate, and the optimizer returns 0
  candidates. On the maintainer's board (private; codes and counts only) it returned 0 candidates for this
  reason.
- `fenolite place --move` (`cli.cmd_place._existing`, change c0432) reports a finding the board had before
  as `place.existing` only when its `where` names no moved part. As soon as one part of an overlapping pair
  moves, the old overlap is judged as new, even when the move makes it smaller.

## What Changes

- The optimizer checks the board before any move once, with the same checker and rules. A candidate's hard
  finding that the baseline has, and that the candidate does not make worse, is reported as a baseline
  finding and does not reject the candidate.
- "Worse" is defined per kind of finding:
  - a courtyard overlap or a `gap` finding between two parts: the area of the intersection of the two
    courtyards on that face grows, or, when they do not intersect, their distance shrinks;
  - a copper clearance finding: its measured gap shrinks;
  - any other finding: it names a moved part.
- `place --move` uses the same rule: a pre-existing overlap of a pair with a moved part stays
  `place.existing` while its overlap area does not grow.
- The report keeps each baseline finding with its details, so a person can still fix it.

## Impact

- `src/fenolite/cli/place_optimize.py` (`propose`, `judge`), `src/fenolite/cli/placement_checks.py`,
  `src/fenolite/cli/cmd_place.py` (`_existing`), a small shared helper for the overlap measure in
  `src/fenolite/placement/` (no checker import, as c0096 requires).
- `tests/unit/cli/test_place_c0432.py`: the test "a finding on a moved part is judged" moves the part
  deeper into the overlap.
- No change for a board without findings before the move.
