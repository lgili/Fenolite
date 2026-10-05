## ADDED Requirements

### Requirement: Neutral ERC report
`fenolite.backends.base` SHALL provide the frozen dataclasses `ErcItem(uuid, description, position, where="")`, `ErcViolation(type, description, severity, items, excluded=False, sheet="", sheet_id="")` and `ErcReport(source, date, kicad_version, coordinate_units, violations, ignored_checks=(), included_severities=(), sheets=())`.
- `position` MUST be a `Point` in integer nanometres on the sheet, and `ErcItem` MUST raise `TypeError` for a coordinate that is not an `int`. `where` is the location a backend found for the item (`REF-PIN`, `REF` or a label text), or `""`.
- `type` and `severity` MUST be the tool's own strings. `sheet` MUST be the tool's readable path of the sheet the violation is listed under, and `sheet_id` the tool's own identifier of that sheet (for KiCad its path of uuids), by which a backend finds the reference a symbol has there. Violations MUST keep report order, sheet by sheet. `ErcReport.sheets` MUST hold the readable path of every sheet the report lists, with or without violations, in report order.
- `ErcReport.of_type(type)` MUST return the violations of that type, in report order.
- `ErcReport.entries()` MUST return the violations as a sorted tuple of `(sheet, type, severity, excluded, items)`, each item as `(description, x, y)`, leaving out uuids, `where`, `sheet_id` and the report order, so that two runs of a tool can be compared.
- `fenolite.backends.base` MUST NOT import any `fenolite.backends.<x>` module.

#### Scenario: Violations by type
- **GIVEN** an `ErcReport` with two `pin_not_connected` violations and one `lib_symbol_issues` violation
- **WHEN** `report.of_type("lib_symbol_issues")` is called
- **THEN** it returns the one violation

#### Scenario: Entries leave out uuids and order
- **GIVEN** two reports holding the same two violations in another order and with other item uuids
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k erc_entries` compares `entries()`
- **THEN** they are equal, and a report with one violation fewer gives other entries

#### Scenario: Integer positions only
- **WHEN** `ErcItem(uuid="u", description="d", position=Point(1.5, 0))` is constructed
- **THEN** a `TypeError` is raised

### Requirement: ERC oracle protocol
`fenolite.backends.base` SHALL define the neutral types through which `checks` asks an external tool for an ERC verdict, without importing a backend:
- `ErcOutcome(report: ErcReport | None, tool_version: str, tool_writes: tuple[str, ...] = (), outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence())`. `report` MUST be `None` when the tool wrote no report, and `message` MUST then be the first sanitised line of the tool's output.
- `ErcRt2Outcome(before: tuple[ErcReport, ...], after: ErcReport | None, tool_version: str, outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence(), redumped: int = 0, kept: int = 0)`: the reports of the runs on the project as it is, the report of the run on the re-dump, and the numbers of sheet files re-dumped and left as they are.
- `ErcOracle`, a `@runtime_checkable` `typing.Protocol` with `name: str`, `version() -> str` and `erc(project: ProjectSet) -> ErcOutcome`.

The types MUST be frozen dataclasses. `erc` MUST NOT write under `project.root` and MUST return `outcome == "timeout"` instead of raising when the tool times out. c0013's `Oracle` protocol is unchanged: a caller narrows an `Oracle` with `isinstance(oracle, ErcOracle)`. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy `ErcOracle`, and the typed function of `oracle.py` that returns a `KicadOracle` as each protocol (`_protocols`, now a tuple of four) MUST cover it.

#### Scenario: KiCad oracle satisfies the protocol
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error for the typed function that returns a `KicadOracle` as `ErcOracle`

#### Scenario: Narrowing a drc-only oracle
- **GIVEN** a fake `Oracle` in `tests/unit/checks/fakes.py` that implements only `name`, `version` and `drc`
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k erc_protocol` checks it
- **THEN** `isinstance(fake, ErcOracle)` is false, and it is true for a fake that also implements `erc`

#### Scenario: Outcome is immutable
- **GIVEN** `ErcOutcome(report=None, tool_version="10.0.6")`
- **WHEN** code assigns `outcome.message = "x"`
- **THEN** a `FrozenInstanceError` is raised

## MODIFIED Requirements

### Requirement: Oracle protocol
`fenolite.backends.base` SHALL define the neutral types through which `checks` asks an external tool for a DRC verdict:
- `SkippedFile(name: str, reason: Literal["outside-root", "variable", "relative", "missing", "nested-table", "too-large", "reserved-name"])`.
- `ProjectSet(root: Path, board: str, files: Mapping[str, Path], skipped: tuple[SkippedFile, ...] = (), has_project: bool = False, has_rules: bool = False)`. `files` MUST map POSIX names relative to `root` to source paths, and `board` MUST be a key of `files`; construction MUST raise `ValueError` otherwise.
- `CanaryState = Literal["fired", "absent", "inconclusive", "not-applicable"]`.
- `DrcOutcome(report: DrcReport | None, tool_version: str, canary: CanaryState, canary_reason: str = "", canary_removed: int = 0, tool_writes: tuple[str, ...] = (), outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence(), parity_judged: bool = False)`. `report` MUST be `None` when the tool wrote no report, and MUST otherwise hold no violation or unconnected item that names a canary uuid. `message` MUST be the first sanitised line of the tool's stderr; when the run asked for the comparison with the schematic and the tool did not make it, it MUST be the line the tool gave for that. `parity_judged` MUST be true exactly when the run asked the tool to compare the board with its schematic and the tool did so.
- `Oracle`, a `typing.Protocol` with `name: str`, `version() -> str` and `drc(project: ProjectSet) -> DrcOutcome`. `drc` MUST NOT write under `project.root`, and MUST return `outcome == "timeout"` instead of raising when the tool times out.

These types MUST be frozen dataclasses. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy `Oracle` with `name == "kicad"`.

#### Scenario: KiCad oracle satisfies the protocol
- **GIVEN** the call of `run_checks` in `cli/cmd_check.py`, whose `oracle` parameter is typed `Oracle | None`, passing `KicadOracle(KicadCli(path, timeout=…))`
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error

#### Scenario: Board outside the files
- **WHEN** `ProjectSet(root=Path("p"), board="a.kicad_pcb", files={})` is constructed
- **THEN** a `ValueError` naming `a.kicad_pcb` is raised

#### Scenario: Fake oracle without a backend
- **GIVEN** a fake `Oracle` defined in `tests/unit/checks/`, which imports only `fenolite.backends.base`
- **WHEN** `uv run pytest tests/unit/checks tests/unit/test_import_graph.py` runs
- **THEN** both pass, and `fenolite.backends.base` imports no `fenolite.backends.<x>` module

#### Scenario: Outcome is immutable
- **GIVEN** `DrcOutcome(report=None, tool_version="10.0.6", canary="not-applicable")`
- **WHEN** code assigns `outcome.canary = "fired"`
- **THEN** a `FrozenInstanceError` is raised

#### Scenario: Parity flag defaults to false
- **WHEN** `DrcOutcome(report=None, tool_version="10.0.6", canary="not-applicable")` is constructed
- **THEN** its `parity_judged` is `False`
