## MODIFIED Requirements

### Requirement: Conversion report
A `ConversionReport` SHALL hold one row per kind of `fenolite.convert.report.KINDS` that the source holds or the write touches, in table order, each with `kind`, `source`, `written`, `changed`, `lost`, `kept` and `reasons`. `reasons` MUST count every changed, lost or kept item under its own reason, sorted by count and then by reason; a first reason standing for all MUST NOT be used. A kept item is one the target cannot hold and the model keeps for a write back to the source's format (change c0424): `written` MUST be `source` less the changed, lost and kept items, a row's JSON MUST show `kept` only when it is above zero, and a kept item MUST NOT make the report lossy.

#### Scenario: Reasons are counted apart
- **GIVEN** a KiCad board with one custom pad and two pads without a number
- **WHEN** it is converted to Altium with `allow_lossy=True`
- **THEN** the row `pad` has `lost` 3 and two reasons, one with count 2 and one with count 1

#### Scenario: Kept items are not losses
- **WHEN** `uv run pytest tests/unit/convert/test_report.py -k kept` makes a report with one kept rule and one written rule
- **THEN** the row `rule` has `source` 2, `written` 1 and `kept` 1, the reason's outcome is `kept`, and the report is not lossy

## ADDED Requirements

### Requirement: Fate of every Altium rule record
The conversion of an Altium board to KiCad SHALL give each rule record of the source document exactly one fate, from the one table `convert.altium_rules.FATES`: written, changed, kept, or lost.
- A record MUST be lost only when it is malformed.
- A disabled record and a record of a kind KiCad cannot hold MUST be kept, with a reason that names the format limit.
- A rule that the KiCad lowering refuses MUST be kept when it came from a kept record.
- The per-kind group losses `unmapped-rule-group-<n>` MUST NOT be reported.
- Kept rules MUST be reported by one `convert.kept` info per kind.

#### Scenario: One rule of each kind
- **GIVEN** an authored PCB document with one rule record of each kind of the table and one disabled record
- **WHEN** `uv run pytest tests/unit/convert/test_altium_rule_fates.py` converts it to KiCad
- **THEN** the row `rule` lists no lost item, every record is written, changed or kept, and the written rules file holds the silk, courtyard, pair and `disallow track` rules

### Requirement: Limits the KiCad rule cannot take
When the KiCad lowering refuses an imported rule only for a limit that the kind's KiCad constraint does not take, the conversion SHALL write the rule without that limit and report it as `changed`, and the model SHALL keep the limit.

#### Scenario: Preferred via drill
- **GIVEN** an imported Routing Via Style rule with a minimum, preferred and maximum hole
- **WHEN** it is converted to KiCad, and when the board is imported with `import --to python`
- **THEN** the rules file holds the via drill's `min` and `max`, the row `rule` lists the rule as changed, and `design.py` holds the drill limits

### Requirement: Shadowed imported rules keep Altium's order
The governing rule of two overlapping imported rules SHALL be the one with the higher Altium priority (the lower number), in the converted design and after `import --to python` and a build.

#### Scenario: A net rule below an All rule
- **GIVEN** an authored document whose clearance for all objects has priority 1 and whose clearance of one net has priority 2
- **WHEN** `uv run pytest tests/unit/convert/test_altium_rule_fates.py -k shadowed` imports it to Python and builds it
- **THEN** `rules.shadowed` names the All rule as governing over the net rule, as Altium applies them
