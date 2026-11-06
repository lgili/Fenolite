# Tasks: c0431

## 1. Writer

- [x] 1.1 Write the copper graphics of a net-tie footprint as component primitives on their signal layer,
  without a net; keep the `footprint-copper` loss for other footprints, planes and graphics no record holds.
  Proof: `uv run pytest tests/unit/convert/test_net_tie_copper.py tests/unit/backends/altium/test_lower_items.py -q`.

## 2. Equivalence

- [x] 2.1 Add the level 3 kind `net-tie-copper`, compared for footprints that are a net tie on a side.
  Proof: `uv run pytest tests/unit/convert/test_net_tie_copper.py tests/unit/checks/equivalence/test_codes.py -q`.
- [x] 2.2 A lost `footprint-copper` row explains it. Proof: `test_unwritten_tie_copper_is_refused_then_explained`.
- [x] 2.3 KiCad's import keeps the tie copper in the footprint (S-2083): `altium_import.import_design` projects
  footprint items, and the comparison counts the primitives of an unnumbered, netless custom pad.
  Proof: `test_import_board.py`, `test_net_tie_copper.py`, and with kicad-cli 10.0.6
  `tests/kicad/altium/test_rta3_oracle.py`, `tests/kicad/equivalence/test_triangle_corpus.py`,
  `tests/kicad/convert/test_triangle.py`.

## 3. Docs and evidence

- [x] 3.1 `explain.toml`, `docs/equivalence.md`, `docs/cli-contract.md`, `docs/cli-surface.json`,
  `pcb-records.md`, S-1900, CHANGELOG. Proof: `uv run python tools/gen_cli_surface.py --check`.
- [x] 3.2 Altium opens the written tie and its DRC is clean on it: an agent's run in Altium 24.5.2.23 (S-1901; default rules give only the width rule's message). Not a maintainer kit case, so the level stays INFERRED.
