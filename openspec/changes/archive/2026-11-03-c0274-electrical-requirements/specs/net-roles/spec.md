## MODIFIED Requirements

### Requirement: Part classes
`fenolite.roles.classify`, the one classifier of the package tree, SHALL give each component one class of `transistor`, `diode`, `inductor`, `capacitor`, `resistor`, `shunt`, `ferrite`, `fuse`, `jumper`, `driver`, `amplifier`, `controller`, `connector`, `net_tie` or `other`, with its terminal map and a confidence, weighing: the user's class, the device's `class`, pin names, pin types, the prefixes `FB`, `F` and `JP` (`medium`), the value or pad count, other prefixes (`low`).

#### Scenario: Classes from pin names
- **GIVEN** an authored circuit with a part `Q7` whose pins are named `G`, `D`, `S` and `KS`, and a part `X1` whose pins are `IN+`, `IN-`, `OUT`
- **WHEN** `uv run pytest tests/unit/roles/test_classify.py` classifies them
- **THEN** `Q7` is `transistor` with `kelvin_source` on `KS`, `X1` is `amplifier`, both `high`

#### Scenario: A ferrite, a fuse and a jumper
- **GIVEN** an authored circuit with `FB1` of value `600R`, `F1` of value `2A` and `JP1` with no value, none of them stated by the user
- **WHEN** `uv run pytest tests/unit/roles/test_classify.py -k prefixes` classifies them
- **THEN** `FB1` is `ferrite`, `F1` is `fuse` and `JP1` is `jumper`, each `medium`, and the inferred roles of the six variants of `examples/roles` are those that `H-G-ROLE-INFER` records

## ADDED Requirements

### Requirement: Safe resistance prefixes
The role classifier MUST accept K as k and Greek micro as the micro sign in resistance values, preserve the distinct m and M scales, and return None for an unmapped matched prefix instead of raising an internal error. Parsing SHALL remain exact.

#### Scenario: Prefix spelling cannot crash a build
- **WHEN** authored resistor values are classified by `uv run pytest tests/unit/roles/test_classify.py -q`
- **THEN** 10K equals 10k, 10m differs from 10M, Greek micro is read exactly, and unsupported matched prefixes yield None
