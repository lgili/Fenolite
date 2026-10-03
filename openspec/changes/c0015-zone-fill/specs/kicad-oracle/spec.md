## ADDED Requirements

### Requirement: Refill through kicad-cli 10
`KicadCli.refill(board, *, files=None) -> RefillRun` SHALL run `pcb drc --format json --severity-all --refill-zones --save-board -o drc.json <board>` through the package runner, on copies, and SHALL return the run and the saved board bytes (`None` when the board is not among `CliRun.outputs`).
- It MUST raise `KicadCliVersionError` (`FEN-6002`) for a major below 10, before any run, because 9.0 has neither option (`H-K-01`).
- `KicadOracle.refill(project)` MUST pass `project.files` without the board key and MUST NOT stage the canary.
- `H-K-FILL-SAVE` and `H-K-FILL-REPEAT` MUST be settled on 10.0.6 before `fill.py` relies on them, as the probes `fill-save-t9`, `fill-save-t10` and `fill-repeat`.

#### Scenario: Saved board in the outputs
- **GIVEN** the authored project for targets 9 and 10
- **WHEN** `uv run pytest tests/kicad/fill/test_fill_probes.py::test_save` runs on 10.0.6
- **THEN** each run returns a saved board whose zone ids equal the original's and whose `GND` zone has at least one fill, and the probes record `present`

#### Scenario: Refill refused on 9.0
- **WHEN** `KicadCli.refill` is called with `kicad-cli` 9.0.9
- **THEN** `KicadCliVersionError` is raised and no `pcb drc` run happens

#### Scenario: Repeatable
- **WHEN** `uv run pytest tests/kicad/fill/test_fill_probes.py::test_repeat` refills the authored project and the built blink three times each on 10.0.6
- **THEN** the fills are equal across the runs and the probe `fill-repeat` records `equal`

### Requirement: Lifted fills pass the oracle
Boards written by `fill_board` SHALL be proved on `kicad-cli`:
- on 10.0.6, a second refill of the written board MUST give the fills that were lifted, for targets 9 and 10 (`H-K-FILL-LIFT`; probes `fill-lift-t9`, `fill-lift-t10` = `equal`);
- on 9.0.9, `tests/data/kicad/fill/triad_t9_filled.kicad_pcb` MUST load, and the violation types of its DRC report MUST differ from those of `triad_t9.kicad_pcb` at most by `isolated_copper` (`H-K-FILL-LOAD9`; probe `fill-load9` = `load`);
- a blink filled, then rebuilt without a change, MUST keep its fills, and a refill of the rebuilt board MUST give equal fills (`H-K-LENS-FILL`; probe `fill-kept` = `equal`).

The committed fixtures MUST be regenerated on 10.0.6 by `test_fixture_is_current` and compared.

#### Scenario: Second refill reproduces the lift
- **WHEN** `uv run pytest tests/kicad/fill/test_fill_probes.py::test_lift` runs on 10.0.6
- **THEN** both probes record `equal`

#### Scenario: Target-9 fills load on 9.0
- **WHEN** `uv run pytest tests/kicad/fill/test_fill_probes.py::test_load9` runs in the pinned 9.0.9 image
- **THEN** the probe records `load` and the type sets differ at most by `isolated_copper`

#### Scenario: Kept fill matches a refill
- **WHEN** `uv run pytest tests/kicad/fill/test_fill_oracle.py::test_kept_fill_matches_refill` runs on 10.0.6
- **THEN** the rebuilt blink keeps its fills, a refill gives equal fills, and after a class clearance change the rebuild reports `zone.fill-stale`

### Requirement: Container runner
`fenolite.backends.kicad.cli.DockerCli` SHALL run `kicad-cli` inside a container image with the same contract as `KicadCli.run`: inputs copied to a fresh temporary directory, that directory mounted as the working directory, the isolated environment, and the created or changed files returned.
- The command MUST be `docker run --rm --platform linux/amd64 -v <tmp>:/w -w /w -e KICAD_CONFIG_HOME=/w/config -e LANG=C -e LC_ALL=C <image> kicad-cli <args>`.
- `find_kicad_cli` MUST accept `docker:<image>` as its explicit value and as `FENOLITE_KICAD_CLI`, and `cli_for(path, *, timeout)` MUST return a `DockerCli` for it and a `KicadCli` otherwise.
- Fenolite MUST NOT pull an image. A failing `docker run` for `version` MUST surface as `FEN-6001` with a hint naming `docker pull <image>`.

#### Scenario: Fake docker
- **GIVEN** a fake `docker` on `PATH` that records its arguments and runs the fake `kicad-cli` in the mounted folder
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_docker_cli.py` runs `cli_for("docker:img:1", timeout=60).run(["version"], files={})`
- **THEN** the recorded arguments hold `--rm`, `-v <tmp>:/w`, `-w /w`, `img:1`, `kicad-cli` and `version`, and the run's stdout is the fake's version

#### Scenario: Container equals local
- **GIVEN** Docker and the pinned 10.0.6 image present locally
- **WHEN** `uv run pytest tests/kicad/fill/test_docker_cli.py::test_container_matches_local` runs
- **THEN** `fill_board` through `DockerCli` gives the text it gives through the local binary; without Docker the test is skipped with that reason
