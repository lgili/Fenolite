# Tasks: c0491-hole-clearance-same-net

Rules for every task:

- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test boards are authored for Fenolite.
- Run each touched test file alone with `-n 0`.

- [x] 1.1 Reproduce with a failing unit test (scenario "Copper of the net of an unplated pad"). Then
  record the net scope of the hole clearance: a `kicad-cli` oracle on authored boards (design D3) in
  `docs/formats/kicad/rules.md`, and the Altium page in `docs/formats/altium/pcb-copper.md`, both with
  `H-G-HOLE-SAME-NET`. Result: KiCad 10.0.6 reports the same-net pair, so the KiCad view keeps today's verdict
  (`DesignRules.hole_clearance_same_net`); 9.0.x not run. No same-net rule condition exists in the model.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/checks/test_copper_holes.py -q -n 0`
  - Proof: `uv run --extra dev pytest tests/kicad/checks/test_hole_clearance_same_net_c0491.py -q -n 0` (needs `kicad-cli`)
- [x] 1.2 Give an unplated pad's hole its pad's net in `_holes`, keep a same-net `hole_clearance` rule
  deciding, and add tests for the three scenarios of "Copper against drilled holes".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/checks/test_copper_holes.py tests/unit/cli/test_build_copper_guard.py -q -n 0`
- [x] 1.3 Run the copper stage and document-copper tests, whose counts may change only for same-net
  unplated holes; explain each changed count in the test.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/checks/test_copper_stage.py tests/unit/checks/test_document_copper.py -q -n 0`
- [x] 2.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 2.2 Maintainer board (private, codes only): `fenolite check` reports no `copper.hole-clearance`
  between an unplated pad and copper of its own net.
