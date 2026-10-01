## ADDED Requirements

### Requirement: Write capability fields
`fenolite.backends.base` SHALL provide the frozen dataclass `WriteResult(text: str, issues: tuple[Issue, ...] = ())`, the neutral result of a backend writer. A backend whose `CapabilityReport.write_kinds` is not empty MUST also report:
- `targets`: the tool versions it writes for, oldest first;
- `default_target`: the target used when the caller names none, which MUST be one of `targets`;
- `downgrade`: `"unsupported"` when a file read at a newer version cannot be written for an older target, or `"supported"`.

A backend that lists `"write"` in `operations` MUST have a non-empty `write_kinds` and MUST provide `write(design, *, target=None, allow_lossy=False) -> WriteResult`, which writes the design's board for `target` (`default_target` when `None`) and never writes a file. A backend with a non-empty `write_kinds` MUST list `"write"` in `operations`.

The KiCad backend MUST include `"kicad_pcb"` in `write_kinds`, MUST report `targets == (9, 10)`, `default_target == 10` and `downgrade == "unsupported"`, and MUST have `operations == ("detect", "read", "write")`. `KicadBackend.write` MUST return what `fenolite.backends.kicad.pcb.write_board` returns for the same arguments. Later writers add their kinds to the same tuple. These values replace the pre-writer values of c0009 (`write_kinds == ()`, `targets == ()`, `default_target is None`, `operations == ("detect", "read")`). `fenolite capabilities` MUST show them for the `kicad` entry of `result.backends`.

#### Scenario: KiCad write fields in capabilities
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the `kicad` entry of `result.backends` has `"kicad_pcb"` in `write_kinds`, `targets == [9, 10]`, `default_target == 10`, `downgrade == "unsupported"` and `operations == ["detect", "read", "write"]`

#### Scenario: Write operation advertised and implemented
- **GIVEN** `KicadBackend()` and the created test board `tests/_boards.py::created_board()`
- **WHEN** an agent finds `"write"` in `capabilities().operations` and calls `backend.write(design)`
- **THEN** it returns a `WriteResult` equal to `write_board(design, target=10)`, and `"lower"` and `"validate"` are still absent from `operations`

#### Scenario: Default target among the targets
- **GIVEN** every registered backend
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k capability` checks their reports
- **THEN** each backend with a non-empty `write_kinds` has `default_target in targets`

#### Scenario: Write result is immutable
- **GIVEN** `WriteResult(text="(kicad_pcb)\n")`
- **WHEN** code assigns `result.text = ""`
- **THEN** a `FrozenInstanceError` is raised

### Requirement: Neutral DRC report
`fenolite.backends.base` SHALL provide the frozen dataclasses `DrcItem(uuid, description, position)`, `DrcViolation(type, description, severity, items, excluded, comment)` and `DrcReport(source, date, kicad_version, coordinate_units, violations, unconnected_items, schematic_parity, ignored_checks, included_severities)`.
- `position` MUST be a `Point` in integer nanometres, and `DrcItem` MUST raise `TypeError` for a coordinate that is not an `int`.
- `type` and `severity` MUST be the tool's own strings, and violations MUST keep the order of the report.
- `DrcReport.of_type(type)` MUST return the violations, unconnected items and parity items whose `type` equals the argument, in report order.
- `fenolite.backends.base` MUST NOT import any `fenolite.backends.<x>` module, so `checks` can receive reports by injection without importing a backend.

#### Scenario: Violations by type
- **GIVEN** a `DrcReport` with two `clearance` violations and one `lib_footprint_mismatch` violation
- **WHEN** `report.of_type("lib_footprint_mismatch")` is called
- **THEN** it returns the one violation

#### Scenario: Integer positions only
- **WHEN** `DrcItem(uuid="u", description="d", position=Point(1.5, 0))` is constructed
- **THEN** a `TypeError` is raised

#### Scenario: Base stays backend-free
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes, and `fenolite.backends.base` imports no `fenolite.backends.<x>` module
