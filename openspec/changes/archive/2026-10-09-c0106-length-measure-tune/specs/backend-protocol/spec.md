## ADDED Requirements

### Requirement: Length facts source
`fenolite.backends.base` SHALL define the frozen records `NetLength(net: str, routed: Nm, vias: Nm, die: Nm, total: Nm, via_count: int)` and `LengthFacts(nets: Mapping[str, NetLength], depths: Mapping[str, Nm], die: Mapping[str, Nm], major: int | None, stackup: Literal["board", "default", "none"], count_vias: bool, evidence: Evidence)`, and the `@runtime_checkable` protocol `LengthSource` with the method `length_facts(design: Design, *, project: ProjectSet | None = None, major: int | None = None, nets: Collection[str] | None = None, issues: list[Issue] | None = None) -> LengthFacts`. Through it, `analysis` and `checks` reach the length of a net as a tool counts it, without importing a backend.
- `NetLength.total` MUST equal `routed + vias + die`: `routed` is the length of the centre lines of the net's tracks and arcs, `vias` the sum of the heights its vias add, `die` the sum of the die lengths of its pads, all in nm; `via_count` counts its vias.
- `LengthFacts.nets` MUST hold one entry, keyed by net name, per net that has a pad, a track, an arc or a via on the board, or only those of them named in the argument `nets`. `depths` MUST map each copper layer to its depth as the tool counts it, and MUST be empty when the depths are unknown; `die` MUST map pad ids (`Pad.id`) to die lengths, a pad without one having no entry; `stackup` MUST say where the depths come from (`none` when they are unknown); `count_vias` MUST be false when the project counts no via height; `major` names the tool version whose counting the facts follow.
- `length_facts` is a query, not an operation: it MUST NOT raise for a project file that fails to read, MUST append warnings and infos to `issues` when a list is given, and `CapabilityReport.operations` stays the closed list of "Capability reports".
- The records MUST be frozen dataclasses with slots whose field types are builtins, `typing` constructs, `fenolite.core` types and `fenolite.model` types only, and `backends.base` MUST still import only `core` and `model`.
- `KicadBackend` MUST satisfy `LengthSource` (`board-frame`, "KiCad net lengths"), and `backends/kicad/backend.py` MUST hold the statement `_LENGTHS: LengthSource = KicadBackend()`, which pyright checks.

#### Scenario: KiCad backend is a length source
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k length_source` checks `isinstance(KicadBackend(), LengthSource)` and `KicadBackend().capabilities().operations`
- **THEN** the first is true, and the operations do not name `length_facts`

#### Scenario: Records are plain data
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k length_records` reads `typing.get_type_hints` of `NetLength` and `LengthFacts`
- **THEN** every annotation names only builtins, `typing` constructs, `fenolite.core` or `fenolite.model` types, and `backends/base.py` imports only `core` and `model`

#### Scenario: The total is the sum of its parts
- **GIVEN** the two-layer and four-layer benches of `tests/_lengthbench.py`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lengths.py -k parts` computes `KicadBackend().length_facts` for major 9 and for major 10
- **THEN** every `NetLength` has `total == routed + vias + die`, and every net with a pad, track, arc or via has an entry
