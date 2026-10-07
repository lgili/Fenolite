## MODIFIED Requirements

### Requirement: Planes in a build
`fenolite build` SHALL hand the script's planes to the build of its target. This requirement extends "Build command" (a step of `cmd_build`) and "Build issue codes" (one code).
- `cmd_build` MUST call `planes(design)` with `to_model`, and a `DslError` it raises MUST become `DesignScriptError` (`FEN-3004`, exit 3) as "Build command" rules for `placements`.
- With `--target altium`, `cmd_build` MUST pass the mapping to `lens.altium.build_altium(…, planes=…)` (`altium-build`, "Internal planes in an Altium build").
- With the KiCad target, `cmd_build` MUST pass the mapping to `lens.build.build_design(…, planes=…)`, and the board it writes MUST give each plane layer the row type `power` (`kicad-file-backend`, "Plane layers of a board"; `H-K-LAYER-POWER`). Over an existing board, the type MUST be set after the layout merge; every other copper layer keeps the type of the board it is written from, `signal` for a created board. A plane does not remove a `power` type that the board holds on another layer.
- A plane whose net has no zone on its layer, in the script or on the existing board, MUST give one `build.plane-zone-missing` (warning) naming the layer and the net, whose hint names `design.zone(<net>, layers=("<layer>",))`. `lens.build.BUILD_ISSUE_CODES` MUST hold `build.plane-zone-missing` with severity `warning`, and `lens.build.plane_issues(planes, design)` MUST return those issues (the second argument is new: the function took the planes alone). No target gives `build.plane-not-lowered` after this change: the code MUST leave `BUILD_ISSUE_CODES` and its entry MUST leave `src/fenolite/cli/data/explain.toml`, where `build.plane-zone-missing` gets one.
- The Altium target is not changed by this change: it writes each plane as an internal plane on its net whether a zone exists or not (`altium-build`, "Internal planes in an Altium build"), so it MUST NOT give `build.plane-zone-missing`.
- A script without planes MUST build every file with the bytes it had before this change, for both targets.

#### Scenario: Plane in a KiCad build
- **GIVEN** a blink variant with `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})` and `design.zone(gnd, layers=("In1.Cu",))`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0, `issues` hold no `build.plane-zone-missing` and no `build.plane-not-lowered`, the planned board holds `(4 "In1.Cu" power)` and `(6 "In2.Cu" signal)`, and it differs from the board of the same script without `planes` in that row only

#### Scenario: Plane without its zone
- **GIVEN** the same variant without the `zone()` call
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0, `issues` hold one `build.plane-zone-missing` warning naming `In1.Cu` and `GND` whose hint names `design.zone` and `In1.Cu`, and the planned board holds `(4 "In1.Cu" power)`

#### Scenario: Plane declared after the first build
- **GIVEN** a confirmed build of the variant without `planes`, and then the script with `planes={"In1.Cu": gnd}`
- **WHEN** it is built again with `--confirm`
- **THEN** the board keeps its layout and holds `(4 "In1.Cu" power)`

#### Scenario: A type set in KiCad stays
- **GIVEN** a confirmed build of the variant without `planes`, whose board was given `(6 "In2.Cu" power)` by token edit, as KiCad's board setup does
- **WHEN** the script without `planes` is built again with `--confirm`
- **THEN** the board still holds `(6 "In2.Cu" power)`

#### Scenario: Plane in an Altium build
- **WHEN** the variant of "Plane in a KiCad build" is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.copper.planes` is `{"In1.Cu": "GND"}`, and no `build.plane-zone-missing` is given

#### Scenario: Unknown plane net stops the build
- **GIVEN** a blink variant with `planes={"In1.Cu": "NOPE"}`
- **WHEN** it is built
- **THEN** the exit code is 3 and stderr carries `FEN-3004` naming `NOPE`

### Requirement: Rule constructor in the DSL
`design.rules.rule(name, kind, *, where=select.ALL, between=None, layers=(), min=None, opt=None, max=None, severity="error", priority=0)` SHALL declare one design rule of any model kind (`fenolite.model.rules.RuleKind`), with selectors from `fenolite.dsl.select` ("Selectors in the DSL").
- `DslError` MUST be raised at the call, and nothing recorded, for: a `name` that is not a non-empty string or is already used by `rule()`; a `kind` outside `RuleKind`; no limit, for every kind but `no_tracks`; a limit that is not a `Length` or a string with a unit; a negative `min`, or an `opt` or `max` of 0 or less; `min` above `opt` or `max`, or `opt` above `max`; a `where` or `between` that is not a selector; a `between` for a kind other than `clearance` and `creepage`; a `layers` value that is not a tuple of strings; a `severity` outside `error`, `warning` and `ignore`; a `priority` that is not an integer of 0 or more.
- The kind `no_tracks` (`rules-model`, "Track layer rules") takes no limit and needs layers: for it, `DslError` MUST be raised for a `min`, `opt` or `max`, naming the argument, and for an empty `layers`, naming `layers`.
- What depends on the target is not checked here: limits per kind, kind support, globs, selector support and layer names are refused by the lowering with its codes, and `build` reports them (exit 7, `FEN-7001`).
- `Rules.named` MUST hold one `dsl.design.RuleSpec` per call, in call order.
- `dsl.to_model` MUST add one model `Rule` per call to `Design.rules.rules`, after the rules of `minimum()`, in call order: id `derived_id("rul", "dsl", "rule:named:<name>")`, the given name, kind, limits, severity and priority, `selector_a` from `where`, `selector_b` from `between` (`None` when not given) and `layers` as given.
- `docs/dsl.md` MUST describe `rule()` in its section "Design rules", with an example per kind group, and say that priority 0 is written first and governs least.

#### Scenario: Creepage rule in the model
- **GIVEN** a design with the classes `HV` and `LV` and `d.rules.rule("mains", "creepage", where=select.netclass("HV"), between=select.netclass("LV"), min=mm(6.4))`
- **WHEN** `to_model(d)` runs
- **THEN** `rules.rules` holds one `creepage` rule named `mains`, with `selector_a == Selector("netclass", "HV")`, `selector_b == Selector("netclass", "LV")`, `min == 6_400_000` and the id `derived_id("rul", "dsl", "rule:named:mains")`

#### Scenario: Board-wide hole pitch
- **WHEN** `d.rules.rule("pitch", "hole_to_hole", min="0.25mm")` is declared and the design is built for target 10
- **THEN** `<name>.kicad_dru` holds a rule `"fenolite_0_pitch"` with `(constraint hole_to_hole (min 0.25mm))` and no condition

#### Scenario: Second side refused for a hole kind
- **WHEN** `d.rules.rule("x", "hole_clearance", where=select.net("A"), between=select.net("B"), min=mm(0.3))` is called
- **THEN** `DslError` is raised naming `between` and `hole_clearance`, and nothing is recorded

#### Scenario: Target refusal reported by the build
- **GIVEN** a design with a `creepage` rule
- **WHEN** it is built with `--kicad-version 9 --dry-run --json`, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001`, a message that names the rule and says that KiCad 9.0 does not check creepage rules, and a hint naming `--allow-lossy`; the second exits 0 with `rules.dropped-for-target` in `issues`

#### Scenario: A class kept on the outer layers
- **GIVEN** a four-layer blink variant with the class `SIG` and `design.rules.rule("sig-outer", "no_tracks", where=select.netclass("SIG"), layers=("In1.Cu", "In2.Cu"))`
- **WHEN** `uv run pytest tests/unit/dsl/test_rule_constructor.py -k no_tracks` runs `to_model`, and the variant is built with `--dry-run --json`
- **THEN** the model holds one `no_tracks` rule with `selector_a` `netclass SIG` and those layers, and the planned rules file holds two `disallow track` rules, one per layer

#### Scenario: Malformed track layer rules
- **WHEN** `rule("a", "no_tracks", layers=("In1.Cu",), min=mm(0.1))`, `rule("b", "no_tracks")` and `rule("c", "no_tracks", layers=("In1.Cu",), between=select.netclass("HV"))` are called
- **THEN** each raises `DslError`, the first naming `min`, the second `layers` and the third `between`
