## ADDED Requirements

### Requirement: Freerouting routes pass the oracle
The Specctra writer, the session reader and the Freerouting plugin SHALL be proved with Freerouting `PINNED_VERSION` and `kicad-cli` 9.0.9 and 10.0.6, probes first, in tests marked `needs_freerouting`:
- **Accept** (`H-G-DSN-ACCEPT`): Freerouting writes a readable session for the written two-pad board and blink.
- **Units** (`H-G-DSN-UNITS`): after `to_copper`, both ends of the two-pad route lie within 100 nm of the pad centres.
- **Protect** (`H-G-DSN-PROTECT`): with one blink net routed beforehand, no session wire on that net differs from the input.
- **Route** (`H-G-DSN-ROUTE`): after `fenolite route --router freerouting --confirm` (and `fenolite fill --confirm` on 10.0.6), `pcb drc` of the board's major reports no unconnected item and no violation type of severity error that the unrouted board lacks.
- **Repeat** (`H-G-DSN-REPEAT`) and **offline** (`H-G-DSN-OFFLINE`, in a container with `--network none`): outcomes recorded.

The outcomes MUST be recorded in `docs/evidence/routing.md` and `docs/evidence/routing/freerouting-2.4.1.json` with the jar's SHA-256 and the Java version, and MUST NOT be written to `docs/evidence/kicad/probes/`. At day 6 of the time box, `dsn-accept` and `dsn-route-t10` MUST hold; otherwise the change stops and the remaining work is recorded for v0.2a.

#### Scenario: Gate on 10.0
- **GIVEN** `FENOLITE_FREEROUTING_JAR` naming the pinned jar and Java 25
- **WHEN** `uv run pytest tests/routing/test_freerouting_gate.py -rA` runs on the local KiCad 10.0.6
- **THEN** `test_accept`, `test_units`, `test_protect` and `test_route` pass, and `test_repeat` records its outcome

#### Scenario: Gate on 9.0
- **WHEN** `test_route` runs for the target-9 blink with the board judged inside the pinned 9.0.9 image
- **THEN** it passes without the fill step, and the outcome is recorded

#### Scenario: Offline run
- **GIVEN** Docker and the pinned Freerouting image
- **WHEN** `uv run pytest tests/routing/test_freerouting_gate.py::test_offline` runs
- **THEN** the container with `--network none` writes a session, the outcome is `present`, and `FreeroutingRouter.sends_data_offsite` is `False` in the same commit that records it

#### Scenario: Skipped without the tool
- **GIVEN** no `FENOLITE_FREEROUTING_JAR`
- **WHEN** `uv run pytest tests/routing -m needs_freerouting -rs` runs
- **THEN** every test is skipped with a reason naming the variable
