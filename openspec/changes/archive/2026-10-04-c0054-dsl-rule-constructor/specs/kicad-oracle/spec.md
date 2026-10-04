## ADDED Requirements

### Requirement: Script rule minimums are enforced by kicad-cli
The minimums that a design script declares with `design.rules.minimum` (`design-dsl`, "Rule minimums in the DSL") SHALL be proved by `kicad-cli pcb drc` on built projects (`H-K-DSL-MINIMUM`). `tests/kicad/build/test_script_rules_oracle.py` holds the proof and runs through the package runner on temporary copies.
- The bench MUST be the routed blink of `examples/blink_routed/design.py` built with its script copper: tracks of 0.3 mm, tracks of 0.5 mm on `GND` (class `PWR`), and vias of 0.6 mm with a 0.3 mm drill.
- Each case MUST build the bench twice from scripts that differ only in the value of one minimum: once with a value the copper breaks, once with a value it respects. The verdict MUST come from the DRC JSON report, never from the exit code (`DRC verdicts come from the JSON report`).
- The cases and their violation types MUST be:

  | case | minimum that is broken | minimum that is respected | type |
  |---|---|---|---|
  | board track width | `track_width=mm(0.4)` | `track_width=mm(0.3)` | `track_width` |
  | class track width | `track_width=mm(0.6), netclass="PWR"` | `track_width=mm(0.5), netclass="PWR"` | `track_width` |
  | board via diameter | `via_diameter=mm(0.7)` | `via_diameter=mm(0.6)` | `via_diameter` |
  | board via drill | `via_drill=mm(0.4)` | `via_drill=mm(0.3)` | `drill_out_of_range` |
  | board clearance | `clearance=mm(1)` | `clearance=mm(0.15)` | `clearance` |
  | class clearance | `clearance=mm(1), netclass="PWR"` | `clearance=mm(0.2), netclass="PWR"` | `clearance` |

- The breaking build MUST give at least one violation of the case's type with severity `error`, and the respecting build MUST give none of that type.
- In the class track-width case every violating item MUST be a track of `GND`, the only routed net of the class. In the class clearance case every violation MUST hold at least one item of a net of the class (`GND` or `VIN`).
- No separate canary is needed: the two builds of a case hold the same rules with different values, so a project whose rules `kicad-cli` did not load gives no violation in the breaking build, and the case fails.
- The cases MUST run for target 10 on `kicad-cli` 10.0.x and for target 9 on 9.0.x and 10.0.x (`Major-aware oracle tests`).

#### Scenario: A broken board minimum is reported
- **GIVEN** the routed blink with `design.rules.minimum(track_width=mm(0.4))`
- **WHEN** `uv run pytest tests/kicad/build/test_script_rules_oracle.py -k "board_track_width"` builds it and runs `pcb drc` on 10.0.6
- **THEN** the report holds `track_width` violations of severity `error` on the 0.3 mm tracks, and the same design with `track_width=mm(0.3)` gives no `track_width` violation

#### Scenario: A class minimum governs only its class
- **GIVEN** the routed blink with `design.rules.minimum(track_width=mm(0.6), netclass="PWR")`
- **WHEN** the same test runs the case `class_track_width`
- **THEN** every `track_width` violation names a track of the net `GND`, no track of `LED_DRV` or `LED_A` is reported, and with `track_width=mm(0.5), netclass="PWR"` the report holds no `track_width` violation
