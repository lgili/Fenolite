## ADDED Requirements

### Requirement: Rule lowering table
`fenolite.backends.altium.rulemap.TABLE` SHALL be the closed table that maps each neutral rule kind to the Altium rule kind that carries it. Each row MUST hold the neutral kind, the Altium kind, the constraint fields, the scope forms it supports, and either `exact` or one reason of `NOT_LOWERED_REASONS` (`no-counterpart`, `scope-unsupported`, `value-unsupported`, `unit-loss`).
- Every neutral rule kind of `model/rules.py` MUST have a row. A row MUST be `exact` only when `docs/formats/altium/pcb-copper.md` records, with a public source and a label, that the Altium constraint is the neutral one.
- `lower(rules)` MUST return the rule records of the `exact` rows and, for every rule that is not written, its kind, selector and reason. It MUST never write a rule whose value or scope differs from the neutral rule's beyond the 2 nm of the PCB unit.
- `lift(records)` MUST return the neutral rules of the records that an `exact` row describes, and the count of the others by Altium kind.
- `lift(lower(rules).records)` MUST equal the lowered subset of `rules`.

#### Scenario: Every kind has a row
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k complete` compares the kinds of `model/rules.py` with `TABLE`
- **THEN** every kind has exactly one row, and every `exact` row is cited in `docs/formats/altium/pcb-copper.md`

#### Scenario: Round trip of the table
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k roundtrip` lowers and lifts generated rule sets
- **THEN** the lifted rules equal the lowered subset, within 2 nm

#### Scenario: A rule with no counterpart
- **GIVEN** a rule of a kind whose row has the reason `no-counterpart`
- **WHEN** `lower` runs
- **THEN** no record is written for it, and the result names its kind, its selector and that reason

### Requirement: Scoped rule records
Rule records SHALL carry the scope of their rule as an expression of the closed scope grammar of `altium-project-reader` ("Closed scope grammar"): all objects, a net, a net class, a layer, and the conjunction of those; a pair rule uses both scope fields.
- Rules of one kind MUST be written in the order of the neutral rules, most specific first, with priorities that follow that order.
- A selector outside the grammar MUST give the reason `scope-unsupported` for that rule only; the other rules of the kind are written.
- Rule names MUST be unique in the document and derived from the kind and the selector, so that two builds give equal names.

#### Scenario: Class rule above the general rule
- **GIVEN** a design with a track width for all nets and another for the class `PWR`
- **WHEN** the PCB document is written and read back
- **THEN** two Width rules exist, the class rule with the scope `InNetClass('PWR')` and the higher priority
