## ADDED Requirements

### Requirement: Stored exclusions source
`fenolite.backends.base` SHALL define the frozen dataclass `StoredExclusion(type: str, position: Point, uuids: tuple[str, str], comment: str = "")` and the `@runtime_checkable` protocol `ExclusionSource` with the method `stored_exclusions(project: ProjectSet) -> tuple[StoredExclusion, ...]`. Through it `checks` reaches the DRC exclusions that a project's own files store, without importing a backend (`verification-loop`, "Exclusions in the DRC stage").
- `type` is the tool's check type, `position` the stored marker position in integer nm, and `uuids` the two stored item uuids in order, the second being the nil uuid `00000000-0000-0000-0000-000000000000` for an entry of one item.
- `stored_exclusions` MUST NOT raise for a project file that fails to read, and MUST return `()` then.
- `stored_exclusions` is not an operation: `CapabilityReport.operations` stays the closed list of "Capability reports".
- `KicadBackend` MUST satisfy `ExclusionSource` (`kicad-file-backend`, "Stored exclusions are read"), and `backends/kicad/backend.py` MUST hold the statement `_EXCLUSION_SOURCE: ExclusionSource = KicadBackend()`, which pyright checks.
- `backends.base` MUST still import only `core` and `model`.

#### Scenario: KiCad backend is an exclusion source
- **GIVEN** a copy set of the native `two_layer` project, whose project file stores no exclusion
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k exclusion` runs
- **THEN** `isinstance(KicadBackend(), ExclusionSource)` is true and `stored_exclusions(project)` returns `()`

#### Scenario: An unreadable project gives no exclusion
- **GIVEN** a copy set whose `.kicad_pro` is not JSON
- **WHEN** `stored_exclusions(project)` is called
- **THEN** it returns `()` and raises nothing
