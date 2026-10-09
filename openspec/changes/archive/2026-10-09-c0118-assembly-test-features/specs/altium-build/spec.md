## ADDED Requirements

### Requirement: Assembly and test features in an Altium build
An Altium build SHALL write the parts of `test_point()` as ordinary parts, SHALL leave the parts of `fiducial()` out of the schematic and of the PCB library and document, because the PCB library writer refuses their footprints, and SHALL write the parts of `tooling_hole()` as the holes of `hole()` ("PCB document output", c0102).
- **Test points.** A test-point part MUST be planned like any part with an authored definition: its symbol in the schematic library and on its sheet, its footprint in the PCB library, and its component in the PCB document with pad `1` on the part's net. Its footprint holds one numbered pad with copper, which `pcblib.check_footprint` accepts.
- **Marks.** `Pad.fab_property` MUST NOT be written to any Altium record: no public source yet says how a pad record holds a test-point, fiducial or other fabrication mark. Every footprint that is written and holds a marked pad (the test points, and an authored footprint with `fab_property=`) MUST be named by one `altium.not-lowered` info of the kind "pad properties".
- **Fiducials.** Their parts MUST be left out before the footprint check, so that they give no `altium.footprint-unsupported` and never make the build withhold the PCB document (`altium.pcbdoc-not-written`), and MUST be named by one `altium.not-lowered` info of the kind "assembly features". Their keep-outs are board keep-outs and are reported as "PCB document output" reports every keep-out.
- **Tooling holes.** A tooling-hole part has the symbol `Fenolite_Holes:Hole`, so it is a hole part of "PCB document output": it is no component, and its round hole that is not plated is written as a board hole of the PCB document. Its courtyard is not written, as for every hole part.
- These two kinds extend the list of c0032's `altium.not-lowered` row, as the kinds of "PCB document output" do.
- Every other file and item MUST be planned as for the same design without the fiducials.

#### Scenario: Test point written, fiducial left out
- **GIVEN** a variant of `examples/blink_2layer/design.py` with `d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))`, `d.tooling_hole("TH1", mm(46), mm(4), drill=mm(3))` and `d.test_point("TP1", led_a, mm(30), mm(12), size=mm(1.5))`
- **WHEN** `uv run pytest tests/unit/lens/test_build_assembly.py -k altium` builds it with `--target altium --dry-run --json`, and then with `--confirm`
- **THEN** the exit code is 0; the PCB document is planned and holds the component `TP1` with its pad on `LED_A`; no written document holds `FID1` or `TH1`; the stored board holds a board hole of 3 mm; and `issues` holds one `altium.not-lowered` info of the kind "assembly features" naming `FID1`, one of the kind "pad properties" naming the test-point footprint, and neither `altium.footprint-unsupported` nor `altium.pcbdoc-not-written`
