## ADDED Requirements

### Requirement: DRC report limits of an oracle
`fenolite.backends.base` SHALL define how a DRC oracle says where its report stops, so that `checks` can tell a complete count from a cut one without importing a backend.
- `DrcLimits(per_type: Mapping[str, int], others: int)` MUST be a frozen dataclass: the largest number of entries the tool writes for each named type of its report, and for every other type. `DrcLimits.limit(type) -> int` MUST give `per_type[type]`, or `others`. Every value MUST be a positive `int`; construction MUST raise `ValueError` otherwise. The key `unconnected_items` stands for the list of unconnected items of a `DrcReport`; every other key is a violation `type`, in the tool's own spelling.
- `LimitedOracle` MUST be a `@runtime_checkable` `typing.Protocol` with `report_limits() -> DrcLimits`. It stands beside `Oracle`, as the netlist and round-trip oracles do, and "Oracle protocol" is unchanged: an oracle MAY satisfy both, and an oracle that does not satisfy `LimitedOracle` says nothing about limits.
- `fenolite.backends.kicad.oracle.KicadOracle` MUST satisfy `LimitedOracle`, returning `fenolite.backends.kicad.drc.REPORT_LIMITS[major]` for the major of its `kicad-cli`: `DrcLimits({"clearance": 499, "unconnected_items": 499}, others=199)` for 9 and for 10. The table MUST hold measured values only, each pinned to a probe of `H-K-DRC-LIMITS` (`kicad-oracle`, "DRC report limits are probed"); a major without a row MUST raise the error that an unsupported major raises today.
- `fenolite.backends.kicad.canary.CLEARANCE_REPORT_LIMIT` MUST be the `clearance` value of that table, so that the canary's verdict `clearance-limit` and the mark of `check` rest on one number.
- No Altium module satisfies `LimitedOracle`: Fenolite runs no Altium tool that writes a report. The findings an Altium document gets come from Fenolite's own checks, which report every finding.

#### Scenario: Limits by type
- **WHEN** `uv run pytest tests/unit/backends/test_base_drc_limits.py -k limit` calls `DrcLimits({"clearance": 499}, others=199).limit` with `clearance` and with `silk_overlap`
- **THEN** it returns 499 and 199, and `DrcLimits({}, others=0)` raises `ValueError`

#### Scenario: The KiCad oracle states its limits
- **GIVEN** `KicadOracle` over a fake `kicad-cli` of version 10.0.6, and over one of version 9.0.9
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_oracle_limits.py` calls `report_limits()` on each
- **THEN** both return limits of 499 for `clearance` and `unconnected_items` and 199 for `track_dangling`, `isinstance(oracle, LimitedOracle)` is true, and `canary.CLEARANCE_REPORT_LIMIT` equals the `clearance` value

#### Scenario: An oracle without limits
- **GIVEN** the fake `Oracle` of `tests/unit/checks/fakes.py`, which has no `report_limits`
- **WHEN** `isinstance(fake, LimitedOracle)` is evaluated
- **THEN** it is false, and `uv run pytest tests/unit/test_import_graph.py` still finds no `fenolite.backends.<x>` import in `fenolite.backends.base`
