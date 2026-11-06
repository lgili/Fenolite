# Tasks: c0443

## 1. Code

- [x] 1.1 The reader gives a component's board cut-out as a footprint `Edge.Cuts` polygon;
  `uv run pytest tests/unit/backends/altium/test_component_cutouts.py -k written_as`.
- [x] 1.2 The writer writes a footprint's closed `Edge.Cuts` outline as a cut-out of its component, once;
  `uv run pytest tests/unit/backends/altium/test_component_cutouts.py`.
- [x] 1.3 `frame.board_edges` holds the footprints' cut-outs;
  `uv run pytest tests/unit/backends/altium/test_frame.py tests/unit/backends/altium/test_component_cutouts.py`.

## 2. Evidence and docs

- [x] 2.1 Round trip and KiCad DRC of public row `-06` (S-2020); `pcb-records.md`, CHANGELOG;
  `uv run pytest tests/unit/test_format_facts.py`.
- [x] 2.2 altium-rounds-2 opens the round trip of row `-06`: the two cut-outs of the connector are board
  cut-outs of the component, not keep-outs, and DRC finds no new violation (kit request).
