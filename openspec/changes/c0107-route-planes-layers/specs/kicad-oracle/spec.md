## ADDED Requirements

### Requirement: Plane routing passes the oracle
The plane layers, the track layer rules, the plane fan-out and the Specctra lists of this change SHALL be proved with Freerouting `PINNED_VERSION` and `kicad-cli` 9.0.9 and 10.0.6, on the authored four-layer bench of `tests/routing/_planebench.py` (two plane layers, an SOIC-8, three 0603 parts and through-hole headers from the offline catalog, classes `PWR`, `SIG` and `HV`, a 1 mm `HV`–`SIG` rule).
- **Row type** (`H-K-LAYER-POWER`): the routed bench with its inner layers of type `power` loads on both majors, its DRC report holds no violation type that the same board with `signal` rows lacks, its inner Gerbers carry `%TF.FileFunction,Copper,L2,Inr*%` and `L3`, and `pcb upgrade --force` keeps the type on 10.0.6. Probes `pcb-layer-power-t9`, `pcb-layer-power-t10` and `pcb-layer-power-resave`.
- **Track layer rule** (`H-K-DRU-NOTRACKS`): a `no_tracks` rule written by `lower_rules` on a board with tracks of the class on and off its layer gives one `items_not_allowed` per track on it and none for the others, with the scoped canary firing, on both majors. Probe `dru-kind-no_tracks`.
- **Fan-out** (`H-K-FANOUT`): `fenolite route --router direct --nets GND --nets VCC --confirm` on the bench built with `planes=` gives fan-out copper (the plane nets alone are selected: the direct router avoids nothing, so its tracks of the other nets would cross); `check` then reports no finding of its copper stage, and after `fenolite fill --confirm` on 10.0.6, `pcb drc` of the board's major reports no unconnected item of a plane net and no violation of severity error that the unrouted board lacks. Probes `route-fanout-t9` and `route-fanout-t10`; the target-9 board is filled by `fenolite fill` with `kicad-cli` 10.0.6, which writes it back for target 9, and judged by 9.0.9.
- **Freerouting** (`H-G-DSN-LAYERS`, `H-G-DSN-PLANE`, `H-G-DSN-CLEARANCE`, `H-G-DSN-EDGE`), in tests marked `needs_freerouting`: `dsn-power-layers` (no wire on a `power` layer), `dsn-plane-alone` (recorded: plane nets left open without fan-out), `dsn-plane-fanout` (with fan-out, no copper added to the plane nets and no open plane connection), `dsn-use-layer`, `dsn-class-class` (no `HV`–`SIG` clearance finding under KiCad's DRC, on the bench variant whose `HV` nets pass the pads of `SIG`, with the same file without the list as control), `dsn-layer-rule` (recorded: `different` on 2026-10-08, the wire is narrowed at pins), `dsn-keepout`, and `dsn-edge-band` (a bench whose shortest route runs along the edge, with the bands added to the file by the test: recorded `different` on 2026-10-08, the route of a 2 mm passage is lost, so the writer writes no band).
- The `dsn-*` outcomes MUST be recorded in `docs/evidence/routing.md` and `docs/evidence/routing/freerouting-2.4.1.json`, never in `docs/evidence/kicad/probes/`; the other probes in the probe files of their majors.

#### Scenario: Plane bench on 10.0
- **GIVEN** the pinned jar, Java 25 and the local `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/routing/test_freerouting_planes.py tests/kicad/routing/test_fanout_oracle.py tests/kicad/board/test_layer_power.py -rA` runs
- **THEN** every probe above records its outcome, and the register row of an outcome that differs from its criterion records what Freerouting or KiCad showed

#### Scenario: Plane bench on 9.0
- **WHEN** `tests/kicad/board/test_layer_power.py`, `tests/kicad/rules/test_rule_kinds_new.py -k no_tracks` and `tests/kicad/routing/test_fanout_oracle.py` run inside the pinned 9.0.9 image
- **THEN** `pcb-layer-power-t9`, `dru-kind-no_tracks` and `route-fanout-t9` record their expected outcomes in `9.0.9.json`

#### Scenario: Skipped without the tools
- **GIVEN** no `FENOLITE_FREEROUTING_JAR`
- **WHEN** `uv run pytest tests/routing/test_freerouting_planes.py -rs` runs
- **THEN** every test is skipped with a reason naming the variable
