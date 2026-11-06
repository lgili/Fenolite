# Design: c0432 place on a converted board

## Baseline of the board before the moves

`cmd_place` keeps the design as read. After the moves it runs `legality.check` twice with the same
keep-outs: on the extents of the board before (parts on the board, as the check after leaves staged parts
out) and on the layout after. A finding after is existing when the set before holds the same
`(code, where, message)` and no reference of its `where` (split on commas) is a moved part. Existing
findings become one `place.existing` warning each, whose message names the code and repeats the finding.
`result.legality` keeps counting the findings of the layout after by their own codes, as before.

Matching by `(code, where, message)` is strict: a finding on a moved part, or one whose measure changed,
stays as it is. The copper check of the group and reuse strategies already compares before and after
(`fresh_clashes`).

## Locked parts

`move_footprint` keeps refusing a locked part without `force`. The hint changes only.

## Dragged copper

`place_group.dragged(design, pads, members, whole)` returns the vias and track ends to move. A via moves
when its piece touches a pad piece of a member and no pad piece of another part. A track end (a point
with the track's width, on its layer) moves when it touches the piece of a moved pad or a moved via. A
track with both ends dragged moves whole. Arcs move only whole (the exclusive groups); an arc end on a
moved pad stays and `place.copper-left` still says so. The dragged ids join `plan.copper`, so
`place.copper-left` names only parts with copper left.
