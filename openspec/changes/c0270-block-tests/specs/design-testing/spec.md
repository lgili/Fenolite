## ADDED Requirements

### Requirement: Stimulus of a block under test
`instantiate(block, *, stimulus=None, **params)` SHALL turn each entry of `stimulus(...)` into a c0253 rig element on the net `dut/<port>` (or `dut/<port>.<member>`) named `stim_<port>`: a voltage or range into a supply against the reference, `source(voltage, current=...)` into a supply with that current, and `draw(current)` into a sink. The rig MUST NOT reach any output.

#### Scenario: A divider judged with its input
- **GIVEN** the authored block `Test:divider` with an expectation on its output
- **WHEN** `uv run pytest tests/unit/testing/test_stimulus.py -k judged` calls `instantiate(divider, stimulus=stimulus(HI=volt("12").pct(2), LO=volt(0)))`
- **THEN** the expectation's row has the status `pass`, and the built board, netlist and BOM equal those built without the stimulus

#### Scenario: Without a stimulus nothing is known
- **WHEN** the same block is instantiated without `stimulus`
- **THEN** the expectation's row has the status `unknown` and `findings("circuit.expect-unknown")` holds one finding

### Requirement: Stimulus reference
The reference of a stimulus SHALL be `ref` when given, else the one port given exactly 0 V, else the block's one `Ground` port. No reference, two candidates, an unknown port, a member of a single-net port, or a current where a voltage is expected or the reverse MUST raise `TestingError` naming the port before anything is built.

#### Scenario: Ambiguous reference
- **WHEN** `uv run pytest tests/unit/testing/test_stimulus.py -k reference` calls `stimulus(HI=volt(0), LO=volt(0))` on the divider, and `stimulus(HX=volt(1))`
- **THEN** the first raises `TestingError` naming `HI` and `LO`, the second naming `HX` and the block's ports, and no temporary folder is left

### Requirement: Requirement rows in tests
`TestDesign.requirements(pattern="*")` SHALL return the rows of c0253's requirement table whose id matches the glob, each with `id`, `entities`, `quantity`, `value`, `limit`, `status` and `evidence`, from the same tool-free check run as `findings`. Without the circuit stage it MUST raise `TestingError`.

#### Scenario: Rows of a block
- **WHEN** `uv run pytest tests/unit/testing/test_queries.py -k requirements` reads `requirements("dut/*")` of the stimulated divider
- **THEN** each row's id starts with `dut/`, the output row's `value` and `limit` are c0246 ranges, and a second call runs no stage again

### Requirement: Achieved values in tests
`TestDesign.achieved(path)` SHALL return the c0246 range that the c0254 generator which made the part at `path` achieved, as recorded in `result.generators`, and MUST raise `TestingError` for a part that no generator made.

#### Scenario: Achieved output range
- **WHEN** `uv run pytest tests/unit/testing/test_queries.py -k achieved` reads `achieved("dut/top")` of the instantiated divider and `achieved("dut/J1")`
- **THEN** the first is the output range of the generator's `gen.achieved` finding, and the second raises `TestingError`

### Requirement: Placement in part views
`PartView` SHALL give `at` (integer nanometres), `rotation` (integer microdegrees) and `side` (`top` or `bottom`) of the part's footprint on the built board.

#### Scenario: Placement read back
- **GIVEN** an authored script placing `R1` at 10 mm, 5 mm, turned by 90° on the bottom
- **WHEN** `uv run pytest tests/unit/testing/test_queries.py -k placement` loads it
- **THEN** `ref("R1").at` is `(10000000, 5000000)`, `rotation` is `90000000` and `side` is `bottom`
