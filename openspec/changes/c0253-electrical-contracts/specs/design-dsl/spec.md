## ADDED Requirements

### Requirement: Electrical contracts in the DSL
`Design` SHALL offer `derating(*, parts=None, source="", **keys)`, `operating(*, ambient)`, `expect(test, reason)` and `rig(*elements)`, and the block builder of c0251 SHALL offer `expect(test, reason)`. The calls MUST record plain data, which the build stores in `RuleSet.contracts`. A bad key or unit, or a repeated name, MUST raise `DslError`.

#### Scenario: Contracts are built
- **GIVEN** the script `examples/circuit/sensor/good.py`, which calls `design.derating(capacitor_voltage=pct(50))`, `design.rig(supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench"))` and one `b.expect(...)` in its buck block
- **WHEN** `uv run pytest tests/unit/dsl/test_contracts.py -k build` builds it
- **THEN** `.fenolite/rules.json` holds under `contracts` one derating rule with `permille` 500, one rig supply `bench` from 10.8 V to 13.2 V, and one expectation with the id `buck/expect#1`

### Requirement: Contract helpers in the DSL
`fenolite.dsl` SHALL export `within`, `at_least`, `at_most`, `value_of`, `rating_of`, `voltage_of`, `current_of`, `supply`, `sink`, `celsius` and `kelvin`. A derating ratio (c0246's `pct()`) MUST be stored as whole per-mille, a temperature difference as whole millikelvin, a temperature as exact decimal degrees Celsius, and a range as c0246 stores it. A value that is not whole in its stored unit, or a float, MUST raise `DslError`.

#### Scenario: A ratio that is not whole per-mille
- **WHEN** a script calls `design.derating(resistor_power=pct("50.05"))`
- **THEN** `DslError` names `resistor_power` and says that a derating is stored in whole per-mille

#### Scenario: Helpers are exported
- **WHEN** `uv run pytest tests/unit/dsl/test_contracts.py -k exports` reads `fenolite.dsl.__all__`
- **THEN** it holds the eleven names, and each of them appears in a `fenolite-design` block of the agent guide
