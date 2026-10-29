## ADDED Requirements

### Requirement: Electrical contracts in the DSL
`Design` SHALL offer `derating(*, parts=None, source="", **keys)`, `operating(*, ambient)`, `contracts(*, unknown="info")`, `expect(test, reason)` and `rig(*elements)`, and the block builder of c0251 SHALL offer `expect(test, reason)`. The calls MUST record plain data, which the build stores in `RuleSet.contracts`. A bad key or unit, or a repeated name, MUST raise `DslError`.

#### Scenario: Contracts are built
- **GIVEN** the script `examples/circuit/sensor/good.py`, which calls `design.derating(capacitor_voltage=ratio(50))`, `design.rig(supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench"))` and one `b.expect(...)` in its buck block, used as `buck1`
- **WHEN** `uv run pytest tests/unit/dsl/test_contracts.py -k build` builds it
- **THEN** `.fenolite/rules.json` holds under `contracts` one derating rule with `permille` 500, one rig supply `bench` whose `voltage` is `{"high": {"e": -1, "m": 132}, "low": {"e": -1, "m": 108}, "nominal": {"e": 0, "m": 12}, "unit": "volt"}`, and one expectation with the id `buck1/expect#1`

### Requirement: Contract helpers in the DSL
`fenolite.dsl` SHALL export `within`, `at_least`, `at_most`, `value_of`, `rating_of`, `voltage_of`, `current_of`, `supply`, `sink` and `ratio`. A derating `ratio(p)` ("at most p % of the rating") MUST be stored as whole per-mille, a temperature margin (c0274's kelvin) as whole millikelvin, and every range as c0246 encodes it. A value that is not whole in its stored unit, a c0246 `pct()` given as a derating, or a float, MUST raise `DslError`.

#### Scenario: A ratio that is not whole per-mille
- **WHEN** a script calls `design.derating(resistor_power=ratio("50.05"))`
- **THEN** `DslError` names `resistor_power` and says that a derating is stored in whole per-mille

#### Scenario: Helpers are exported
- **WHEN** `uv run pytest tests/unit/dsl/test_contracts.py -k exports` reads `fenolite.dsl.__all__`
- **THEN** it holds the ten names, and each of them appears in a `fenolite-design` block of the agent guide
