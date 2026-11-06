## ADDED Requirements

### Requirement: Carried rule records matched by content
The board property `Fenolite.Altium.Rules6` SHALL key each rule list a record gave by two SHA-256 keys (`rulecarrier.rule_keys`, schema `fenolite.altium-rules.v1`, change c0457): its content and its shape. Both are taken over the rule's children after its name, each in compact form, in sorted order, with the runs of spaces of a condition made one. The shape also leaves out the values of each constraint's `min`, `opt` and `max`. A conversion back to Altium (`rulecarrier.match`) MUST keep a record when each of its lists is a distinct rule of the rules file of the same content, one of its own name first. A rule of the same content as a rule a kept record took MUST be taken too and not lowered. A property of schema `fenolite.altium-rules.v0` MUST still be read: a list then matches a rule printed under the record's name with the same text.

#### Scenario: Rules written again under other names
- **GIVEN** a KiCad board converted from an authored Altium document, whose rules file is written again with every rule renamed, in reverse order, and with other spaces in its conditions
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k names` converts it back without `--allow-lossy`
- **THEN** every record comes back as the source holds it, and the `rule` row has no change and no loss

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
- **GIVEN** the authored Altium document imported with `import --to python`, one clearance edited in `design.py` and built with `build`
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k imported` converts the board to Altium without `--allow-lossy`
- **THEN** it exits 0, the edited record keeps its name and priority with the new gap, no other record changes, and no Clearance record is added for the import's board minimum

### Requirement: The pour of the way back follows the source
A document converted to KiCad and back to Altium with the computed pour SHALL pour what the computed pour of the source document pours. A Clearance record whose scope the pour does not read, carried back by the property, MUST refuse the polygons it could govern on the way back as it does in the source (`rule-scope`, then `depends-on-refused`), each reported `altium.zone-unpoured`, and the polygon itself MUST be written.

#### Scenario: Public row -04
- **GIVEN** public row `altium-third-party-pcbdoc-04`, whose source pour refuses its 9 polygons (4 `rule-scope`, 5 `depends-on-refused`) under a Clearance record of unread scope
- **WHEN** `uv run pytest tests/corpus/test_altium_pour_c0457.py` converts it to KiCad and back with the computed pour
- **THEN** the way back reports 9 `altium.zone-unpoured` and no `altium.zones-poured`, writes the 9 polygons, and loses no rule
