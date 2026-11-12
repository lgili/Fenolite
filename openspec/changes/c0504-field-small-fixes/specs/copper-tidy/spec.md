## ADDED Requirements

### Requirement: Style findings with places
`fenolite.tidy.style` SHALL give, besides `tidy.acute`, `tidy.jog` (info) at the middle of each jog, `tidy.off-45` (info)
at each joint of kind `other`, and `tidy.collinear` (info) at each point where exactly two tracks of one net, layer
and width meet in a straight line with nothing else there. The report MUST count the collinear joints as
`collinear`, beside the other joint kinds (change c0504).

#### Scenario: A jog, a 60° corner and a redundant point
- **GIVEN** an authored board with one net drawn as a 0.2 mm jog between two 45° turns, a 120° corner and two
  collinear tracks joined end to end
- **WHEN** `uv run pytest tests/unit/tidy/test_report.py -k places` runs `fenolite tidy <board> --report --json`
- **THEN** the exit code is 0, the issues hold one `tidy.jog`, one `tidy.off-45` and one `tidy.collinear`, each
  at its point, and `result.report` counts one `collinear` joint

### Requirement: Style report of any board
`fenolite tidy PATH --report` and `--compare` SHALL read any board that a `BoardFrame` backend reads, an Altium
`.PcbDoc` included. A tidy step on a board that is not KiCad MUST exit 2 with `FEN-2001`, saying that the steps write
KiCad boards and that `--report` reads any board (change c0504).

#### Scenario: The report of an Altium document
- **WHEN** `fenolite tidy tests/data/slots/slots_altium.PcbDoc --report --json` runs
- **THEN** the exit code is 0 and `result.report` holds the joint counts of its tracks; with `--chamfer` instead
  of `--report` the exit code is 2
