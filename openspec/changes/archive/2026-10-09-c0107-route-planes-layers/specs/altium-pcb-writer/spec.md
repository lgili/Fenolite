## ADDED Requirements

### Requirement: Track layer rules in the Altium rule table
`fenolite.backends.altium.rulemap.TABLE` SHALL hold one row for the neutral kind `no_tracks` (`rules-model`, "Track layer rules"), last, as the kind is last in `RuleKind`, with the status `no-counterpart` and a note. This requirement extends "Rule lowering table": with it every kind of `model/rules.py`, thirteen of them, has exactly one row.
- The note MUST say that Altium's rule of the routing layers of a scope is the nearest counterpart and that its record (kind number, constraint keys) is in no public file read under the sources register, so the row cannot be `exact`.
- `lower` MUST write no record for a `no_tracks` rule and MUST name its kind, its selector and the reason `no-counterpart`; `fenolite build --target altium` then gives one `altium.not-lowered` (warning) with `where` `design-rules/no_tracks` and lists the rule in `result.rules.not_lowered` ("Rules in an Altium build"). The rule is never dropped without that issue.
- The table "The lowering table" of `docs/formats/altium/pcb-copper.md` MUST gain the row, with the source of the statement about Altium's rule (`S-0660`) and the label `INFERRED`.
- `lift` is unchanged: a record of that Altium kind in a document is counted among the records it does not map.
- The row MAY become `exact` only through a later change that registers a public file holding the record.

#### Scenario: Thirteen rows
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k complete` compares the kinds of `model/rules.py` with `TABLE` and with the page's table
- **THEN** every kind has exactly one row, the last is `no_tracks` with the status `no-counterpart` and a note, and the page's table equals `TABLE`

#### Scenario: A track layer rule in an Altium build
- **GIVEN** the four-layer blink variant with `design.rules.rule("sig-outer", "no_tracks", where=select.netclass("SIG"), layers=("In1.Cu", "In2.Cu"))`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rules.py -k no_tracks` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` hold one `altium.not-lowered` warning with `where` `design-rules/no_tracks` naming `sig-outer`, `result.rules.not_lowered` holds it with the reason `no-counterpart`, and the PCB document holds the rule records of the same script without the rule
