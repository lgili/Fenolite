## ADDED Requirements

### Requirement: Board-frame queries agree with kicad-cli
`tests/kicad/frame/` (marker `needs_kicad`, major-aware) SHALL check `board_pads` and `placed_extent` against the running `kicad-cli` on the frame bench `tests/kicad/frame/_framebench.py`. The bench MUST hold `Mini_R_0603`, `Mini_LED_THT_3mm`, `Mini_QFP-32_7x7mm_P0.8mm` (from `Mini_v9.pretty` for target 9, `Mini.pretty` for target 10) and the authored CC0 footprints of `tests/data/libs/Frame.pretty`, placed with `place_footprint` at 0°, 90°, 180°, 270° and 30° on both sides, each pad on its own net, written for the running major with a project `fp-lib-table`, a rules file that sets every clearance to 0.2 mm (written with c0018's `write_rules`), and an empty `KICAD_CONFIG_HOME`. DRC MUST be judged only from the JSON report read with `read_drc_report`.
- **Positions** (`test_pad_positions`): every non-via `317` and `327` record of `pcb export ipcd356` MUST match one `board_pads` record by reference and pin, the differences between records MUST equal those of the records' `position` within ±2 export units per axis, exactly at multiples of 90°, and the `R` field MUST equal `(−rotation) mod 360°` in degrees. This extends the data of `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE` and `H-G-PAD-ANGLE-ABS` to 180° and 270°.
- **Copper entries** (`H-G-FRAME-SHAPE`): for each `circle`, `rect`, `oval`, `roundrect` and filled-polygon `custom` pad of the bench, two probe vias of another net, one along an edge normal and one along a corner diagonal, MUST be placed where their exact distance to the pad's copper entries is 0.2 mm minus 20 µm (near board) or plus 20 µm (far board), found by bisection with exact integer tests. On the near board each probe MUST give exactly one `clearance` violation naming its uuid; on the far board none MUST.
- **Extents** (`H-G-FRAME-CRTYD`): pairs of bench footprints whose `placed_extent` faces overlap by 20 µm MUST give one `courtyards_overlap` violation per pair, and pairs 20 µm apart none, for rectangle, line-loop and circle courtyards on both sides. The second footprint of a pair is moved along X from the first contact, found by bisection with `polygons_intersect`.
- **Probes**, in `tests/kicad/_probes.py` for majors 9 and 10: `pcb-frame-shape-near` (`present` when every near probe fires once, `different` otherwise), `pcb-frame-shape-far` (`absent` when none fires), `pcb-frame-crtyd-overlap` (`present` when every pair fires once) and `pcb-frame-crtyd-gap` (`absent` when none fires). An outcome other than the expected one MUST stop the change until the entry or extent rule is revised and the row is refuted with a successor.

#### Scenario: Pad positions on both majors
- **GIVEN** the frame bench written for the running major
- **WHEN** `uv run pytest tests/kicad/frame/test_frame_oracle.py::test_pad_positions` runs on the local KiCad 10.0.6 and in the `kicad-9` job
- **THEN** every pad record matches, including the footprints at 180° and 270° on the bottom

#### Scenario: Clearance canary
- **WHEN** `uv run pytest tests/kicad/frame/test_frame_oracle.py::test_shape_canary` runs
- **THEN** `run("pcb-frame-shape-near")` is `present` and `run("pcb-frame-shape-far")` is `absent`

#### Scenario: Courtyard canary
- **WHEN** `uv run pytest tests/kicad/frame/test_frame_oracle.py::test_courtyard_canary` runs
- **THEN** `run("pcb-frame-crtyd-overlap")` is `present` and `run("pcb-frame-crtyd-gap")` is `absent`

### Requirement: Script copper passes the oracle
`tests/kicad/frame/` SHALL prove on the running `kicad-cli` that copper resolved from intents loads, keeps its uuids and connects its pads, using builds of `examples/blink_routed/design.py`.
- **Uuids** (`H-G-FRAME-UUID`), probes run before `resolve_copper` exists, on a board whose tracks and vias carry copper uuids set in the test: `pcb-frame-uuid-9` (majors 9 and 10: the target-9 board loads, `load`), `pcb-frame-uuid-10` (major 10: the target-10 board loads) and `pcb-frame-uuid-keep` (major 10: after `pcb upgrade --force`, every track and via keeps its uuid, `equal`). A `reject` or `different` outcome MUST stop the change until the uuid scheme is revised (design, "Risks").
- **Route** (`H-G-FRAME-ROUTE`): `pcb-frame-route` (majors 9 and 10: the routed blink's report holds no `unconnected_items` entry and no `clearance` or `shorting_items` violation naming a script item, `absent`), `pcb-frame-route-cut` (majors 9 and 10: the same board without the `led_a` segment that reaches `D1` gives exactly one unconnected item, `present`) and `pcb-frame-route-moved` (majors 9 and 10: the build whose `D1` was moved 4 mm by `tests/_layout_edit.py::move_footprint` and then rebuilt, `absent` as for `pcb-frame-route`; on major 10 the target-10 board is re-saved with `pcb upgrade --force` before the rebuild, and on major 9 the edited target-9 text is rebuilt, because 9.0 has no `pcb upgrade` (S-0037)).
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and built files MUST NOT be committed.

#### Scenario: Copper uuids survive a re-save
- **WHEN** `uv run pytest tests/kicad/frame/test_copper_oracle.py -k uuid` runs on the local KiCad 10.0.6
- **THEN** `pcb-frame-uuid-9` and `pcb-frame-uuid-10` are `load` and `pcb-frame-uuid-keep` is `equal`

#### Scenario: Routed nets are connected
- **WHEN** `uv run pytest tests/kicad/frame/test_copper_oracle.py -k route` runs on 10.0.6 and in the `kicad-9` job
- **THEN** on both majors `pcb-frame-route` and `pcb-frame-route-moved` are `absent` and `pcb-frame-route-cut` is `present`

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for each `pcb-frame-*` probe of major 10
