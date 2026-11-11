# Tasks: c0494-altium-silk-segment-written

Rules for every task:

- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test documents are authored for Fenolite and written by Fenolite's own
  writer.
- Run each touched test file alone with `-n 0`.

- [ ] 1.1 Reproduce: write the authored document of design D2, build it back through Fenolite, and compare
  the overlay tracks and arcs per footprint, source against written (design D1). Record which of H1, H2 and
  H3 holds in the test's docstring. If nothing differs, add a footprint shape until the defect shows, or
  record that the authored data does not reproduce it and stop for review.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_overlay_round_trip_c0494.py -q -n 0`
- [ ] 1.2 Fix the step that adds the stroke (design D3); test for "An open outline on both sides".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_overlay_round_trip_c0494.py tests/unit/backends/altium/test_pcb_graphics.py -q -n 0`
- [ ] 1.3 Run the comparison on the public rows (scenario "Public rows").
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_overlay_round_trip_c0494.py -q -n 0 -k public`
- [ ] 2.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 2.2 Maintainer board (private, codes only): after the build, the overlay comparison reports no added
  primitive, and Altium's DRC no longer reports the text against an added segment.
