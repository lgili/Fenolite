# Tasks: c0487-placement-existing-findings-baseline

Rules for every task:

- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages. Test boards are authored for Fenolite.
- Run each touched test file alone with `-n 0`.

- [x] 1.1 Add the overlap measure of design D2 (intersection area, else distance) as a helper in
  `src/fenolite/placement/`, with unit tests for touching, nested, disjoint and failing courtyards.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/placement/test_constrained_legality.py -q -n 0`
- [x] 1.2 Compute the baseline once in `place_optimize.propose`, split each candidate's findings into hard
  and baseline in `judge`, and list the baseline findings in the candidate report; tests for the three
  scenarios of "Pre-existing findings are a baseline".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_optimization_proposal.py -q -n 0`
- [x] 1.3 Check that a stale review of a proposal with baseline findings still gives `FEN-4002`.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_optimization_plan.py -q -n 0`
- [x] 2.1 Keep a pre-existing overlap of a moved part as `place.existing` while its area does not grow
  (`cmd_place._existing`); change `test_a_finding_on_a_moved_part_is_judged` to move the part deeper into
  the overlap, and add the scenario "A moved part leaves an old overlap smaller".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_c0432.py -q -n 0`
- [x] 2.2 Update the text of `place.existing` in `cli/data/explain.toml` and the guide page `placement.md`.
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py tests/unit/placement/test_place_codes.py -q -n 0`
- [x] 3.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [x] 3.2 Maintainer board (private, codes and counts only): `place --strategy optimize` on the KiCad copy,
  whose board has findings before any move, returns at least one candidate, and each candidate
  lists the findings of the board before as baseline.
  - Maintainer runs (private board).
  Result (maintainer board, 2026-11-16): 4 candidates, each with 126 baseline findings; needs 1000 evaluations for one movable part (about 35 min), 0 candidates at 64: follow-up on speed.

Decision (maintainer, 2026-11-16): the decisions of this change are listed under "Decisions" in
`design.md`. The guide page `placement.md` has a 12000-byte budget, so its new line is one sentence; the
optimizer's `baseline` field is described in the CHANGELOG and the result schema.

Decision (maintainer, 2026-11-17): profiled on the maintainer's board (cProfile, 64 evaluations), one
evaluation runs the whole-board placement check: `check_geometry` took about 60% of it, most of that in the
keep-out and drill loops that built every pad's copper shape again for each keep-out and each drill, and the
copper check the rest. The search found nothing at a small budget because `beam_search` sorted each domain by
position, so it judged the poses at the board's lower-left first and the current pose (the sampler's first)
late. Now each pad's shapes are built once per check with a box test before the exact one (same verdicts),
and the domain is judged in the sampler's order; the beam keeps the least states by score and poses in any
order, so a search that completes gives the same result. Tests `test_the_domain_order_is_the_order_of_evaluation`
and the existing legality tests. Not done: an incremental copper check of the moved parts only.

Result (maintainer board, 2026-11-17): the placement check of the board gives the same hard and missing
strings before and after (same digest), in 1.27 s instead of 2.13 s. `place --strategy optimize`, 59
selected, 1 movable, budget 64: 2 candidates (was 0), each with 126 baseline findings, in 104 s (was 144 s;
the 1000-evaluation run that found the first candidates took about 35 min).

- [x] 3.3 Judge each optimizer candidate incrementally: the fixed parts are checked once, each candidate only
  near its placed parts (`MovedPartsCheck` in `cli/placement_checks.py`), with the same verdicts as the
  whole-board check; a baseline courtyard pair with no moved part keeps its measure.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_moved_parts.py -q -n 0`

Decision (maintainer, 2026-11-17): the incremental check reuses the whole-board check instead of splitting
the copper, geometry and mechanical checks by item. The board is cut to the placed footprints plus the fixed
footprints, tracks and vias whose boxes (pad copper, drills, extents, rule areas, bodies) lie within the
largest clearance, hole clearance or gap of them; zones, arcs, graphics, rule areas, holes and the outline
stay whole. The verdicts are those of the fixed parts plus what the cut board with the placed parts adds to
the cut board without them, as multisets. When the placed parts take a verdict away (a duplicate-drill
group grows, a reservation finds its drill) or a placed footprint holds a rule area (its area changes the
rules of the copper in it, beyond the cut), the whole board is checked: exact, never faster than before. The
copper issues and summary of an incremental check are left empty: the optimizer reads only the hard and
missing strings and the copper and mechanical findings. `_measures` measures only the courtyard pairs with
a moved part and reads the extents of those parts only; the other pairs keep the measure of the board
before. Tests `test_moved_parts_check_equals_the_whole_board_check` (random moves with rotation, side and
poses on edges, cut-outs, rule areas, holes, drills and courtyards; the rule-area fallback),
`test_a_part_on_another_parts_drills_gives_the_whole_board_verdicts` and
`test_the_optimizer_judges_only_the_parts_near_the_moved_one` (fails without the change: every evaluation
then checks all 30 parts).

Result (maintainer board, 2026-11-17): one evaluation took 1.68 s (1.54 s of whole-board check) and now
0.17 s (0.13 s of incremental check); the 64 incremental verdicts equal the whole-board ones. `place
--strategy optimize`, 59 selected, 1 movable, budget 64, dry run: same result as before, byte for byte (2
candidates with the same ids, scores and 126 baseline findings each, same input digest and blockers), in
18.6 s instead of 104 s.

- [x] 3.4 Prove the incremental check on a board read from an Altium PCB document: the same verdicts as the
  whole-board check for free pads, derived courtyards, bodies, a component's keep-out, a room, a polygon, a
  copper region and Altium's keep-out clearance.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_moved_parts.py -q -n 0`

Decision (maintainer, 2026-11-18): no change to the cut. What a finding about one part reads in an Altium
reading lies in that part or stays whole on the cut board: a free pad is a board-only footprint (its pad
and hull are in its box) or a board hole (kept whole); a component's keep-outs are rule areas of its
footprint (in its box; a moved part with one falls back to the whole board); a room is a board rule area
that restricts nothing (kept whole); polygons, copper regions and fills are zones and board graphics (kept
whole); the derived courtyard (c0489) and the extruded bodies of a footprint are its own and in its box;
component primitives are footprint graphics, which the placement check does not read; the keep-out
clearance (c0498) is a `clearance` rule, so the reach includes it; the placement check judges no copper
against the board edge, and the outline is fixed before the search. Tests on `authored` written as a PCB
document by the Altium writer and read back by the Altium import:
`test_moved_parts_check_equals_the_whole_board_check_on_an_altium_reading` (random moves with rotation,
side and poses near keep-outs, the room, free pads, the polygon, the region and the board edge),
`test_an_altium_part_near_a_free_pad_or_a_components_keepout_gives_the_whole_board_verdicts` and
`test_the_altium_optimizer_evaluations_match_the_whole_board` (`propose_altium`, every evaluation compared).
Each deliberately broken cut, then reverted, fails at least one of them: reach without the clearances,
footprint keep-outs left out of the boxes, extents and bodies left out, free pads never near, and no
fallback for a moved part with a keep-out. Seen while testing, not in this change: the keep-out clearance
also judges copper near a room, which restricts nothing.

Result (maintainer board, Altium PCB document, 2026-11-18): `place --optimize` dry run, 59 selected,
budget 64, each evaluation also checked on the whole board: 64 of 64 verdicts equal, all 64 judged on a cut
board; 0.14 s per evaluation (0.67 s at most) against 1.29 s for the whole-board check (1.99 s at most). The
12-part scope request has no movable part on that document (all fixed by attached copper).
