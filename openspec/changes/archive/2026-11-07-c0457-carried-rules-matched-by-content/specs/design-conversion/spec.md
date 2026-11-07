## ADDED Requirements

### Requirement: Carried rule records matched by content
The board property `Fenolite.Altium.Rules6` SHALL key each rule list a record gave by two SHA-256 keys (`rulecarrier.rule_keys`, schema `fenolite.altium-rules.v1`, change c0457): its content and its shape. Both are taken over the rule's children after its name, each in compact form, in sorted order, with a condition in the form `rulecarrier.condition_key` gives (schema `fenolite.altium-rules.v2`): its parsed selectors when KiCad's closed grammar reads it, else its text with runs of spaces made one and balanced outer parentheses taken off. A property of schema `fenolite.altium-rules.v1` MUST still be compared with the keys of that version. The shape also leaves out the values of each constraint's `min`, `opt` and `max`. A conversion back to Altium (`rulecarrier.match`) MUST keep a record when each of its lists is a distinct rule of the rules file of the same content, one of its own name first. A rule of the same content as a rule a kept record took MUST be taken too and not lowered. A property of schema `fenolite.altium-rules.v0` MUST still be read: a list then matches a rule printed under the record's name with the same text.

#### Scenario: Rules written again under other names
- **GIVEN** a KiCad board converted from an authored Altium document, whose rules file is written again with every rule renamed, in reverse order, and with other spaces in its conditions
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k names` converts it back without `--allow-lossy`
- **THEN** every record comes back as the source holds it, and the `rule` row has no change and no loss

#### Scenario: Conditions of one meaning
- **GIVEN** `A.Type == 'Via' && A.NetClass == 'X'` with and without outer parentheses, with doubled spaces, and with each term in parentheses
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k meaning` keys them
- **THEN** they share one key, and a condition of another class does not

#### Scenario: A version 1 property
- **GIVEN** the same board with a version 1 property
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k version_1` converts it back
- **THEN** every record comes back as the source holds it

#### Scenario: A version 0 property
- **GIVEN** the same board with a version 0 property and one rule renamed
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k version_0` converts it back
- **THEN** every record comes back as the source holds it

### Requirement: Source rules edited in KiCad
A record whose rule lists are all rules of the file under their own names, of the same shapes, with other limits, SHALL be written with the limits KiCad holds and with its own name, priority, scopes and enabled state (`rulemap.edited_fields`). A key whose value did not change keeps its text. Its rules count `changed` under `rule` with the reason `to_altium.LIMITS_EDITED`. The rules of any other record not kept that are still in the file MUST be lowered as rules of their kind and count `changed` with `to_altium.EDITED_LOWERED`. Only such a rule that no Altium record can hold MUST be a loss of reason `SOURCE_RULE_LOST`.

#### Scenario: An edited limit
- **GIVEN** the same board whose scoped clearance of 10 mil (0.254 mm) holds 0.26 mm in the rules file
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k limit` converts it back without `--allow-lossy`
- **THEN** the record keeps its name, priority 2 and scope with `GAP` and `GENERICCLEARANCE` of `10.2362mil`, every other record comes back as read, and the `rule` row has one change and no loss

#### Scenario: An added condition
- **GIVEN** the same board whose unscoped clearance holds a condition on net `GND`
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k otherwise` converts it back
- **THEN** a Clearance record `Clearance_net_GND` of scope `InNet('GND')` is written, the record `Board Gap` is not, and the `rule` row counts one change and no `SOURCE_RULE_LOST`

#### Scenario: Flow A with one clearance edited
- **GIVEN** the authored Altium document imported with `import --to python`, whose script holds `design.rules.minimum(...)`, one clearance edited in `design.py` and built with `build`, which writes the via rule's condition in parentheses
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k imported` converts the board to Altium without `--allow-lossy`
- **THEN** `convert --to altium` exits 0, the edited record keeps its name and priority with the new gap, no other record changes, and the `rule` row counts one change (`LIMITS_EDITED`) and no loss

### Requirement: Board minimums of an imported design
A conversion back to Altium of a board that carries rule records SHALL NOT lower a rule that a build writes for `design.rules.minimum()` on the whole board (`rulecarrier.board_minimum`: named `fenolite_0_min_<constraint>`, without a condition or a layer, one constraint of that name holding a `min` alone) and that no record holds. When another rule of the file without a condition or a layer holds the same `min` of that constraint, the minimum MUST be taken without a report. Otherwise it MUST be a loss of reason `to_altium.BOARD_MINIMUM`, of the class `report`, which never needs `--allow-lossy`.

#### Scenario: A minimum no rule holds
- **GIVEN** the authored board with a rule `fenolite_0_min_via_diameter` of `min 0.3mm` added to its rules file
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k board_minimum` converts it back without `--allow-lossy`
- **THEN** every record comes back as read, and the `rule` row loses one rule for `BOARD_MINIMUM`, class `report`

### Requirement: The pour of the way back follows the source
A document converted to KiCad and back to Altium with the computed pour SHALL pour what the computed pour of the source document pours. A Clearance record whose scope the pour does not read, carried back by the property, MUST refuse the polygons it could govern on the way back as it does in the source (`rule-scope`, then `depends-on-refused`), each reported `altium.zone-unpoured`, and the polygon itself MUST be written.

#### Scenario: Public row -04
- **GIVEN** public row `altium-third-party-pcbdoc-04`, whose source pour refuses its 9 polygons (4 `rule-scope`, 5 `depends-on-refused`) under a Clearance record of unread scope
- **WHEN** `uv run pytest tests/corpus/test_altium_pour_c0457.py` converts it to KiCad and back with the computed pour
- **THEN** the way back reports 9 `altium.zone-unpoured` and no `altium.zones-poured`, writes the 9 polygons, and loses no rule
