## ADDED Requirements

### Requirement: Board-wide rules lower to board-setup minimums
`fenolite.backends.kicad.lowering.lower_minimums(ruleset, *, target, current, issues=None)` SHALL return the board-setup minimums that the project file for KiCad `target` must hold, as a mapping from a key of `board.design_settings.rules` to nanometres. `lowering.MINIMUM_KEYS[target]` maps each rule kind, taken in normal form (`rulemap.normal_form`, so a `via_drill` rule counts as `hole_size`), to its key:

| kind in normal form | key for targets 9 and 10 |
|---|---|
| `clearance` | `min_clearance` |
| `track_width` | `min_track_width` |
| `via_diameter` | `min_via_diameter` |
| `hole_size` | `min_through_hole_diameter` |
| `edge_clearance` | `min_copper_edge_clearance` |

- A `target` that is not a key of `MINIMUM_KEYS` MUST raise `ValueError`.
- `lowering.is_board_wide(rule)` MUST be true exactly when the normal form of `rule` has `selector_a` `all`, no `selector_b` and no `layers`. A `via_drill` rule on `all` is not board-wide, because its normal form selects vias only.
- For each kind of `MINIMUM_KEYS[target]`, the governing board-wide rule MUST be the last board-wide rule of that kind in `rulemap.rule_order`, which is the one KiCad applies when several rules match (`H-K-DRU-ORDER`).
- When that governing rule has severity `error` and a `min`, its key MUST be returned with the least `min` among the governing rule and every rule of the same kind that comes after it in `rulemap.rule_order`, whatever their selectors, layers and severities. Rules before the governing rule MUST NOT count, because it governs every item they select. Otherwise, and when no board-wide rule of the kind exists, the key MUST NOT be returned.
- The function MUST return only keys of `MINIMUM_KEYS[target]`, and every returned value MUST be the `min` of a rule of `ruleset`: Fenolite ships no minimum values of its own.
- Only the modelled rules of `ruleset.rules` MUST be read; opaque rule slots are not seen. A `ruleset` of `None`, or one without a rule of the table's kinds, MUST give an empty mapping and no issue.
- `current` holds the minimums in force in the project being written (key to nanometres). It does not change the returned values; "Conflicts with board-setup minimums are reported" compares rules with it.

#### Scenario: Fab rule set
- **GIVEN** five board-wide rules of severity `error` and priority 0: `clearance` with `min=100_000`, `track_width` with `min=127_000`, `via_diameter` with `min=450_000`, `hole_size` with `min=200_000` and `edge_clearance` with `min=300_000`
- **WHEN** `lower_minimums(ruleset, target=10, current={})` is called with an `issues` list
- **THEN** it returns `{"min_clearance": 100_000, "min_track_width": 127_000, "min_via_diameter": 450_000, "min_through_hole_diameter": 200_000, "min_copper_edge_clearance": 300_000}` and `issues` stays empty

#### Scenario: A later rule lowers the minimum
- **GIVEN** a board-wide `hole_size` rule with `min=300_000` and priority 0, and a `via_drill` rule on `all` with `min=200_000` and priority 1
- **WHEN** they are lowered for target 9
- **THEN** the result is `{"min_through_hole_diameter": 200_000}`

#### Scenario: An earlier rule does not count
- **GIVEN** a board-wide `track_width` rule with `min=200_000` and priority 1, and a `track_width` rule on `net SIG` with `min=100_000` and priority 2
- **WHEN** they are lowered for target 10
- **THEN** the result is `{"min_track_width": 200_000}`, because the rule on `SIG` is written before the board-wide rule and never governs

#### Scenario: Via drill alone is not board-wide
- **GIVEN** only a `via_drill` rule on `all` with `min=200_000`
- **WHEN** it is lowered for target 10 with `current={}`
- **THEN** `is_board_wide` is false for it and the result is empty

#### Scenario: Layer or second selector
- **GIVEN** a `clearance` rule on `all` with `layers == ("F.Cu",)`, and a `clearance` rule with `selector_a = all` and `selector_b = netclass HV`
- **WHEN** `is_board_wide` is applied to each
- **THEN** it returns false for both, and true for a `clearance` rule whose `selector_a` and `selector_b` are both `all`

#### Scenario: No rules
- **GIVEN** `ruleset` is `None`
- **WHEN** `lower_minimums(None, target=10, current={"min_track_width": 200_000})` is called with an `issues` list
- **THEN** it returns `{}` and `issues` stays empty

### Requirement: Conflicts with board-setup minimums are reported
`lower_minimums` SHALL append an issue to `issues` for every rule whose value a board-setup minimum that Fenolite does not write keeps KiCad from applying. The codes extend the closed table of "Project issue codes" (see `kicad-file-backend`, "Project files carry the board-setup minimums").
- The info `kicad.project.minimum-kept` MUST be added for each kind whose governing board-wide rule has a severity other than `error` or no `min`, naming the rule and the reason. Its key is not returned, because a board-setup minimum has no severity of its own.
- The warning `kicad.project.rule-below-minimum` MUST be added for each rule of a kind of `MINIMUM_KEYS[target]` whose key is not returned, when `current` holds that key, the rule's `min` is below `current[key]`, and the key's entry in `lowering.FLOOR_OVER_RULES` holds `target`. Rules before a governing board-wide rule MUST be skipped. The message MUST name the rule, its `min`, the key and `current[key]`, and the hint MUST say that a board-wide rule of that kind with severity `error` lets Fenolite lower the minimum.
- The tables MUST follow the probes of "Board-setup minimums are proved by kicad-cli", read from `docs/evidence/kicad/probes/9.0.9.json` for major 9 and `10.0.6.json` for major 10:
  - `FLOOR_OVER_RULES[key]` holds exactly the majors M for which `pro-min-rules-template-<kind>-tM` records `present`;
  - `MINIMUM_KEYS[M]` holds a kind exactly when `pro-min-keys-template-<kind>-tM` records `present` and `pro-min-keys-lowered-<kind>-tM` records `absent`.

  Until the probes have run, the tables hold the claims of `H-K-PRO-MIN-RULE` and `H-K-PRO-MIN-KEYS`: every `FLOOR_OVER_RULES` entry holds `{9, 10}`, and `MINIMUM_KEYS` holds the table above for both targets. The unit scenarios of this capability use these values unless they say otherwise.
- Every issue of this requirement MUST be a warning or an info: KiCad accepts these projects, and the user may change a rule later.

#### Scenario: Narrower rule below the template minimum
- **GIVEN** a `track_width` rule on `netclass SIG` with `min=100_000`, no board-wide `track_width` rule, and `current == {"min_track_width": 200_000}`
- **WHEN** it is lowered for target 10 with an `issues` list
- **THEN** no key is returned and `issues` holds one warning `kicad.project.rule-below-minimum` naming the rule, `0.1`, `min_track_width` and `0.2`; with `FLOOR_OVER_RULES["min_track_width"] == frozenset({9})`, `issues` stays empty

#### Scenario: Governing rule of severity warning
- **GIVEN** a board-wide `track_width` rule with `min=100_000` and severity `warning`, and `current == {"min_track_width": 200_000}`
- **WHEN** it is lowered for target 9 with an `issues` list
- **THEN** no key is returned, and `issues` holds the info `kicad.project.minimum-kept` naming the severity `warning` and the warning `kicad.project.rule-below-minimum` naming the same rule

#### Scenario: Shipped tables follow the probes
- **GIVEN** the committed `lowering.FLOOR_OVER_RULES`, `lowering.RULES_OVER_CLASSES` and `lowering.MINIMUM_KEYS`, and the probe files `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lowering_minimums.py -k tables` runs
- **THEN** it passes only if each table holds exactly the majors and kinds that the probe outcomes support

### Requirement: Class clearances against board-wide clearance rules are reported
`fenolite.backends.kicad.lowering.class_conflicts(ruleset, *, target, clearances, model_names, issues=None)` SHALL report the classes whose clearance KiCad does not combine with the governing board-wide `clearance` rule as the design states them. `clearances` maps the name of every class entry of the project being written to its clearance in nanometres, and `model_names` holds the names of the model's classes. `class_conflicts` MUST NOT add an issue when no board-wide `clearance` rule exists. The codes extend the closed table of "Project issue codes".
- When `target` is in `lowering.RULES_OVER_CLASSES`, KiCad applies the governing rule to the items of every class. The warning `kicad.project.class-shadowed` MUST then be added for each class whose clearance is greater than the rule's `min`, naming the class, its clearance and the rule, except for:
  - a `Default` entry that `model_names` does not hold, whose nets the rule is meant to govern;
  - a class for which a `clearance` rule after the governing rule in `rulemap.rule_order`, whose normal form has `selector_a` `netclass <class name>`, no `selector_b` and no `layers`, has a `min` at least equal to the class clearance.
- When `target` is not in `RULES_OVER_CLASSES`, a class clearance above the rule governs the items of that class. The warning `kicad.project.default-over-rule` MUST then be added when `model_names` holds no `Default` and the `Default` clearance is greater than the rule's `min`, naming both values. The hint MUST say that a model class `Default` with the rule's clearance lowers it.
- `RULES_OVER_CLASSES` MUST hold exactly the majors M for which `pro-min-class-tM` records `absent` and `pro-min-class-control-tM` records `present`, in the probe files named by "Conflicts with board-setup minimums are reported". Until the probes have run it holds `{9, 10}`, the claim of `H-K-PRO-MIN-CLASS`, and the unit scenarios use that value unless they say otherwise.
- `class_conflicts` MUST compare clearances only: class track and via values are not checked against rules.

#### Scenario: Class clearance overridden by a board-wide rule
- **GIVEN** a board-wide `clearance` rule with `min=100_000` and priority 0, `clearances == {"Default": 200_000, "HV": 2_000_000}` and `model_names == {"HV"}`
- **WHEN** `class_conflicts(ruleset, target=10, clearances=clearances, model_names=model_names)` is called with an `issues` list
- **THEN** `issues` holds one warning `kicad.project.class-shadowed` naming HV, `2` and the rule; a further `clearance` rule on `netclass HV` with `min=2_000_000` and priority 1 removes it

#### Scenario: Default class above the rule
- **GIVEN** the same inputs and `RULES_OVER_CLASSES == frozenset()`
- **WHEN** `class_conflicts` is called for target 10 with an `issues` list
- **THEN** `issues` holds one warning `kicad.project.default-over-rule` naming `0.2` and `0.1`, and no `kicad.project.class-shadowed`; with `"Default"` in `model_names`, `issues` stays empty
