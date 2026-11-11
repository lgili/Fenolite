# Tasks: c0495-cli-small-fixes

Rules for every task:

- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test data is authored for Fenolite.
- Each fix is its own task with its own proof. Run each touched test file alone with `-n 0`.

- [ ] 1.1 (a) Name an option by its flag and add `dest` in `cli/describe.py`; tests for the two scenarios
  of "An argument's name is its flag"; update "Discovery" in `docs/cli-contract.md` and regenerate the guide.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_describe.py tests/unit/cli/test_capabilities_cmd.py -q -n 0`
  - Proof: `uv run python tools/gen_agent_guide.py --check && uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 2.1 (b) Resolve a board through the registry in `cli/_boardview.load_board` (design D2); test for "An
  Altium PCB document" and for the error of an unread suffix (no absolute path).
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_net_cmd_c0495.py -q -n 0`
- [ ] 3.1 (c) Zone locations from the model in `checks/drc_json.item_locations`, the old-locator waiver
  match and `check.waiver-location-old` (design D3); test for "Isolated copper of a named zone".
  - Proof: `uv run --extra dev pytest tests/unit/checks/test_drc_json.py tests/unit/checks/test_waivers.py -q -n 0`
- [ ] 4.1 (d) Counts, reasons and examples in `LossyConversionError` and `convert.lossy` (design D4); test for
  "Drawings on layers KiCad lacks".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_lossy_message_c0495.py -q -n 0`
- [ ] 4.2 Teach `check.waiver-location-old` on the agent guide page that lists check codes.
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 5.1 Regenerate the schemas for `dest` and the issue details.
  - Proof: `uv run python tools/gen_schemas.py --check`
- [ ] 5.2 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
