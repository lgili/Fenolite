## ADDED Requirements

### Requirement: Net-tie groups in the model
The board and library layers SHALL model a footprint's net-tie groups as `FootprintInstance.net_ties` and `FootprintDef.net_ties`, both `tuple[tuple[str, ...], ...]`, ordered, with the default `()`, so documents written before them still load. Canonical JSON omits a field at its default, so a footprint without groups MUST be written with the bytes it had before these fields existed.
- Each inner tuple is one group: the numbers of pads that the footprint joins on purpose, in the order the source lists them. A backend reads them from its own form (`kicad-file-backend`, "Net-tie groups on boards and footprints"), and the copper check skips the pad pairs of one group (`copper-check`, "Pairs that are judged").
- `Design.validate()` MUST NOT check the numbers against the pads: a read board keeps what its file says.
- `docs/design-model.md` MUST describe both fields and MUST say that 0.2.x and 0.3.0 cannot read a document that carries `net_ties`; `schemas/fenolite.model.v0/board.json` and `library.json` MUST be regenerated, and `SCHEMA_VERSION` stays `"0"`.
- A backend that reads no groups leaves the field `()`: the Altium import does, so the copper check of an imported board judges every pad pair.

#### Scenario: Old documents load
- **GIVEN** a `board.json` written before this change
- **WHEN** `uv run pytest tests/unit/model -k net_ties` loads it with `load_dir`
- **THEN** every `FootprintInstance.net_ties` is `()`, and writing the design again gives the same bytes: no `net_ties` key is written

#### Scenario: Schema in step
- **WHEN** `uv run python tools/gen_schemas.py --check` runs
- **THEN** it exits 0, and both schemas list `net_ties` as an array of arrays of strings

### Requirement: Waivers in the findings layer
The findings layer SHALL hold a design's waivers as `fenolite.model.findings.Waiver(name: str, code: str, items: tuple[str, ...], reason: str, min_gap: Nm | None = None)`, a frozen dataclass, in `Findings.waivers: tuple[Waiver, ...]`, sorted by name, with the default `()`, so `findings.json` files written before them still load.
- `code` is a finding code (`copper.short`, `copper.clearance`, `copper.zone-overlap` or `<oracle>.drc.<suffix>`); `items` are names or glob patterns of the finding's items, as `where` prints them; `min_gap` is in integer nm.
- What a waiver may say is checked where it is declared (`design-dsl`, "Waivers in the DSL"); how it matches is `verification-loop`, "Waivers in the check".
- `docs/design-model.md` MUST describe `Waiver` and the field and MUST say that 0.2.x and 0.3.0 cannot read a `findings.json` that carries `waivers`; `schemas/fenolite.model.v0/findings.json` MUST be regenerated. A design without waivers MUST write the `findings.json` bytes it wrote before.

#### Scenario: Waivers round-trip through the cache
- **GIVEN** a design whose findings hold two waivers, one with `min_gap=150_000`
- **WHEN** `uv run pytest tests/unit/model -k waivers` writes it with the canonical writer and loads it back
- **THEN** the loaded `Findings.waivers` equals the original, in name order, and `findings.json` holds no float

### Requirement: Check severities in the rules layer
The rules layer SHALL hold the severities that a design gives the checks of a design-rule tool as `RuleSet.severities: dict[str, RuleSeverity]`, with the default `{}`, so `rules.json` files written before it still load. A key is the finding code of the check (`<oracle>.drc.<suffix>`, as `check` reports it), a value is `error`, `warning` or `ignore`, and canonical JSON writes the keys sorted. `docs/design-model.md` MUST describe the field and MUST say that 0.2.x and 0.3.0 cannot read a `rules.json` that carries `severities`; `schemas/fenolite.model.v0/rules.json` MUST be regenerated. A rule set without severities MUST write the bytes it wrote before. A severity is not a rule: it has no `RuleKind` and no row in a backend's rule table.

#### Scenario: Severities round-trip
- **GIVEN** a `RuleSet` with `severities == {"kicad.drc.via-dangling": "error", "kicad.drc.silk-overlap": "ignore"}`
- **WHEN** it is written and loaded back
- **THEN** the loaded value is equal, and `rules.json` lists `kicad.drc.silk-overlap` before `kicad.drc.via-dangling`

#### Scenario: Unused keys change no byte
- **WHEN** `uv run pytest tests/unit/lens -k unused_keys` builds `examples/blink_2layer/design.py` and `examples/blink_routed/design.py` for targets 9 and 10 with a fixed seed and timestamp
- **THEN** the SHA-256 of every planned file, the documents under `.fenolite/` included, equals the one the test records from the commit before this change, and no document holds `net_ties`, `waivers` or `severities`
