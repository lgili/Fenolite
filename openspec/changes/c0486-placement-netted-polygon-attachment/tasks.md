# Tasks: c0486-placement-netted-polygon-attachment

Rules for every task:

- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages. Test boards are authored for Fenolite.
- Run each touched test file alone with `-n 0`.

- [ ] 1.1 Project the graphic nets in `place_optimize.propose` before `inspect_attachments`, and read a
  netted copper graphic as a piece of its net in `placement_protection.inspect_attachments`, with unit
  tests for the three scenarios of "Netted copper graphics in the attachment check".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/placement/test_optimization_protection.py -q -n 0`
- [ ] 1.2 Run the optimize command on an authored board with a netted `gr_poly` (scenario "A GND polygon
  away from the part") end to end.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_place_optimization_proposal.py -q -n 0`
- [ ] 2.1 State the direction of Y in the help of `--move` and `--region` (`cli/cmd_place.py`) and in
  `agent/skill/references/placement.md`; regenerate the command pages with
  `uv run python tools/gen_agent_guide.py`; add the test of "A larger Y moves the part down" and of the help.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_place_cmd.py tests/unit/agent/test_pages.py -q -n 0`
- [ ] 2.2 Check the generated guide is current.
  - Proof: `uv run python tools/gen_agent_guide.py --check`
- [ ] 3.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 3.2 Maintainer board (private, codes and counts only): on the KiCad copy converted from the Altium
  board, `place --strategy optimize` with a scope of free passives reports no `attachment_unchecked` part
  caused by a netted copper polygon, and returns at least one candidate or a reason other than
  `attachment_unchecked`.
