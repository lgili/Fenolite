## MODIFIED Requirements

### Requirement: Backend registry
`fenolite.backends.registry` SHALL provide `register(backend)`, `get(name)`, `all_backends()` and `for_path(path)`.
- The built-in backends, KiCad (`kicad`) and Altium (`altium`, `fenolite.backends.altium.backend.AltiumBackend`, change c0043), MUST be registered on the first call to any of them. Their modules MUST be imported inside a function, not at module import. Registering the Altium backend MUST NOT import a reader, the adapter or a writer: `backends/altium/backend.py` imports them inside `read`.
- `register` MUST raise `ValueError` for a name already registered.
- `get` MUST raise `KeyError` naming the known backends for an unknown name.
- `all_backends()` MUST return the backends sorted by name.
- `for_path` MUST return the first backend, in that order, whose `detect` returns `True`, or `None`. No path MUST be detected by two built-in backends.

#### Scenario: Built-in backends listed
- **WHEN** `registry.all_backends()` is called in a fresh interpreter
- **THEN** it returns two backends whose names are `altium` and `kicad`, in that order

#### Scenario: Registration stays cheap
- **WHEN** a fresh interpreter calls `registry.all_backends()` and then lists `sys.modules`
- **THEN** no module under `fenolite.backends.altium.read` or `fenolite.backends.altium.adapter` is loaded

#### Scenario: Duplicate registration
- **WHEN** a second backend named `kicad` is registered
- **THEN** `ValueError` is raised naming `kicad`

#### Scenario: Unknown backend
- **WHEN** `registry.get("nope")` is called
- **THEN** `KeyError` is raised and its message names `altium` and `kicad`

#### Scenario: Backend for a path
- **WHEN** `registry.for_path(Path("a.kicad_pcb"))`, `registry.for_path(Path("a.PcbDoc"))` and `registry.for_path(Path("a.txt"))` are called
- **THEN** the first returns the KiCad backend, the second the Altium backend and the third `None`

#### Scenario: Detection is disjoint
- **GIVEN** one path per suffix that a built-in backend detects
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k disjoint` asks every built-in backend
- **THEN** exactly one backend detects each path
