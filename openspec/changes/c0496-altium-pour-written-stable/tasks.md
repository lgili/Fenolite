# Tasks: c0496-altium-pour-written-stable

Rules for every task:

- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test documents are authored for Fenolite and written by Fenolite's own
  writer.
- Run each touched test file alone with `-n 0`.

- [ ] 1.1 Reproduce: write the authored document of design D3 with and without the remote polygon, through
  the carrier and through the computed pour, and diff the region records of the unrelated polygons. Record
  the causes of design D2 that hold in the test's docstring.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_stable_c0496.py -q -n 0`
- [ ] 1.2 Make `_carried_pour_records` per polygon and let the pour loop compute only the rest (design D1);
  test for "A zone added in KiCad".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_stable_c0496.py tests/unit/convert/test_altium_kept_pour_c0482.py -q -n 0`
- [ ] 1.3 Fix each cause of design D2 so the computed pour reads only its inputs, drop zero-length edges and
  segments, and add `altium.pour-changed`; tests for "A remote zone added" and "An overlapping zone added".
  Register `H-A-POUR-LOCAL` in `docs/formats/altium/pcb-pour.md`.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_stable_c0496.py tests/unit/backends/altium/test_pour_engine.py tests/unit/backends/altium/test_pour_regions.py -q -n 0`
- [ ] 1.4 Teach `altium.pour-changed` on the agent guide page that lists Altium codes.
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 1.5 Run the pour census on the public rows: the counts of poured and refused polygons stay the same, or
  each change is explained.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_compare.py tests/unit/backends/altium/test_pour_refusal.py -q -n 0`
- [ ] 2.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 2.2 Maintainer board (private, codes only): with a remote zone added, the pours of the other nets
  are written byte-identical, apart from the index, and Altium's dead-copper analysis finds no new island.
