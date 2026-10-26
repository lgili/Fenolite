## ADDED Requirements

### Requirement: Outward height of a part
`fenolite.model.board.outward_height(footprint: FootprintInstance) -> Nm | None` SHALL return the height of a placed part above the board surface on its own side, as "Component bodies" defines it, and SHALL be the one place of the package that computes it.
- A body is known when its `projection_unknown` is false. The upper bound of a known body is its `z_max` when the body has signed bounds, and its `height` otherwise.
- The function MUST return the largest upper bound of the footprint's known bodies, and `None` when the footprint has no known body or that bound is not positive. It MUST NOT read the component, a footprint property, a 3D model reference or the footprint's definition, and it MUST NOT read `standoff` or `z_min`: what lies below the top of a body is the business of the volume analysis.
- It is pure: no file, no clock, integers only.
- A consumer that needs the height of a part (a placement rule, a checker, an exporter) MUST call this function. No other field of the model holds a part's height: `Component` has none, and a script states a height by giving the part a body (`design-dsl`, "Part heights and height limits in the DSL").
- `docs/design-model.md` MUST say this under "Component bodies".

#### Scenario: Largest known body
- **GIVEN** a footprint with three bodies: one with `height == 2_000_000`, one with `z_min == -500_000` and `z_max == 9_000_000` (and a legacy `height` of 3 mm kept as provenance), and one with `height == 30_000_000` and `projection_unknown` true
- **WHEN** `uv run pytest tests/unit/model/test_outward_height.py -k largest` calls `outward_height`
- **THEN** it returns `9_000_000`: the signed bound wins over that body's legacy height, and the body of unknown projection makes no claim

#### Scenario: No known height
- **WHEN** `outward_height` is called for a footprint without bodies, for one whose only body has `projection_unknown` true, and for one whose only body has `z_min == -4_000_000` and `z_max == 0`
- **THEN** each call returns `None`

#### Scenario: One reader
- **WHEN** `uv run pytest tests/unit/model/test_outward_height.py -k one_reader` searches `src/fenolite/checks/placement.py`, `src/fenolite/cli/cmd_place.py` and `src/fenolite/cli/cmd_build.py` for attribute reads of `.z_max` and for iteration over `.bodies`
- **THEN** it finds none: the placement rules reach a part's height only through `outward_height`

### Requirement: Height limits in the model
`fenolite.model.rules` SHALL define the frozen value object `HeightLimit(area, max, severity="error")`, and `RuleSet` SHALL gain the field `heights: tuple[HeightLimit, ...]`, empty by default and stored in `rules.json`. This is an addition to the rules layer of "Model layers for v0.1", beside the proximity rules of "Proximity rules in the model".
- `area` MUST be a non-empty name of a rule area; `max` a positive length in nm; `severity` a `PlacementSeverity`. `HeightLimit` MUST raise `ValueError` otherwise, and `RuleSet` MUST raise `ValueError` for two limits of one `area`.
- It is a value object, not an entity: it carries no id, and its area is its key. `to_model` writes the limits in area order.
- A height limit is not a rule of `RuleSet.rules` and has no `RuleKind`. No backend lowers it: the KiCad writer and `lower_rules` read only `RuleSet.rules`, the Altium rule table (`altium-pcb-writer`, "Rule lowering table") gains no row, and a board read from a file has none.
- `schemas/fenolite.model.v0/rules.json` MUST be regenerated. A `rules.json` without the key `heights` MUST load with an empty tuple, and a rule set without limits MUST be written without the key, so a design that declares none writes the bytes it wrote before this change. `SCHEMA_VERSION` stays `"0"`.
- `docs/design-model.md` MUST describe the value object and the field, and MUST say that 0.2.x and 0.3.0 cannot read a `rules.json` that carries `heights`.

#### Scenario: Limits round trip
- **GIVEN** a design whose `RuleSet.heights` holds `HeightLimit("LID", 5_000_000, "warning")` and `HeightLimit("FAN", 12_000_000)`
- **WHEN** it is written with `canonical.dump_dir` and loaded with `canonical.load_dir`
- **THEN** the loaded limits equal the originals, and `rules.json` holds them under `heights` with `FAN` before `LID`

#### Scenario: Files of an older build
- **GIVEN** a `rules.json` written before this change
- **WHEN** it is loaded and written again
- **THEN** `RuleSet.heights == ()` and the written bytes equal the input

#### Scenario: Refused values
- **WHEN** `HeightLimit("LID", 0)`, `HeightLimit("", 1_000_000)` and a `RuleSet` holding two limits on `LID` are built
- **THEN** each raises `ValueError`

#### Scenario: Compatibility is documented
- **WHEN** `uv run pytest tests/unit/model/test_rules.py -k documented` reads `docs/design-model.md`
- **THEN** the section on `heights` holds the sentence that 0.2.x and 0.3.0 cannot read a document that carries the key
