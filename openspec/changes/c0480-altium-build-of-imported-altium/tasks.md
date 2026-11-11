# Tasks: c0480-altium-build-of-imported-altium

- [x] 1.1 `lower_items` and `_document_holds` check drawings with the document's layer map
  (`lower.built_mechanical`, `lower.kicad_mechanical`), with unit tests.
  - Proof: `uv run --extra dev pytest tests/unit/lens/test_altium_carried_build_c0480.py -q`
- [x] 1.2 `source_not_lowered` leaves out the design's own items, with a unit test.
  - Proof: `uv run --extra dev pytest tests/unit/lens/test_altium_carried_build_c0480.py -q`
- [x] 1.3 `build --target altium` of a script with `Fenolite.Altium.*` board carriers writes through the
  conversion (`cmd_build.altium_carried`, `_through_conversion`), with a round-trip test and a
  `CHANGELOG.md` entry.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/lens/test_altium_carried_build_c0480.py -q`
- [x] 1.4 A conversion to Altium puts a single-pad `unconnected-(…)` pad on no net (`to_altium.open_pads`),
  with a unit test.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/lens/test_altium_carried_build_c0480.py -q`
- [x] 1.5 Maintainer board (private, codes and counts only): F2 equals F5 (rules, equivalence), and the
  F2 project compiles in Altium 24.5 with the source's messages.
  - Result 2026-11-11: 124 of 124 rules, 537 of 537 pad nets, 262 footprints at the same pose; F2 and F5
    give the same equivalence findings; Altium 24.5 compiles F2 with no error, 262 components, 103 nets
    identical to the source.
