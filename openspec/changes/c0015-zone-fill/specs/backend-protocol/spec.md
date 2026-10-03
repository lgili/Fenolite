## ADDED Requirements

### Requirement: Fill oracle protocol
`fenolite.backends.base` SHALL define the neutral types through which `checks` and the CLI ask an external tool for zone fills:
- `ZoneFills(zone_id: str, fills: tuple[ZoneFill, ...], filled: bool)`;
- `FillOutcome(zones: tuple[ZoneFills, ...] | None, tool_version: str, outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", supported: bool = True, evidence: Evidence = Evidence())`. `supported` MUST be false, with `zones` `None` and no run, when the tool cannot refill; `zones` MUST be `None` when no refilled board could be read;
- `FillOracle`, a `typing.Protocol` with `name: str` and `refill(project: ProjectSet) -> FillOutcome`. `refill` MUST NOT write under `project.root` and MUST report a timeout as `outcome == "timeout"`.

These types MUST be frozen dataclasses. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy `FillOracle`.

#### Scenario: KiCad oracle is a fill oracle
- **GIVEN** the call of `run_checks` in `cli/cmd_check.py`, whose `fill_oracle` parameter is typed `FillOracle | None`, passing a `KicadOracle`
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error

#### Scenario: Unsupported tool makes no run
- **GIVEN** a fake `kicad-cli` whose `version` prints `9.0.9`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle.py -k refill_unsupported` calls `KicadOracle.refill`
- **THEN** the outcome has `supported == False` and `zones is None`, and the fake recorded only the `version` call

#### Scenario: Outcome is immutable
- **WHEN** code assigns `outcome.supported = True` on a `FillOutcome`
- **THEN** a `FrozenInstanceError` is raised
