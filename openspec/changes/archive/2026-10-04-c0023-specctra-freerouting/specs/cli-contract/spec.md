## ADDED Requirements

### Requirement: Freerouting in doctor
`fenolite doctor` SHALL report, in the `freerouting` entry of `result.routers`, the jar path, the version, `java_major` and `java_ok` (`java_major >= 25`). A jar without a suitable Java MUST give `doctor.tool-unsupported` (warning) naming Java 25, and a missing jar `doctor.tool-missing`. `fenolite capabilities` MUST list `freerouting` with the plugin's `sends_data_offsite` value, and `result.sends_data_offsite` MUST stay `false`, because the router runs only when named and, while it sends data, only with `--allow-offsite`.

#### Scenario: Jar with an old Java
- **GIVEN** `FENOLITE_FREEROUTING_JAR` naming an existing file and a fake `java` that prints `17.0.2`
- **WHEN** `uv run pytest tests/unit/cli/test_doctor_cmd.py -k freerouting` runs `fenolite doctor --json`
- **THEN** the entry has `java_major: 17` and `java_ok: false`, one `doctor.tool-unsupported` warning names Java 25, and the exit code is 0

#### Scenario: Refused without the flag
- **GIVEN** the plugin with `sends_data_offsite` `True` and a fake jar
- **WHEN** `fenolite route <board> --router freerouting --dry-run` runs
- **THEN** the exit code is 2 and the hint names `--allow-offsite`
