## ADDED Requirements

### Requirement: Requirement table in the roles command
`fenolite roles PATH --check` SHALL add `result.requirements`: the rows of the role checks and, when `PATH` is a project that Fenolite built, the rows of `fenolite.checks.circuit` on its `.fenolite/` model, sorted by `id`. Without `--check` the result MUST NOT hold `requirements`. The command MUST stay read-only. `docs/cli-contract.md` MUST describe the row under the heading `roles`.

#### Scenario: One table for roles and circuit
- **GIVEN** the `bad` variant of `examples/circuit/sensor` built in `tmp_path`, whose script declares the role of `SW` with `current=amp("1.5")`
- **WHEN** `uv run pytest tests/unit/cli/test_roles_cmd.py -k requirements` runs `fenolite roles <dir> --check --json`
- **THEN** `result.requirements` holds the row `circuit.rating-current:L1:current` with value source `user` (basis `rail 3V3`) and limit source `device`, and the role rows of `SW`, each with a source of `device`, `role`, `policy` or `user`, and the folder is unchanged

#### Scenario: A board that Fenolite did not build
- **WHEN** `fenolite roles tests/data/kicad/board/two_layer.kicad_pcb --check --json` runs
- **THEN** `result.requirements` holds only role rows, and the exit code is 0

### Requirement: Requirements file bounds both kinds of row
A `[[current]]` row of `fenolite roles --check --requirements FILE` SHALL bound the current of its nets for the role rows and for the circuit rows alike, with source `user` and, as basis, the row's `source` text or `requirements.toml`. As for roles, a row bounds a net only when no rig, rail or stated role does.

#### Scenario: A stated current reaches the circuit rows
- **GIVEN** the `bad` variant of `examples/circuit/sensor` without its role declaration of `SW`, built in `tmp_path`, and a requirements file with `[[current]]` `select = { net = "SW" }`, `current = "0.8A"`, `temp_rise = "10K"`, `source = "bench note"`
- **WHEN** `fenolite roles <dir> --check --requirements <file> --json` runs
- **THEN** the row `circuit.rating-current:L1:current` has the value 0.8 A with source `user` and basis `bench note`, and status `pass`
