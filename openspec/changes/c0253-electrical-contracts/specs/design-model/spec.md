## ADDED Requirements

### Requirement: Contracts in the model
`fenolite.model.rules` SHALL define the frozen value objects `DeratingRule`, `OperatingRange`, `Expectation`, `RigSupply`, `RigSink` and `ContractSet`, with the closed tables `DERATING_KEYS`, `EXPECT_OPS` and `EXPECT_REFS`. `RuleSet` SHALL gain `contracts: ContractSet | None`, stored in `rules.json` under `contracts` only when it is not empty. No float MAY be stored, and no backend lowers contracts.

#### Scenario: Contracts round trip
- **GIVEN** a design whose `RuleSet.contracts` holds a derating rule, an ambient range, an expectation `within(value(R1) * 2, [3 V, 4 V])` and a rig supply
- **WHEN** `uv run pytest tests/unit/model/test_rules.py -k contracts` writes it with `canonical.dump_dir` and loads it with `canonical.load_dir`
- **THEN** the loaded contracts equal the originals, and `rules.json` holds them under `contracts`

#### Scenario: Files of an older build
- **GIVEN** a `rules.json` written by 0.6.0
- **WHEN** it is loaded, validated against the regenerated schema and written again
- **THEN** `RuleSet.contracts` is `None` and the written bytes equal the input

### Requirement: Expectation trees in the model
An `Expectation` SHALL hold `id`, `block`, `reason`, `origin` and `test`. Its test MUST be a tree whose top operation is one of `within`, `at_least` and `at_most`, whose inner operations are `add`, `sub`, `mul`, `div` and `neg`, and whose leaves are c0246 ranges or refs (`value`, `rating` with an optional `pin`, `voltage`, `current`) naming entity ids. `origin` MUST be a module name and a line, never a file path.

#### Scenario: Refused values
- **WHEN** a `DeratingRule` with `permille` 0 or 1001, an `Expectation` whose top operation is `add`, an `Expectation` whose `origin` is an absolute path such as `C:/x/design.py:3`, and a `ContractSet` with two rig elements named `bench` are built
- **THEN** each raises `ValueError`
