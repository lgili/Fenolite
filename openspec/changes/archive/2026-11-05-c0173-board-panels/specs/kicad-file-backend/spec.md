## ADDED Requirements

### Requirement: Panel boards written
A KiCad panel board SHALL hold every item of each copy moved exactly, nets renamed `B<k>/<name>`, uuids derived from the copy ids, the frame and gap rings on `Edge.Cuts` instead of the copies' outlines, score lines on the user layer named `V-Score`, one `Fenolite_Panel:MouseBites_…` footprint per tab of `np_thru_hole` pads, and c0118's fiducial and tooling-hole footprints.

#### Scenario: Panel board of the fixture
- **GIVEN** `tests/data/panels/tabs.py` (2 × 4 copies of the fixture, tabs, rails with three fiducials and four tooling holes)
- **WHEN** `uv run pytest tests/unit/panel/test_kicad.py -k fixture` writes and reads the panel board
- **THEN** it holds 8 × the fixture's footprints plus the tab, fiducial and tooling footprints, every net name starts with `B1/` to `B8/`, and `edge_outline` gives one outer ring and the gap rings

#### Scenario: The board loads in KiCad
- **WHEN** `uv run pytest tests/kicad/panel/test_panel_board.py -k load` runs in the pinned 9.0.9 and 10.0.6 images
- **THEN** each board loads, DRC gives no `invalid_outline`, no `unconnected_items` and no finding beyond the copies' own, and the NPTH file holds every mouse-bite and tooling hole

#### Scenario: Panel rebuilds to the same bytes
- **WHEN** the same panel script is written twice with the same `--seed` and `--timestamp`
- **THEN** every file keeps its bytes
