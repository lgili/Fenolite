## ADDED Requirements

### Requirement: Netlist and round-trip oracles
`fenolite.backends.base` SHALL define the neutral types through which `checks` asks an external tool for its netlist export and for the reports of an RT2 run, without importing a backend:
- `PadAssignment(element: str, net: str)`: `element` is `REF-PIN` (a component reference, `-`, a pad or pin number); `net` is the source's own label for the element's net, `""` for no net.
- `Uncovered(element: str, reason: str)`: an element that a source names but does not assign, with the reason.
- `PadNetList(source: str, assignments: tuple[PadAssignment, ...], uncovered: tuple[Uncovered, ...] = ())`. Construction MUST raise `ValueError` when an element is both assigned and uncovered.
- `NetlistOutcome(netlist: PadNetList | None, tool_version: str, outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence())`. `netlist` MUST be `None` when the tool wrote no export, and `message` MUST then be the first sanitised line of the tool's stderr or of the parse error.
- `Rt2Outcome(before: tuple[DrcReport, ...], after: DrcReport | None, normalised: bool, tool_version: str, outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", evidence: Evidence = Evidence())`. `before` MUST hold the reports of the two runs on the original in run order, and fewer when a run wrote no report; `after` is the report of the run on the re-dump.
- `NetlistOracle`, a `@runtime_checkable` `typing.Protocol` with `name: str`, `version() -> str` and `netlist(project: ProjectSet, *, board: Design) -> NetlistOutcome`.
- `RoundTripOracle`, a `@runtime_checkable` `typing.Protocol` with `name: str`, `version() -> str` and `rt2(project: ProjectSet) -> Rt2Outcome`.

The types MUST be frozen dataclasses. `netlist` and `rt2` MUST NOT write under `project.root`, and MUST return `outcome == "timeout"` instead of raising when the tool times out. c0013's `Oracle` protocol is unchanged: a caller narrows an `Oracle` with `isinstance(oracle, NetlistOracle)` or `isinstance(oracle, RoundTripOracle)` before calling the new methods. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy `Oracle`, `NetlistOracle` and `RoundTripOracle`, and `oracle.py` MUST hold a typed function that returns a `KicadOracle` as each of the three, which `pyright` checks.

#### Scenario: KiCad oracle satisfies the three protocols
- **GIVEN** the typed function in `src/fenolite/backends/kicad/oracle.py` that returns a `KicadOracle` as `Oracle`, `NetlistOracle` and `RoundTripOracle`
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error

#### Scenario: Element assigned and uncovered
- **WHEN** `PadNetList(source="export", assignments=(PadAssignment("R1-1", "VIN"),), uncovered=(Uncovered("R1-1", "not-exported"),))` is constructed
- **THEN** a `ValueError` naming `R1-1` is raised

#### Scenario: Narrowing a drc-only oracle
- **GIVEN** a fake `Oracle` in `tests/unit/checks/fakes.py` that implements only `name`, `version` and `drc`
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k oracle_protocols` checks it
- **THEN** `isinstance(fake, NetlistOracle)` and `isinstance(fake, RoundTripOracle)` are false, and both are true for a fake that also implements `netlist` and `rt2`

#### Scenario: Base stays backend-free
- **WHEN** `uv run pytest tests/unit/test_import_graph.py tests/unit/checks` runs
- **THEN** both pass, and `fenolite.backends.base` imports no `fenolite.backends.<x>` module

#### Scenario: Outcomes are immutable
- **GIVEN** `Rt2Outcome(before=(), after=None, normalised=False, tool_version="9.0.9")`
- **WHEN** code assigns `outcome.normalised = True`
- **THEN** a `FrozenInstanceError` is raised
