# Tasks: c0486-placement-netted-polygon-attachment

Rules for every task:

- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages. Test boards are authored for Fenolite.
- Run each touched test file alone with `-n 0`.

- [x] 1.1 Project the graphic nets in `place_optimize.propose` before `inspect_attachments`, and read a
  netted copper graphic as a piece of its net in `placement_protection.inspect_attachments`, with unit
  tests for the three scenarios of "Netted copper graphics in the attachment check".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/placement/test_optimization_protection.py -q -n 0`
- [x] 1.2 Run the optimize command on an authored board with a netted `gr_poly` (scenario "A GND polygon
  away from the part") end to end.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_optimization_proposal.py -q -n 0`
- [x] 2.1 State the direction of Y in the help of `--move` and `--region` (`cli/cmd_place.py`) and in
  `agent/skill/references/placement.md`; regenerate the command pages with
  `uv run python tools/gen_agent_guide.py`; add the test of "A larger Y moves the part down" and of the help.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_place_cmd.py tests/unit/agent/test_pages.py -q -n 0`
- [x] 2.2 Check the generated guide is current.
  - Proof: `uv run python tools/gen_agent_guide.py --check`
- [x] 3.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [x] 3.2 Maintainer board (private, codes and counts only): on the KiCad copy converted from the Altium
  board, `place --strategy optimize` with a scope of free passives reports no `attachment_unchecked` part
  caused by a netted copper polygon, and returns at least one candidate or a reason other than
  `attachment_unchecked`.
  - maintainer runs (private board).
  Result (maintainer board, 2026-11-16): 0 `attachment_unchecked`; 12 of 12 scoped passives `attached_copper`.

## Decisions

- Decision (maintainer, 2026-11-16): `propose` projects the graphic nets only for the attachment
  inspection (`inspect_attachments(graphicnets.with_graphic_nets(design), …)`); the design it checks,
  transforms and writes keeps its graphics as read, so a write gives the same bytes as before.
- Decision (maintainer, 2026-11-16): an unfilled closed graphic (`polygon`, `rect`, `circle`) is copper
  only on its stroke; a filled one covers its interior and stroke as one `Thick`. A `line` or `arc` is its
  stroke. Any other shape (wrong point count) raises and keeps the parts unchecked.
- Decision (maintainer, 2026-11-16): the `placement` page sits at its 12,000-byte limit, so the direction
  of Y is two sentences after `--move` rather than a separate bullet.
