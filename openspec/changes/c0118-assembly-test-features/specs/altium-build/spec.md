## ADDED Requirements

### Requirement: Assembly and test features in an Altium build
An Altium build SHALL leave the parts of `fiducial()`, `test_point()` and `tooling_hole()` out of the schematic and of the PCB document, and SHALL report them with one `altium.not-lowered` info of the kind "assembly features" that names them. A mark on any other authored pad SHALL NOT be lowered, and SHALL give one `altium.not-lowered` info of the kind "pad properties" that names the footprints. These kinds extend the list of c0032's `altium.not-lowered` row.
- Every other file and item MUST be planned as for the same design without those parts.

#### Scenario: Features left out
- **GIVEN** a variant of `examples/blink_2layer/design.py` with `d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))` and `d.test_point("TP1", led_a, mm(30), mm(12), size=mm(1.5))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, no planned file holds `FID1` or `TP1`, and `issues` holds one `altium.not-lowered` info of the kind "assembly features" naming both
