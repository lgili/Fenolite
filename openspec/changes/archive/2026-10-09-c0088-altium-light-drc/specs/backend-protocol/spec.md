## MODIFIED Requirements

### Requirement: Design rules source
`fenolite.backends.base` SHALL define the frozen dataclass `DesignRules(design: Design, min_clearance: Nm | None = None, rules_over_classes: bool = True, floor_over_rules: bool = False, opaque_clearance_rules: int = 0, unread: tuple[tuple[str, str], ...] = (), evidence: Evidence = Evidence(), left_out: tuple[tuple[str, int, str], ...] = ())` and the `@runtime_checkable` protocol `DesignRulesSource` with the method `design_rules(design: Design, project: ProjectSet, *, issues: list[Issue] | None = None) -> DesignRules`. Through it, `checks` reaches the clearance rules that a project's own files hold, without importing a backend.
- `DesignRules.design` MUST be `design` with the net classes, the class of each net and the design rules that the project's files give; what a missing or unread file would give MUST keep `design`'s own value.
- `min_clearance` MUST be the project's board minimum clearance in nm, or `None`. `rules_over_classes` and `floor_over_rules` MUST say, for the tool version the board is judged against, whether a governing custom clearance rule replaces the class clearances and whether the board minimum also raises rule values (`copper-check`, "Clearance in force"). `opaque_clearance_rules` MUST count the project's clearance rules that could not be lifted into the model. `unread` MUST name each project file that failed to read, with the error's message, in file-name order.
- `left_out` MUST name the copper that the project's files hold in a form the model does not carry as copper, as (kind, count, reason) in kind order; `DesignRules.design` is then without the items that stand for it, and `checks.copper.rules_issues` MUST give one `copper.item-unsupported` per entry, `where` = the kind. It is empty for a KiCad project.
- `design_rules` MUST NOT raise for a file that fails to read, and MUST append the readers' warnings and infos to `issues` when a list is given.
- `design_rules` is not an operation: `CapabilityReport.operations` stays the closed list of "Capability reports".
- `KicadBackend` MUST satisfy `DesignRulesSource` (`kicad-file-backend`, "Design rules for the copper check"), and `backends/kicad/backend.py` MUST hold the statement `_RULES_SOURCE: DesignRulesSource = KicadBackend()`, which pyright checks.
- `backends.base` MUST still import only `core` and `model`.

#### Scenario: KiCad backend is a rules source
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k rules_source` checks `isinstance(KicadBackend(), DesignRulesSource)` and `KicadBackend().capabilities().operations`
- **THEN** the first is true, and the operations do not name `design_rules`

#### Scenario: Unread file reported, not raised
- **GIVEN** a project set whose `<stem>.kicad_pro` holds the text `{`
- **WHEN** `KicadBackend().design_rules(design, project)` is called
- **THEN** no exception is raised, `unread` holds one entry naming `<stem>.kicad_pro`, and `DesignRules.design.circuit.netclasses` equals `design.circuit.netclasses`

#### Scenario: Base module stays neutral
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k base_imports` runs
- **THEN** it passes, `backends/base.py` importing only `core` and `model`

## ADDED Requirements

### Requirement: Document parity protocol
`fenolite.backends.base` SHALL define the `@runtime_checkable` protocol `DocumentParity` with the method `parity_side(schematic: Design, board: Design) -> SideOutcome`: a document backend builds the schematic side of the parity comparison (`checks.parity`) from the two readings that `DocumentValidator.read_documents` gave. It MUST read no file and run no tool; `side` is `None` when the schematic reading gives no side, with a `message`.
- `ParityInputs` is unchanged: it serves a backend that reads the schematic of a `ProjectSet` itself and may take an oracle's netlist. A document backend has both readings already, so it is not asked to read them again.
- `AltiumBackend` MUST satisfy `DocumentParity`, `BoardFrame` and `DesignRulesSource`, and `backends/altium/backend.py` MUST hold the three statements that pyright checks. None of the three is an operation: `CapabilityReport.operations` of the Altium backend stays `("detect", "read")`.

#### Scenario: Altium backend satisfies the three protocols
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k backend_is` checks `isinstance(AltiumBackend(), …)` for `BoardFrame`, `DesignRulesSource` and `DocumentParity`
- **THEN** each is true, and the operations are `("detect", "read")`
