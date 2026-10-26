## ADDED Requirements

### Requirement: Rule areas, board items and area rules in an Altium build
The Altium build SHALL treat the rule areas, texts, graphics and dimensions that a script declares (`design-dsl`, "Rule areas in the DSL", "Board drawings in the DSL") as the board items they are in the model: written to a planned PCB document where `altium-pcb-writer` has a record for them ("Board text records", "Board graphics and keep-out records"), and reported item by item where it has none ("Complete board in an Altium build"). This requirement adds no record, key or format fact.
- **Rule areas.** A keep-out that sets at least one of `no_tracks`, `no_vias`, `no_pads` and `no_copper_pour` MUST be written with those restrictions. `Keepout.name` has no recorded key in the keep-out record: it MUST NOT be written, and each named keep-out MUST give one `altium.not-lowered` info whose `where` is `keepout/<id>` and whose message names the name that is lost. A rule area that forbids nothing, a named area for rules only, has no record, as any keep-out without a restriction: it MUST give one `altium.not-lowered` with `where` `keepout/<id>` and MUST be counted under `keep-out` of `result.pcb.not_lowered`.
- **Texts.** A board text whose `h_justify` and `v_justify` are both `center` MUST be written as before. Another justification has no recorded key in the text record: the text MUST NOT be written at a guessed position, and MUST give one `altium.not-lowered` with `where` `text/<id>` that names the justification.
- **Dimensions.** `lens.altium_copper.KINDS`, the kinds of "Written items are accounted", MUST gain `dimension`. No dimension record is written: each `Dimension` of the board MUST give one `altium.not-lowered` with `where` `dimension/<id>`, and `result.pcb.not_lowered` MUST hold `dimension` with their count. `lens.altium_copper.BOARD_KINDS` MUST gain the row `("dimensions", "dimensions")`, so that a build without a PCB document reports the dimensions with one info, as it reports keep-outs, texts, graphics and holes.
- **Area rules.** A rule whose selector holds an `area` leaf (`rules-model`, "Closed selector grammar") has no scope in the closed scope grammar of the rule records. `backends.altium.rulemap.lower` MUST give it the reason `scope-unsupported`, for that rule only ("Scoped rule records"), and the build MUST report it with the `altium.not-lowered` warning of "Rules in an Altium build" (`where` `design-rules/<kind>`) and list it under `result.rules.not_lowered`. `rulemap.TABLE` gains no row: `area` is a selector, not a rule kind. `build.area-unknown` (`design-dsl`, "Board items in a build") stays a check of the KiCad build and of the in-memory KiCad build that resolves script copper ("Script copper in an Altium build").
- **Copper guard.** The copper guard of an Altium build ("Copper guard in an Altium build") judges the document it reads back with the same `check_copper`, so it can find `copper.keepout` (`copper-check`, "Keep-out findings") for the keep-outs that the document holds. As that requirement rules for every copper error other than a short, the finding MUST be reported with severity `warning` and the guard's suffix, and MUST NOT stop the build. Area rules are not in the document, so the guard does not apply them.
- A design without rule areas, justified texts, dimensions and area rules MUST give the files and the issues it gave before this requirement.

#### Scenario: Script items in an Altium build
- **GIVEN** the blink variant of `design-dsl`, "Blink with a keep-out, a label and a dimension": `d.rule_area("ANT", …, forbid=("tracks", "vias"))`, `d.text("rev", "REV A", (mm(2), mm(2)))` and `d.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.pcb.written` holds `keep-out` 1 and `text` 1, `result.pcb.not_lowered` holds `dimension` 1, and the `altium.not-lowered` issues for these items are exactly two infos: one with `where` `keepout/<id>` that names `ANT`, and one with `where` `dimension/<id>`

#### Scenario: A rules-only area and a justified text
- **GIVEN** a blink variant with `d.rule_area("HV", …)` without `forbid` and one text declared with a `justify` other than the centred default
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.pcb.not_lowered` holds `keep-out` 1 and `text` 1, and `issues` holds one `altium.not-lowered` with `where` `keepout/<id>` and one with `where` `text/<id>` that names the justification

#### Scenario: An area rule is not lowered
- **GIVEN** a blink variant with the rule area `HV` and a `clearance` rule `hv` whose `selector_a` is `area HV` and whose `min` is 2 mm
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `altium.not-lowered` warning with `where` `design-rules/clearance` that names `hv` and `scope-unsupported`, `result.rules.not_lowered` lists the rule with that reason, and every other rule of the design is written as before

#### Scenario: Dimensions without a document
- **GIVEN** a model without a board outline whose board holds one `Dimension`
- **WHEN** `build_altium` runs
- **THEN** no `.PcbDoc` is planned, and `issues` holds one `altium.not-lowered` info with `where` `dimensions` that names the count 1

#### Scenario: No new item, no new issue
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py tests/unit/lens/test_altium_pcb_golden.py tests/unit/lens/test_altium_rules.py` builds the committed samples
- **THEN** every file equals the committed one, and no `altium.not-lowered` names a dimension, a name or a justification
