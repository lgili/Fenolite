# Tasks: c0488-altium-four-layer-through-hole-pads

Rules for every task:

- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages. Test boards are authored for Fenolite.
- New files under `tests/data/` get a `tests/data/MANIFEST.toml` entry.
- Run each touched test file alone with `-n 0`.

- [ ] 1.1 Author a 4-layer KiCad board with two through-hole pads and run the matrix of design D1 through
  `convert --to altium` and `build --target altium`; record which case loses the inner layers, and where
  (`lower._stack`, `lower._built_stack` or `adapter.layers.LayerMap`), in this change's design.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_four_layer_tht_c0488.py -q -n 0`
- [ ] 1.2 Declare the fixture.
  - Proof: `uv run --extra dev pytest tests/corpus/test_manifest.py -q -n 0`
- [ ] 2.1 Return the span `all` from `norm.copper_span` for a plated pad on every copper layer, and write it
  in `span_text`; tests for the two new scenarios of "Tolerances and normalisation".
  - Proof: `uv run --extra dev pytest tests/unit/checks/equivalence/test_norm.py -q -n 0`
- [ ] 2.2 Run the other level 3 tests that read `pad-copper`.
  - Proof: `uv run --extra dev pytest tests/unit/checks/equivalence/test_c0281_levels.py -q -n 0`
- [ ] 3.1 Keep the inner layers in the written stack (or in the reader's chain) as task 1.1 found; tests for
  "Four-layer board through convert" and "Four-layer board through build".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_four_layer_tht_c0488.py tests/unit/backends/altium/test_lower_stackup.py -q -n 0`
- [ ] 3.2 Run the plane and layer tests of earlier changes.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_altium_planes_c0466.py tests/unit/backends/altium/test_lower_layers.py -q -n 0`
- [ ] 4.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 4.2 Maintainer board (private, codes and counts only): `convert --to altium` and `build --target
  altium` of the 4-layer board give no `convert.unexplained`, and the written document's
  stack holds every copper layer of the source.
