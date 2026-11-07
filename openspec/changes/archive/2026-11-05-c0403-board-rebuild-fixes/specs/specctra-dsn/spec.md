## ADDED Requirements

### Requirement: Clearance rules are lowered in rule order
`write_dsn` SHALL lower clearance rules between net classes in `rule_precedence` order, so the governing rule of each class pair sets its `class_class` value, a lower one included; board-wide clearance rules MUST stay floors. A governing rule between the nets of one class MAY lower that class below its own clearance, and the class MUST then keep its previous value against every other written class through `class_class`. When the file holds nets without a class, or a board-wide rule is above the governing value, the higher value MUST be written with one `specctra.rule-widened` naming the rule (change c0403, F8).

#### Scenario: A higher-priority pair rule below a one-sided rule
- **GIVEN** a one-sided 3 mm clearance rule on class `PHASE_U` at priority 2 and a (`CTRL`, `PHASE_U`) rule of 1.85 mm at priority 1
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn_rule_order.py` writes the design file
- **THEN** `class_class` (`CTRL`, `PHASE_U`) holds 1.85 mm and every other pair of `PHASE_U` 3 mm

#### Scenario: A lower rule between the nets of one class
- **GIVEN** class `PHASE_U` with a 3 mm clearance and a (`PHASE_U`, `PHASE_U`) rule of 0.3 mm
- **WHEN** the design file is written without and with a net that has no class
- **THEN** without it the class rule holds 0.3 mm and each other class keeps 3 mm through `class_class`; with it the class keeps 3 mm and one `specctra.rule-widened` names the rule
