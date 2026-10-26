## ADDED Requirements

### Requirement: Proximity rules in the model
`fenolite.model.rules` SHALL define `PlacementSeverity = Literal["error", "warning"]` and the frozen value objects `PadSelection(path, number="", index=None)` and `ProximityRule(name, parts, anchor, within, severity="error")`, and `RuleSet` SHALL gain the field `proximity: tuple[ProximityRule, ...]`, empty by default and stored in `rules.json`. This is an addition to the rules layer of "Model layers for v0.1".
- `PadSelection.path` MUST be a non-empty component path; `number` a pad number, empty for every pad of the part; `index` `None` or a non-negative `int`, given only with a `number`. `ProximityRule.parts` and `anchor` MUST be non-empty, and `within` MUST be a positive length in nm. Each value object MUST raise `ValueError` otherwise. `RuleSet` MUST raise `ValueError` for two `ProximityRule`s of one `name`.
- They are value objects, not entities: they carry no id, and a rule's name is its key. `to_model` writes them in name order.
- A proximity rule is not a rule of `RuleSet.rules` and has no `RuleKind`. No backend lowers it: the KiCad writer and `lower_rules` read only `RuleSet.rules`, the Altium rule table (`altium-pcb-writer`, "Rule lowering table") gains no row, and a board read from a file has none.
- `schemas/fenolite.model.v0/rules.json` MUST be regenerated, and `uv run python tools/gen_schemas.py --check` MUST exit 0. A `rules.json` without the key `proximity` MUST load with an empty tuple, and a rule set without proximity rules MUST be written without the key, so a design that declares none writes the bytes it wrote before this change. `SCHEMA_VERSION` stays `"0"`.
- `docs/design-model.md` MUST describe the two value objects and the field, and MUST say that 0.2.x and 0.3.0 cannot read a `rules.json` that carries `proximity`.

#### Scenario: Rules round trip
- **GIVEN** a design whose `RuleSet.proximity` holds `ProximityRule("dec7", (PadSelection("C5", "1"),), (PadSelection("U1", "7"),), 2_000_000)`
- **WHEN** it is written with `canonical.dump_dir` and loaded with `canonical.load_dir`
- **THEN** the loaded rule equals the original, and `rules.json` holds it under `proximity`

#### Scenario: Files of an older build
- **GIVEN** a `rules.json` written before this change
- **WHEN** it is loaded, validated against the regenerated schema and written again
- **THEN** loading succeeds, validation passes, `RuleSet.proximity == ()`, and the written bytes equal the input

#### Scenario: Refused values
- **WHEN** `ProximityRule("r", (), (PadSelection("U1"),), 1)`, `ProximityRule("r", (PadSelection("C1"),), (PadSelection("U1"),), 0)`, `PadSelection("U1", index=0)` and a `RuleSet` holding two rules named `dec7` are built
- **THEN** each raises `ValueError`

#### Scenario: Compatibility is documented
- **WHEN** `uv run pytest tests/unit/model/test_rules.py -k documented` reads `docs/design-model.md`
- **THEN** the section on `proximity` holds the sentence that 0.2.x and 0.3.0 cannot read a document that carries the key
