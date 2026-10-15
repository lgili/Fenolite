## Context

- **Request.** Part E of the maintainer's request "board slots and cut-outs, end to end" (2026-10-15). Depends on c0167 (`OutlineSlot`, `model.outline.outline_items`, `geometry.rings.merge_rings`, the shared fixture). Uses c0168's cut-out regions for Altium input when it is archived; works without it.
- **What exists** (`origin/dev` at `a87723c`, read on 2026-10-15). Each item checks a claim of the request; corrections are marked.
  - Copper check. `checks/copper.py` turns tracks, arcs, vias, pads and fills into thick shapes and judges pairs of different nets for shorts and clearance (`checks/copper.py:1-16`, `_Items` at `:238-377`); `CopperKind` is track, arc, via, pad, fill, zone, keepout (`checks/clearance.py:27`). The codes are `copper.short`, `copper.clearance`, `copper.zone-overlap`, `copper.keepout`, `copper.rules-incomplete`, `copper.item-unsupported`, `copper.clearance-unset` (`checks/codes.py:67-73`). *The request is right*: there is no copper-to-edge, cut-out or slot clearance.
  - The rule kind exists. `edge_clearance` is a `RuleKind` (`model/rules.py:25`), a DSL constraint (`dsl/design.py:97, 360`), written to KiCad as `edge_clearance` (`backends/kicad/rulemap.py:32, 64, 110, 164`) and to Altium as `BoardOutlineClearance` (`backends/altium/rulemap.py:121`). It is read today by the placement guard (`placement/legality.py:80-90`, courtyards against the outline), by `route` (`cli/cmd_route.py:230-300`, the project's `min_copper_edge_clearance` as a rule for the router) and by stitching (`backends/kicad/copper.py:886-897`, `edge_clearance_in_force`: the last board-wide rule in `rule_order`, else the project's minimum).
  - Holes. No check of Fenolite judges a drilled hole: the kinds `hole_to_hole` and `hole_clearance` are lowered (`backends/kicad/rulemap.py`, `backends/altium/rulemap.py`) and judged only by KiCad's DRC (`backends/kicad/drc.py:54-70`, which records that 9.0.9 gives no `hole_clearance` between a pad and an unplated hole). *Correction:* the request's "slot-to-hole clearance where hole checks apply" has no Fenolite check to extend.
  - Frame. `BoardFrame` gives `board_pads` and `placed_extents` (`backends/base.py:792-800`), implemented by `backends/kicad/backend.py:141` and `backends/altium/backend.py:417`; `checks` may import `model`, `geometry` and `backends.base` only (`tests/unit/test_import_graph.py:40`), so it cannot call `board_outline`.
  - Creepage. *The request is right* that analyses use `Outline.cutouts` and `--groove-width` (`analysis/boundary.py:138-162`, `analysis/grooves.py`); c0167 adds slots to `board_boundary`.
- **Measured on 2026-10-15** in the pinned images `kicad/kicad:10.0.6` and `kicad/kicad:9.0.9` (scratch script, not committed; task 1.2 makes them probes). A 60 × 30 mm board built by `build_design` with a milled slot 2 mm wide (`cutout(shape.slot(…))`, its lower edge at y = 11 mm) and plated hole parts with 2 mm copper whose copper edge lies 0.47, 0.52, 0.548, 0.552 and 0.6 mm from the slot's edge; project without a rule. `pcb drc` gives one `copper_edge_clearance`, "board setup constraints edge clearance 0.5000 mm; actual 0.4700 mm", on both majors: the distance is to the edge line, and the 0.1 mm stroke of the edge (`OUTLINE_WIDTH`) does not count. The second board of c0167's measurement 5 gives `hole_clearance` for copper 0.2 mm from an oval NPTH pad on 10.0.6 and nothing on 9.0.9.

## Goals / Non-Goals

**Goals**
- `fenolite check` and the build's copper guard find copper too close to the board edge, a cut-out or a slot, with the same items as KiCad's DRC.
- A drilled hole that breaks into a milled cut-out, and two drilled holes that overlap, are found.
- A slot and its equal cut-out give one creepage.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Board edges reach the check through the frame.** `BoardFrame.board_edges(design, *, issues=None) -> tuple[EdgeRing, ...] | None`, `EdgeRing(name, points, mids)`: lines and exact arcs. KiCad: from `Board.outline` through `outline_items` and `merge_rings` (names `board`, `cut-out <k>`, `slot <name>`), else from `edge_outline` of the read board (`board`, `edge ring <k>`). Altium: the `Edge.Cuts` graphics of the import (outline and, with c0168, cut-out regions), the same way. `None` when no ring closes; the check then gives `copper.item-unsupported` for the edge with the reason.
   - Rejected: the check reading `Board.outline` itself. A read board has none, and that is the common case of `check`.

2. **Edge clearance in force.** `ClearanceResolver.edge(subject) -> Clearance`: the governing `edge_clearance` rule whose selector matches the copper item (the last in `rule_order`, as for `clearance`), else the board minimum, `DesignRules.min_edge_clearance` (KiCad: `min_copper_edge_clearance` of the project; Altium: the board-wide `BoardOutlineClearance`). Whether a rule below the board minimum lowers it is measured on both majors (`H-K-EDGE-RESOLVE`), and a switch `edge_floor_over_rules` of `DesignRules` holds the answer per major, as `floor_over_rules` does for clearance. For board-wide rules the result equals `edge_clearance_in_force` (stitching), which then calls the resolver.

3. **The judged pair and the distance.** Each copper shape (as for clearance: a track's or arc's core widened by half its width, a via's disc on each layer, a pad's board-frame entries, a fill) is judged against each edge ring as a closed polyline of width 0, arcs polygonised at `ARC_TOL_NM` with the band `ARC_TOL_NM + 1` (as copper arcs are). The gap is to the edge line; the edge's stroke does not count (measured). A gap below the limit gives `copper.edge-clearance` with the rule's severity. Copper wholly outside the board ring or inside a cut-out is judged the same way; KiCad reports only what is near an edge (`H-K-OUTLINE-OUTSIDE`).
   - Rejected: the board area as a polygon minus cut-outs, tested by containment. A distance to a polyline needs no boolean and gives the gap for the message.

4. **The finding.** `copper.edge-clearance` (error or warning by the governing rule; info is not used), message "<item> is <gap> from the board edge (<ring>); edge clearance <limit> (<source>)", `where` the item's locator and the ring's name, the closest point as its location. Its explanation is an `EdgeClearanceExplanation` with the candidate rows of Decision 2 (rule rows: id, priority, selector, layers, value, severity; the board minimum row), built from the resolver's candidates as `ClearanceExplanation` is, and grouped by `group_findings` with the relation `edge`. A finding counts once per item and ring.

5. **Drilled holes.** A drilled hole is a pad's drill (round or slot), a via's drill and a board `Hole` (with c0168's slot). `copper.hole-in-cutout` (error): its area overlaps a cut-out's or slot's area or crosses the board ring; a hole wall broken by a milled slot cannot be made. `copper.hole-overlap` (warning): two drilled holes whose areas overlap, other than two copies of one hole; KiCad says nothing about overlapping oval NPTH pads (c0167, measurement 4), Altium's Hole To Hole Clearance flags them (S-0460). No limit is applied; `hole_to_hole` and `hole_clearance` stay KiCad's DRC's.
   - Rejected: judging `hole_to_hole` values here: KiCad already does at `check`, with its own rounding.

6. **Creepage equality.** No new code: c0167 gives a slot and `cutout(shape.stadium(…))` the same ring from `core.stadium`, and `board_boundary` merges an L. This change adds the tests and the documentation, and the groove rule (`analysis/grooves.py`) bridges a slot narrower than `--groove-width` by its width, as it does any cut-out.

7. **Where it runs.** In `check_copper`, so in the `copper.clearance` stage and in the build's copper guard (`design-dsl`, "Copper guard before writing") with their severities. The examples and committed boards are run before merge (task 3.3); an example whose copper is too close to its edge is moved, never waived.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/base.py` | `EdgeRing`; `BoardFrame.board_edges`; `DesignRules.min_edge_clearance`, `edge_floor_over_rules` |
| `src/fenolite/backends/kicad/backend.py`, `frame.py`, `copper.py` | `board_edges`; the edge minimum and switch; `edge_clearance_in_force` through the resolver |
| `src/fenolite/backends/altium/backend.py`, `frame.py` | `board_edges`; `BoardOutlineClearance` as the board minimum |
| `src/fenolite/checks/clearance.py` | `ClearanceResolver.edge`, `EdgeClearanceExplanation` |
| `src/fenolite/checks/copper.py`, `checks/codes.py` | the edge pair, the two hole findings, three codes |
| `src/fenolite/cli/data/explain.toml`, agent guide `recovery` | three entries |
| tests | `tests/unit/checks/test_copper_edges.py`, `test_copper_holes.py`, `tests/unit/analysis/test_creepage_slots.py`, `tests/kicad/checks/_edgebench.py`, `test_edge_clearance.py` |
| docs | `docs/copper-rule-explanations.md`, `docs/cli-contract.md`, `docs/analyses.md` ("Creepage", "Grooves"), `docs/formats/kicad/drc.md` |

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-EDGE-CENTRE | `copper_edge_clearance` measures copper to the `Edge.Cuts` line, not counting its stroke, on 9.0.9 and 10.0.6; the board setup's default is 0.5 mm (S-0020, S-0029) | `tests/kicad/checks/test_edge_clearance.py -k centre` | `edge-centre-047` `present`, `edge-centre-052` `absent` on both majors |
| H-K-EDGE-RESOLVE | How an `edge_clearance` custom rule and `min_copper_edge_clearance` combine (a rule below and above the minimum), per major | `-k resolve` | the four probes `edge-resolve-*` recorded on both majors |
| H-K-EDGE-AGREE | On the bench of task 3.2 (tracks, arcs, vias, pads, a fill; outer ring, a round cut-out, a slot, the merged L), Fenolite's `copper.edge-clearance` items equal KiCad's `copper_edge_clearance` items | `-k agree` | equal sets on both majors |

All start `INFERRED`; `H-K-EDGE-CENTRE` carries the measurement of 2026-10-15 as its first record.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| edge distance and limit | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-EDGE-CENTRE`, `H-K-EDGE-RESOLVE` |
| items found | KICAD-VERIFIED on the bench; the check's `EVIDENCE` stays `INFERRED` | `H-K-EDGE-AGREE` |
| hole findings, creepage equality, explanations | mechanical | unit tests |

## Risks / Trade-offs

- **New findings on existing boards.** Copper near an edge was never reported by Fenolite; `check` and the guard now report it, as KiCad's DRC always did. The changelog says so.
- **Arc band.** Copper within 1 µm of a curved edge may be judged unlike KiCad; the band is stated in the finding as for copper arcs.
- **Altium input before c0168** has no cut-out edges; the check then judges the outer ring only, and `copper.item-unsupported` names the regions it could not read.

## Migration Plan

- `DesignRules` gains two fields with defaults; `BoardFrame` gains a method, implemented by both backends; a third-party frame without it is detected and the edge pair skipped with `copper.rules-incomplete`.

## Budget (5 days)

| part | days |
|---|---|
| probes: centre, resolve; register | 0.75 |
| frame edges (KiCad, Altium) | 0.75 |
| resolver, explanation, the edge pair, the finding | 1.25 |
| hole findings | 0.5 |
| bench and agreement with KiCad | 0.75 |
| creepage tests, docs, closing | 1.0 |

Cut order: (1) `copper.hole-overlap`; (2) `EdgeClearanceExplanation` grouping beyond the rows; never cut: the edge finding with KiCad's agreement and `copper.hole-in-cutout`.

## Open questions

1. **Should edge findings stop a build through the copper guard?** Recommended: yes, with the rule's severity, as clearance findings do; the examples are fixed first. Decided by the maintainer on 2026-10-15: yes, with the rule's severity, as clearance findings do; the examples are fixed first.
2. **Should copper wholly outside the board be a finding of its own?** Recommended: no; c0102 drops it on outline changes and KiCad reports nothing for it. Decided by the maintainer on 2026-10-15: no.
3. **Should Fenolite judge `hole_to_hole` and `hole_clearance` values?** Recommended: not in this change; a follow-up when an Altium-only flow needs them without KiCad. Decided by the maintainer on 2026-10-15: not in this change; a follow-up when an Altium-only flow needs them.
4. **Is `copper.hole-overlap` a warning or an error?** Recommended: warning; two overlapping drilled holes can be intended (a drilled slot made of two holes), and Altium's rule decides on its side. Decided by the maintainer on 2026-10-15: warning.
