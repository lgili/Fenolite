## ADDED Requirements

### Requirement: Schematic netlist oracle
`fenolite.backends.base` SHALL define `SchematicNetlistOracle`, a `@runtime_checkable` `typing.Protocol` with `name: str`, `version() -> str` and `schematic_netlist(project: ProjectSet) -> NetlistOutcome`, through which `checks` asks an external tool for the netlist of a project's schematic without importing a backend.
- The `NetlistOutcome` is the type of "Netlist and round-trip oracles". Its `PadNetList` MUST have the source `schematic` and one `PadAssignment(f"{ref}-{pin}", <net name>)` per pin the tool lists; a pin the tool does not list is not an element.
- `netlist` MUST be `None` when the tool wrote no export, and `message` MUST then be the first sanitised line of the tool's output or of the parse error.
- `schematic_netlist` MUST NOT write under `project.root`, and MUST return `outcome == "timeout"` instead of raising when the tool times out.
- c0013's `Oracle` protocol is unchanged: a caller narrows with `isinstance(oracle, SchematicNetlistOracle)`. `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy the protocol, and the typed function of `oracle.py` that returns a `KicadOracle` as each protocol MUST cover it.

#### Scenario: KiCad oracle satisfies the protocol
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error for the typed function that returns a `KicadOracle` as `SchematicNetlistOracle`

#### Scenario: Narrowing
- **GIVEN** a fake `Oracle` in `tests/unit/checks/fakes.py` that implements `name`, `version`, `drc` and `netlist`
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k schematic_netlist` checks it
- **THEN** `isinstance(fake, SchematicNetlistOracle)` is false, and it is true for a fake that also implements `schematic_netlist`

#### Scenario: Base stays backend-free
- **WHEN** `uv run pytest tests/unit/test_import_graph.py tests/unit/checks` runs
- **THEN** both pass, and `fenolite.backends.base` imports no `fenolite.backends.<x>` module
