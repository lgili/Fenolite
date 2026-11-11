# Tasks: c0487-placement-existing-findings-baseline

Rules for every task:

- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages. Test boards are authored for Fenolite.
- Run each touched test file alone with `-n 0`.

- [ ] 1.1 Add the overlap measure of design D2 (intersection area, else distance) as a helper in
  `src/fenolite/placement/`, with unit tests for touching, nested, disjoint and failing courtyards.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/placement/test_constrained_legality.py -q -n 0`
- [ ] 1.2 Compute the baseline once in `place_optimize.propose`, split each candidate's findings into hard
  and baseline in `judge`, and list the baseline findings in the candidate report; tests for the three
  scenarios of "Pre-existing findings are a baseline".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_optimization_proposal.py -q -n 0`
- [ ] 1.3 Check that a stale review of a proposal with baseline findings still gives `FEN-4002`.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_optimization_plan.py -q -n 0`
- [ ] 2.1 Keep a pre-existing overlap of a moved part as `place.existing` while its area does not grow
  (`cmd_place._existing`); change `test_a_finding_on_a_moved_part_is_judged` to move the part deeper into
  the overlap, and add the scenario "A moved part leaves an old overlap smaller".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_c0432.py -q -n 0`
- [ ] 2.2 Update the text of `place.existing` in `cli/data/explain.toml` and the guide page `placement.md`.
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py tests/unit/placement/test_place_codes.py -q -n 0`
- [ ] 3.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 3.2 Maintainer board (private, codes and counts only): `place --strategy optimize` on the KiCad copy,
  whose board has findings before any move, returns at least one candidate, and each candidate
  lists the findings of the board before as baseline.
