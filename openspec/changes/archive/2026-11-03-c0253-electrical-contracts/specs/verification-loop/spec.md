## ADDED Requirements

### Requirement: Contracts in the circuit stage
The stage `circuit.rules` of c0252 SHALL also judge the contracts of `electrical-contracts`: ratings, operating ranges, the policy, expectations and the rig. Its summary MUST hold `requirements` and `halves.contracts` (`ran` or `no-contracts`, the latter when the model has no `fenolite.device` component, expectation or rig element). The stage MUST be skipped with `no-parameters` only when `no-contracts` holds too. Its place, name, skip `no-model` and tool-free run stay c0252's.

#### Scenario: A failing rating gates the check
- **GIVEN** the `bad` variant of `examples/circuit/sensor` built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_stage.py -k gate` runs `fenolite check <dir> --stages model.validate,circuit.rules --json`
- **THEN** the stage `circuit.rules` has status `errors`, the issues hold `circuit.rating-voltage` as an error, its summary holds `requirements`, and the exit code is 5

#### Scenario: Contracts alone run the stage
- **GIVEN** a built design with one device part and one expectation, and no rail, port or interface parameter
- **WHEN** `fenolite check <dir> --stages circuit.rules --json` runs
- **THEN** the stage is not skipped, its summary holds the expectation's row, and `summary.halves` is `{"contracts": "ran", "rails": "no-parameters"}`

#### Scenario: A board without a model is unchanged
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages circuit.rules --json` runs
- **THEN** the stage is `skipped` with c0252's reason `no-model`, and the exit code is 0

### Requirement: Device records injected into the circuit stage
`cmd_check`, `cmd_build` and `cmd_roles` SHALL resolve each component's `fenolite.device` through the catalog and the project's records (c0248) and classify the parts with `fenolite.roles.classify`, and SHALL pass both to `circuit_issues(model, *, devices=..., classes=...)` and the stage. `checks` MUST NOT import `catalog` or `roles`. Without `devices`, rating rows MUST be `unknown`; without `classes`, class-specific rows MUST be `unknown`.

#### Scenario: A fake mapping
- **GIVEN** the `bad` variant built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_stage.py -k injected` calls `run_checks` with `stages=("circuit.rules",)` once with the resolved devices and once with none
- **THEN** the first gives the four designed findings, and the second gives no `circuit.rating-*` finding and one `circuit.rating-missing` info
