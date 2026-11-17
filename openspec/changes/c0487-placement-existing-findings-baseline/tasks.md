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

