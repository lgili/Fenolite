# Tasks: c0496-altium-pour-written-stable

Rules for every task:

- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test documents are authored for Fenolite and written by Fenolite's own
  writer.
- Run each touched test file alone with `-n 0`.

- [x] 1.1 Reproduce: write the authored document of design D3 with and without the remote polygon, through
  the carrier and through the computed pour, and diff the region records of the unrelated polygons. Record
  the causes of design D2 that hold in the test's docstring.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_stable_c0496.py -q -n 0`
  - Done 2026-11-13: the computed pour of the three polygons is byte-identical with and without the remote
    polygon; the cause was D1 (all-or-nothing carry). One global input found and fixed: the arc tolerance
    of the objects and board area was the smallest of all polygons (now one context per tolerance).
- [x] 1.2 Make `_carried_pour_records` per polygon and let the pour loop compute only the rest (design D1);
  test for "A zone added in KiCad".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_stable_c0496.py tests/unit/convert/test_altium_kept_pour_c0482.py -q -n 0`
  - Note: "precedes" is read within reach: a new polygon far away that pours first does not make a carried
    polygon fall back (the scenario's remote zone may sort first); a computed polygon within reach that
    pours before it does. Decision (maintainer, 2026-11-13): accepted.
- [x] 1.3 Fix each cause of design D2 so the computed pour reads only its inputs, drop zero-length edges and
  segments, and add `altium.pour-changed`; tests for "A remote zone added" and "An overlapping zone added".
  Register `H-A-POUR-LOCAL` in `docs/formats/altium/pcb-pour.md`.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_stable_c0496.py tests/unit/backends/altium/test_pour_engine.py tests/unit/backends/altium/test_pour_regions.py -q -n 0`
- [x] 1.4 Teach `altium.pour-changed` on the agent guide page that lists Altium codes.
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [x] 1.5 Run the pour census on the public rows: the counts of poured and refused polygons stay the same, or
  each change is explained.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_compare.py tests/unit/backends/altium/test_pour_refusal.py -q -n 0`
- [x] 2.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 2.2 Maintainer board (private, codes only): with a remote zone added, the pours of the other nets
  are written byte-identical, apart from the index, and Altium's dead-copper analysis finds no new island.

  Result (maintainer board, 2026-11-16): with a remote zone, 40 of 40 written pours byte-identical apart from the index; the same 5 `altium.pour-changed` with and without it; but each written document holds 2 zero-length pour edges or tracks (expected 0): follow-up. Altium dead-copper part not run (VM).

  Decision (maintainer, 2026-11-17): the 2 zero-length edges were not written by Fenolite's pour; they are in
  the source document's own shape-based region (one outline vertex stated twice in a row) and the carrier
  copied them. The carrier now drops a repeated vertex (neither round) from the carried plain and shape-based
  records; the copper is the same and every other byte is the source's. Test
  `test_a_carried_zero_length_edge_is_dropped`.

  Result (maintainer board, 2026-11-17): zero-length pour edges or tracks 0 and 0 (were 2 and 2); with the
  remote zone 40 of 40 written pours byte-identical apart from the index; 5 `altium.pour-changed` in both,
  as before; exit 0 and equivalence level 5 in both. Altium dead-copper part still not run (VM).
