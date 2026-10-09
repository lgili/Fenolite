## ADDED Requirements

### Requirement: Private state per kicad-cli run
Every `KicadCli.run` SHALL run `kicad-cli` with the variables of `private_state(<run folder>/.fenolite-state)` (`cli.STATE_VARIABLES`: owner-only temporary, runtime, cache and state folders; S-0703, S-0704, S-0705), applied before `KICAD_CONFIG_HOME`, `LANG`, `LC_ALL` and `env`, so that parallel runs share no instance lock (`H-K-CLI-STATE`).

#### Scenario: A run sees its own folders
- **GIVEN** a fake `kicad-cli` that records six variables and the mode of each folder, and a caller environment where all six name `/shared`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_runner.py -k private_state` runs a command
- **THEN** each variable names its folder under `<tmp>/.fenolite-state/` with mode 0700, and a file the fake writes there is not in `outputs`

#### Scenario: Parallel runs
- **GIVEN** the same fake `kicad-cli`
- **WHEN** eight runs start at once
- **THEN** their `TMPDIR` values are eight different folders, none of which exists afterwards

### Requirement: Reserved state folder
`.fenolite-state` SHALL be a reserved name like `config` (`cli.RESERVED_DIRS`): `KicadCli.run` MUST refuse it as a run file name and never report a file under it as an output, and the copy set of a check MUST skip it as `reserved-name`. The runner MUST NOT change `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME` or `XDG_DATA_DIRS`.

#### Scenario: A library row in the state folder
- **GIVEN** a project whose `fp-lib-table` names `${KIPRJMOD}/.fenolite-state/Z.pretty`
- **WHEN** `project_set` plans the copy set
- **THEN** the row is skipped as `reserved-name` and the folder is not copied

### Requirement: Docker runs keep the caller's state
`DockerCli` SHALL pass no private state: each container (`--rm`) has its own `/tmp`, and the `docker` client MUST keep the caller's environment, `XDG_RUNTIME_DIR` included, with the container command unchanged.

#### Scenario: Docker keeps the caller's runtime folder
- **GIVEN** a fake `docker` and a caller with `XDG_RUNTIME_DIR=/run/user/1000`
- **WHEN** `DockerCli(image).version()` runs
- **THEN** the `docker` client sees `XDG_RUNTIME_DIR=/run/user/1000`, and the command's `-e` entries are `KICAD_CONFIG_HOME=/w/config`, `LANG=C` and `LC_ALL=C` only

### Requirement: Oracle tests run kicad-cli with private state
The tests' own `kicad-cli` launchers (`tests/_kicad.py`, `tests/_libs.py`, and every oracle that builds its environment with `_kicad.oracle_env`) SHALL give each call private folders made by `private_state`, removed afterwards, and `tests/kicad/check/test_parallel_runs_oracle.py` SHALL run `kicad-cli` in parallel in the `kicad-9` and `kicad-10` jobs.

#### Scenario: Parallel runs of the real tool
- **GIVEN** `kicad-cli` 9.0.9 or 10.0.6
- **WHEN** `uv run pytest tests/kicad/check/test_parallel_runs_oracle.py` runs eight `version` runs, eight `sch erc` runs of an unloadable schematic, and eight raw helper runs at once
- **THEN** every run gives its usual result (each ERC run "Failed to load schematic", exit 3, no report) and none prints a lock message, and a run given `TMPDIR` creates `org.kicad.kicad/instances` in that folder
