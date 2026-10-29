## ADDED Requirements

### Requirement: Contracts in the circuit stage
The stage `circuit.rules` of c0252 SHALL also judge the electrical contracts of `electrical-contracts`: ratings, the derating policy, expectations and the rig. Its summary MUST hold `requirements`, the rows of the requirement table. Its skip `no-parameters` MUST NOT apply when the model holds a component with a `fenolite.device` property, an expectation or a rig element. Its place, its name, its skip `no-model` and its tool-free run MUST stay as c0252 defines them.

#### Scenario: A failing rating gates the check
- **GIVEN** the `bad` variant of `examples/circuit/sensor` built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_stage.py -k gate` runs `fenolite check <dir> --stages model.validate,circuit.rules --json`
- **THEN** the stage `circuit.rules` has status `errors`, the issues hold `circuit.rating-voltage` as an error, its summary holds `requirements`, and the exit code is 5

#### Scenario: Contracts alone run the stage
- **GIVEN** a built design with one device part and one expectation, and no rail, port or interface parameter
- **WHEN** `fenolite check <dir> --stages circuit.rules --json` runs
- **THEN** the stage is not skipped, and its summary holds the expectation's row

#### Scenario: A board without a model is unchanged
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages circuit.rules --json` runs
- **THEN** the stage is `skipped` with c0252's reason `no-model`, and the exit code is 0

### Requirement: Device records injected into the circuit stage
`cmd_check`, `cmd_build` and `cmd_roles` SHALL resolve the `fenolite.device` id of each component through the catalog and the project's device records (c0248), and SHALL pass them to `circuit_issues(model, *, devices=...)` and the stage as a mapping from device id to `DeviceDef`. `checks` MUST NOT import `catalog`. Without the mapping, the rating rows MUST be `unknown`.

#### Scenario: A fake mapping
- **GIVEN** the `bad` variant built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_stage.py -k injected` calls `run_checks` with `stages=("circuit.rules",)` once with the resolved devices and once with none
- **THEN** the first gives the four designed findings, and the second gives no `circuit.rating-*` finding and one `circuit.rating-missing` info
