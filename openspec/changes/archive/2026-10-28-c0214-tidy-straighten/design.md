## Context

c0208 built `fenolite tidy` with prune and right-angle chamfers (`src/fenolite/tidy/`, `cli/cmd_tidy.py`):
pieces per net shaped as the copper check shapes them (`tidy.graph`), the groups test
(`graph.keeps_groups`), and a copper check passed in by the caller (`edits.Check`), with an undo loop. The
package may import `model`, `geometry` and `backends.base` only. c0175's decision 5 plans straighten,
T-joint and zone chamfers and a style report on top. This change takes those (tasks 7.2 to 7.5) and leaves
the routing plugin `octilinear` (task 7.6) in c0175.

## Decisions

1. **A run is a chain between fixed points.** Per net and layer, a point where exactly two movable tracks
   (unlocked, not kept, of one width, not of zero length) end and nothing else of the net touches the
   disc of the width is an inner joint. A run is a maximal chain of two or more tracks through inner
   joints; its ends are the fixed points (pads, vias, joints of three or more, locked or kept items, arcs,
   free ends). A closed chain has no ends and stays. A run whose tracks touch another item of the net
   elsewhere than at its two end discs stays too, since a new shape would drop that contact.
2. **Shapes, not a grid search.** Between the ends P and Q a fixed list of shapes on the 0/45/90°
   lattice is tried: the straight segment when P and Q are aligned or on a diagonal; diagonal then
   straight; straight then diagonal; straight, diagonal, straight with the diagonal at 1/2, 1/4 and 3/4
   of the straight part; the two L shapes; and the two L shapes with a 45° cut of half the shorter side.
   Every point is an integer, so every angle is exact. A grid search would find more, but costs a copper
   check per cell; the octilinear plugin will own such a search. Three segments serve a staircase between
   two fixed points, which is the router's usual leftover.
3. **Turn costs.** A turn weighs 1 at 45° and 3 at 90°, so two 45° turns beat one right angle; an acute
   turn is forbidden in a new shape and weighs 4 in the run as found, a turn below 90° at another angle 2. A turn whose point lies in a pad
   that the run ends on weighs nothing. The joints of the shape with other tracks ending at P or Q count
   as turns, so a run is never bent into an acute joint with its neighbour; a track that passes through P
   or Q counts as the lighter of its two ways, so a 45° entry of a T-joint is not redrawn into a right
   angle on the bar by the next run. A shape is tried only when it
   weighs less than the run; the lightest is tried first, then the shortest, then by list order.
4. **Each shape is judged as a chamfer is.** A shape must touch, of its net, only what the end discs
   touched, keep the net's groups, and add no finding of `check` on the whole design with the earlier
   runs applied. The first shape that passes replaces the run; when none passes the run stays, silently:
   a run that cannot improve is not a problem. The shape's segments reuse the run's track ids in order
   (`replaced`), drop the rest (`removed`) and derive ids for extra segments (`added`).
5. **Order and protection.** Runs go by net name, layer and smallest track id, each against the copper
   of the runs before it, so the result does not depend on file order. A net of a differential pair (an
   interface of a pair kind, or the KiCad name rule of `model.pairs`) or one that a rule of kind `length`,
   `skew` or `diff_pair_skew` selects keeps its length or its coupling only if untouched:
   `tidy.straighten-skipped` names it.
6. **T-joints.** A stem (a horizontal or vertical movable track) ending at J at 90° on a bar of its net,
   layer and width (the interior of one track, or the joint of two collinear tracks), with nothing else
   there, becomes a 45° entry: the stem's end moves back by the leg and a 45° track joins it to the bar at
   the leg's distance from J, on the side with more bar. The leg is `leg` or twice the width, at most half
   of the stem and half of that bar side; the bar is not changed. Entries share the corners' checks,
   undo loop and `tidy.chamfer-undone`, through a common `Joint` shape (`cuts`, `diagonal`, `items`).
7. **Zone corners.** With `zones=True`, each convex corner of an unlocked zone's outline of a selected net
   whose two edges are horizontal and vertical is cut by a 45° edge, legs `leg` or 1 mm, at most half of
   each edge. A reflex corner would add copper and stays. Every pad, via, track and arc of the net that
   touched the outline on a zone layer must still touch it, corner by corner and then all together, or
   the corner (then the zone) stays with `tidy.chamfer-undone`. A cut zone loses its fill (`fills`
   emptied, `filled` false): the stored fill no longer matches; `tidy.fill-stale` asks for `fill`. The
   edit's layer is `null`, as a via's.
8. **The style report counts the model.** `tidy.style` reads the design only: per net class (the net's
   class, else `Default`) and copper layer, joints of two track ends at a point by the interior angle (45°
   turn, 90°, acute below 90°, other; straight joints are not counted); at three or more ends each acute
   pair counts. A jog is a track shorter than three widths whose two ends are turning joints. Widths
   carry their total length (tracks and arcs, floor of the exact length). Vias count per class. Each acute
   joint is a `tidy.acute` warning at its point. Evidence `INFERRED`, `H-G-TIDY-STYLE`.
9. **The CLI.** `--straighten` runs between prune and chamfer; all three run when no step is named.
   `--zones` needs the chamfer step. `--report` runs no step and plans nothing; `--compare REFERENCE`
   (implies `--report`) reads a second KiCad board. The report uses the classes of the project beside
   each board (`design_rules`). A step run gives `result.style` with the counts before and after. Four
   new options cost four lines of the generated `commands` page, which has a 600-line budget.
10. **Spec order.** `Tidy command` and `Tidy codes` are MODIFIED blocks of the capability that c0208
    creates, so c0208 is archived first.

## Risks / Trade-offs

- A copper check runs per tried shape: at most ten per run. Runs are few on the boards Fenolite routes; a
  board with thousands of staircases is slow, and `--nets` narrows it.
- Straightening an L between two pads replaces it by a 45° shape, which moves more copper than a chamfer.
  The groups and the copper check judge it as any edit; `--chamfer` alone keeps the old behaviour.
- A zone cut drops a fill that `fill` must redo; nothing is lost that a fill does not give back.

## Open Questions

None.
