## MODIFIED Requirements

### Requirement: Clearance rules of a PCB document
`AltiumBackend` SHALL satisfy `DesignRulesSource` (`backend-protocol`): `design_rules(design, project)` gives the clearance in force for the import `design` of the PCB document `project.board`.
- `DesignRules.design` MUST be `design` with the clearance of every zone at 0, with every `clearance` rule lowered by `UNIT_SLACK_NM` = 5 nm (`docs/formats/altium/import.md`, "Clearance of the copper check"). It MUST hold every track and every arc of `design`: the import makes no copper of an object on an internal plane (`altium-import`, "Objects on an internal plane"), so the rules source takes nothing out.
- `opaque_clearance_rules` MUST count the enabled `Clearance` records of `Rules6/Data` that `read.rules.map_rules` does not map; a disabled record MUST NOT count. `min_clearance` MUST be `None`, `rules_over_classes` true and `floor_over_rules` false.
- `left_out` MUST hold one entry of kind `plane` with the number of internal plane layers when the board has any, and be empty otherwise. An internal plane layer is a copper layer whose `altium` bag holds a `layer_id` from 39 to 54. The entry's reason MUST hold the number of objects that the import left out on those layers, the sum of their `plane_cuts`.
- A document that cannot be read MUST be named in `unread` and MUST NOT raise.

#### Scenario: Rules of a built sample
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k rules_source` asks for the rules of `routed.PcbDoc`
- **THEN** both zones have the clearance 0, the two clearance rules are 199 995 nm, no rule is opaque, and a missing document is named in `unread`

#### Scenario: Planes of an imported board
- **GIVEN** an authored document whose chain is 1 → 39 → 32, with two free tracks without a net on layer 39 and one track on layer 1
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k plane` imports it and asks for its rules
- **THEN** `DesignRules.design` holds the one track of the import, `left_out` is one entry `plane` with the count 1 whose reason names 2 objects, and a board without a plane layer has an empty `left_out`
