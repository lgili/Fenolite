## MODIFIED Requirements

### Requirement: Rules where they map
`import_board` and `import_project` SHALL fill `Design.rules` from the rule records through the mapper of c0042, `read.rules.map_rules`, and SHALL never approximate a rule.
- `adapter.rules.import_rules(records, ids, *, file, sha256, issues, storage="Rules6", layers=None)` MUST call `map_rules(records, origin=<file name>, layers=layers)` with `records == [r.fields for r in doc.rules]`: `RuleRecord.fields` of c0041 is the record's whole pair list, which is the mapper's input. It MUST take from the returned `RuleMapping` the neutral rules and the unmapped list, and MUST NOT hold a rule table of its own. The kinds that map are those of c0042: Clearance, Width, Routing Via Style and Hole Size.
- The adapter MUST keep each mapped rule's kind, name, limits, selectors, `priority` and `severity` as the mapper gives them, and MUST replace its header: the id and native id of "Identifiers and provenance" (also for the rule set), the provenance, and a bag with the pairs `rule_kind`, `scope1` and `scope2` in place of the mapper's record text, followed by the other pairs the mapper gave (`cell`, `cells_not_lifted`; `altium-project-reader`, "Cells of an object matrix"). The native id of a cell rule MUST end with `:<cell>`, so that the rules of one record have different ids.
- `import_board` MUST pass the copper layers of the board as `layers` (`LayerMap.copper_layers()`: for each layer of the copper chain the name the board record gives it, its neutral name, and `inner_signal` for an id between the top layer's and the bottom layer's), so that a layer condition of a `Clearance` record maps where `altium-project-reader`, "More forms of a Clearance record", says it does. `adapter.layers.copper_layers_of(layers)` MUST give the same value from the `Layer` entities of an imported board, and `None` when a copper layer holds no `layer_id` and `altium_name` pair. The rules of a rule file are mapped without layers.
- A layer name in a mapped rule MUST be the neutral name of "Layers and stack-up".
- `priority` MUST be the record's, 1 the highest, as the model defines it. A disabled rule MUST NOT be mapped: the mapper lists it as unmapped with the reason `disabled`, because a rule of severity `ignore` would silence the rule that applies in its place.
- Each unmapped rule MUST be counted by one `altium.import.rule-unmapped` info per rule kind, with the count and the mapper's reasons. The mapper's per-rule infos `altium.rule.unmapped` MUST NOT be forwarded; its other issues are.
- Rules of a rule file of the project are imported only when the caller passes them in `ProjectInput.rules`, as `RulesInput(file, sha256, records)`; the backend passes none.

#### Scenario: Rules of the routed sample
- **GIVEN** the PCB document of `tests/data/altium/routed/` of c0038, whose `Rules6` holds a clearance, a width and a via rule for the class `PWR` and for all objects
- **WHEN** it is imported
- **THEN** `design.rules` holds a `clearance` rule whose `selector_a` is `netclass PWR` with priority 1, a `track_width` rule with `min`, `opt` and `max`, a `via_diameter` and a `via_drill` rule, and no `altium.import.rule-unmapped`

#### Scenario: Disabled rule
- **GIVEN** a document whose `Rules6` holds a `Width` rule with `ENABLED=FALSE` and no other rule
- **WHEN** it is imported
- **THEN** `design.rules` holds no rule, and one `altium.import.rule-unmapped` counts one `Width` rule with the reason `disabled`

#### Scenario: Scope outside the grammar
- **GIVEN** a rule record whose first scope is `InPolygon`
- **WHEN** it is imported
- **THEN** `design.rules` does not hold it, and `altium.import.rule-unmapped` counts one rule of its kind with the mapper's reason

#### Scenario: Layer conditions take the layers of the board
- **GIVEN** a document of two copper layers named `Top Layer` and `Bottom Layer` whose `Rules6` holds the three records of "A clearance matrix on a two-layer board"
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_rules.py -k "take_the_layers or four_layers"` imports it
- **THEN** `design.rules` holds the 5 mil rule with `layers == ("F.Cu", "B.Cu")` and the 10 mil rule, and one `altium.import.rule-unmapped` says `no-layer 1`; with a copper chain of four layers the two layer conditions are unmapped with `scope 2`
