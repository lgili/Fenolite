## ADDED Requirements

### Requirement: Integer delay and loss values
`fenolite.dsl` SHALL export `fs`, `ps` and `ns`, giving a `Delay` of integer femtoseconds, and `mdb` and `db`, giving a `Loss` of integer milli-decibels. A text with more digits than one femtosecond or one milli-decibel holds, a negative value and a float MUST raise `DslError`. The model MUST store these values as integers in keys ending `_fs` and `_mdb`.

#### Scenario: Exact conversion
- **WHEN** `uv run pytest tests/unit/dsl/test_timing.py` converts `ps("12.5")`, `ns("1.2")` and `db("1.5")`, and `ps("0.0001")` and `ps(1.5)`
- **THEN** the first three give 12 500 fs, 1 200 000 fs and 1 500 mdB, and the last two raise `DslError`

### Requirement: Propagation and loss inputs
`design.propagation(layer, *, per_mm)`, `design.propagation(*, via)` and `design.loss(layer, *, per_mm, at)` SHALL record the user's propagation delay per millimetre of a copper layer, per via crossed, and loss per millimetre at a frequency, in `RuleSet.propagation` and `RuleSet.losses`. Fenolite MUST ship no propagation or loss value.

#### Scenario: Inputs round trip
- **GIVEN** a script that declares `F.Cu` at `fs(5_900)` per mm and vias at `fs(10_000)`
- **WHEN** `uv run pytest tests/unit/model/test_rules.py -k propagation` builds it and reads `rules.json` back
- **THEN** `RuleSet.propagation` holds those two integers, and a design without them stores no key

### Requirement: Topologies as ordered pad trees
`design.topology(name, *chains)` SHALL record an ordered tree of pins, where `a >> b` chains two pins and `a >> (b, c)` fans out. Consecutive pins MUST share a net unless a bridge joins them. A cycle, a pin on two branches, a disconnected tree or consecutive pins on two nets without a bridge MUST raise `DslError` located by line. The tree MUST be stored in `RuleSet.topologies` with nodes as `REF-PIN`.

#### Scenario: A daisy chain through a terminator
- **GIVEN** `examples/topologies/design.py`, whose `clk` chains `U1-CLK >> R1-1` and `R1-2 >> U2-CLK >> U3-CLK >> U4-CLK`, with `R1` bridging pins 1 and 2
- **WHEN** `uv run pytest tests/unit/dsl/test_topology.py -k daisy` builds it
- **THEN** the topology holds five net edges and one bridge edge, across the nets `CLK_A` and `CLK_B`

#### Scenario: A cycle refused
- **WHEN** a script chains `U1-1 >> U2-1 >> U3-1 >> U1-1`
- **THEN** `DslError` is raised naming the topology and the pin `U1-1`

### Requirement: Bridges through series parts
A bridge SHALL join two pins of one part in a topology, declared by `design.bridge(part, a, b, *, delay=None, loss=None)` or by the `bridges` table of the part's device record. A series part between two chains without a bridge MUST give `topology.bridge-missing` (error) at build.

#### Scenario: A missing bridge
- **GIVEN** the example with `R1` built from a part without a device and no `design.bridge`
- **WHEN** `uv run pytest tests/unit/dsl/test_topology.py -k bridge_missing` builds it
- **THEN** the exit code is 5 and one `topology.bridge-missing` names `R1`

### Requirement: Delay and loss along a path
The stage `topology.rules` SHALL compute a path's delay as the sum, along the shortest copper path between the two pads and through the bridges, of each segment's `length_nm * per_mm_fs / 10^6`, each via's and bridge's delay and each pad's die delay, rounding each segment up for a `max` and down for a `min`; and a path's loss likewise from the loss inputs, rounding up.

#### Scenario: Hand-computed delay
- **GIVEN** an authored bench with a 30 mm `F.Cu` track, one via and a 20 mm `In1.Cu` track from `U1-1` to `U2-1`, `F.Cu` at 5 900 fs/mm, `In1.Cu` at 6 900 fs/mm and vias at 10 000 fs
- **WHEN** `uv run pytest tests/unit/checks/test_topology_stage.py -k delay` judges `delay(max=ps(400))`
- **THEN** the delay is 325 000 fs and no issue is given, and with `max=ps(300)` one `topology.delay-out-of-range` error names 325 000 fs and 300 000 fs

### Requirement: Skew, stubs and order
The stage SHALL judge `skew(*ends, max=)` as each end's delay from the root less the longest, `stub(max=)` as the copper length of each branch that leaves a tree path and ends at no listed pin, and `order()` as whether the copper path from the root visits each chain's pins in chain order.

#### Scenario: Loads out of order
- **GIVEN** the example routed so that the copper reaches `U3` before `U2`
- **WHEN** `uv run pytest tests/unit/checks/test_topology_stage.py -k order` runs the stage
- **THEN** one `topology.order` error names `U2-CLK` and `U3-CLK`

### Requirement: Protocol constraint objects
`fenolite.dsl.protocol` SHALL provide frozen records of named limits (`Usb2`, `Clock`) that `design.constrain(target, obj)` binds to an interface or topology of their kind and expands into topology constraints and `rules.pair` rules. A record MUST have no default limit, and binding it to another kind MUST raise `DslError`.

#### Scenario: Kind checked
- **WHEN** `uv run pytest tests/unit/dsl/test_protocol.py` binds `protocol.Usb2(skew_max=ps(10))` to an `I2C` interface, and then to a `USB2` interface
- **THEN** the first raises `DslError`, and the second adds a `skew` constraint judged by `topology.rules` and, since the pair's layers share one propagation value, the lowered rule `pair:<name>:skew`
