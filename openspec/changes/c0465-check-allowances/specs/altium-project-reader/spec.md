## ADDED Requirements

### Requirement: Short-Circuit and Net Antennae records map
`read.rules.map_rules` SHALL map the enabled ShortCircuit and NetAntennae records of a document that relax
their check (change c0465, design D5):
- When some enabled ShortCircuit record holds `ALLOWED=TRUE`, every enabled ShortCircuit record MUST map, and
  otherwise none MUST. When some enabled NetAntennae record holds a tolerance above 0, every enabled NetAntennae
  record MUST map, and otherwise none MUST. A record not mapped MUST stay `Unmapped` with `checked`.
- ShortCircuit MUST give one `short` rule over its two scopes, of severity `ignore` when `ALLOWED=TRUE` and
  `error` when `ALLOWED=FALSE`, at the record's priority.
- NetAntennae MUST give one `antenna` rule over its first scope with `max` = `NETANTENNAETOLERANCE`.
- A record of another key, or a value of `ALLOWED` other than `TRUE` and `FALSE`, MUST stay `Unmapped` with
  `keys`.
- The two kinds MUST leave `CHECKED_KINDS` for `RULE_KIND_MAP`, and the table "Rule kinds and their reading" of
  `rule-file.md` MUST list them as neutral.
- The warning `altium.rules.check-relaxed` MUST no longer be given, and MUST leave `TEXT_READ_CODES`.
- The Altium writer MUST write a `short` rule as a ShortCircuit record and an `antenna` rule as a NetAntennae
  record, with the keys of the public records (S-2243). A record read from a document is still carried as it
  was (c0434).

#### Scenario: An allowed short and a default rule
- **GIVEN** an authored rule file with a ShortCircuit `ALLOWED=TRUE` between `InNet('AGND')` and
  `InNet('DGND')` at priority 1, a ShortCircuit `ALLOWED=FALSE` `All`/`All` at priority 2, and a NetAntennae
  of tolerance 50 mil
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rule_allowances_c0465.py -q -n 0` maps it
- **THEN** it gives a `short` rule `ignore` between nets `AGND` and `DGND` governing over a `short` rule
  `error` `all`/`all`, an `antenna` rule of `max` 1 270 000 nm, no `Unmapped`, and no `check-relaxed`

#### Scenario: Nothing relaxed, nothing mapped
- **GIVEN** an authored rule file with one ShortCircuit `ALLOWED=FALSE` and one NetAntennae of tolerance 0
- **WHEN** the same test maps it
- **THEN** it gives no rule, and both records are `Unmapped` with `checked`
