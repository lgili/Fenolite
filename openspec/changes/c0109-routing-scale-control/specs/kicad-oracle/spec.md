## ADDED Requirements

### Requirement: Grouped and budgeted routes pass the oracle
The routing scale controls SHALL be proved with the pinned tools and `kicad-cli` 9.0.9 and 10.0.6, in tests marked `needs_router` or `needs_freerouting`, probes first:
- **Group** (`H-K-KRT-GROUP`): `tests/routing/test_krt_gate.py::test_group` routes an authored blink with two net classes that share sizes, in one KiCadRoutingTools run without `--clearance`; `pcb drc` of the board's major then reports no unconnected item and no violation type of severity error that the unrouted board lacks. Outcomes `krt-group-t9`, `krt-group-t10`.
- **No optimizer** (`H-G-DSN-NOOPT`): `tests/routing/test_freerouting_gate.py::test_no_optimizer` runs the blink's design file with `--router.optimizer.enabled=false` and with `-mt 0`; outcomes `dsn-noopt` (whether an optimization stage is logged with the switch) and `dsn-mt0` (the same with `-mt 0` alone).
- **Netless** (`H-G-DSN-NETLESS`): `::test_netless` routes a bench where a net outside the job has a class clearance wider than the board's default rule: once left out of the network section, once as `others="netless"` writes it (declared, because its class is wider), and a control where that class is named with `-inc`; outcomes `dsn-netless` (a session wire on the left-out net, or a KiCad clearance violation against it), `dsn-netless-declared` (a KiCad clearance violation against it in the file as written) and `dsn-inc` (a session wire on the class named with `-inc`). The test MUST fail on a session wire on the left-out net, on a clearance violation when the left-out net is judged in the default class, and on `dsn-netless-declared` = `present`; `dsn-netless` is recorded either way.
- **Gates kept**: the existing `test_route` of both gates MUST still record `equal` with the command lines of this change.

The outcomes MUST be recorded in `docs/evidence/routing.md`, the Freerouting ones also in `docs/evidence/routing/freerouting-2.4.1.json`, and never in `docs/evidence/kicad/probes/`. `docs/evidence/routing.md` MUST also hold the measured record of 2026-10-05 on the generated 100-part board: per run the command, the selected and declared nets, the router's stage times and CPU seconds, the copper added, the tracks on plane layers, KiCad's unconnected items and DRC findings by type, and the machine load.

#### Scenario: Group on 10.0
- **GIVEN** `FENOLITE_KRT` and `FENOLITE_KRT_PYTHON` naming the pinned checkout
- **WHEN** `uv run pytest tests/routing/test_krt_gate.py -k group -rA` runs on the local KiCad 10.0.6
- **THEN** `krt-group-t10` is `equal`

#### Scenario: Group on 9.0
- **WHEN** `test_group` runs for the target-9 blink with the board judged inside the pinned 9.0.9 image
- **THEN** `krt-group-t9` is `equal`, and the outcome is recorded

#### Scenario: Optimizer switch and netless nets
- **GIVEN** `FENOLITE_FREEROUTING_JAR` naming the pinned jar and Java 25
- **WHEN** `uv run pytest tests/routing/test_freerouting_gate.py -k "no_optimizer or netless" -rA` runs on the local KiCad 10.0.6
- **THEN** `dsn-noopt` is `absent`, `dsn-mt0` is `present`, `dsn-netless-declared` is `absent` and `dsn-inc` is `present`, and `dsn-netless` is recorded as measured (`present` on 2026-10-08: no wire on the left-out net, and two clearance violations by KiCad at 0.3 mm from a class of 0.4 mm), each with the jar's SHA-256 and the Java version
