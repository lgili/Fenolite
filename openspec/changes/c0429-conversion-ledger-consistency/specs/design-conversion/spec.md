## ADDED Requirements

### Requirement: Report and issues agree
The issues of a conversion SHALL agree with its report, for every kind of `KINDS`: one `convert.lossy`
warning per row with lost items, with the kind as `where` and the counts per lost reason, whatever the
kind's loss class; one `convert.changed` info per row with changed items; one `convert.kept` info per row
with kept items. A row without lost, changed or kept items MUST NOT have that issue. The refusal of a
`refuse` kind without `allow_lossy` is unchanged.

#### Scenario: A lost report kind warns
- **GIVEN** a report whose `rule` row (loss class `report`) has lost items
- **WHEN** the issues of the conversion are built with `allow_lossy`
- **THEN** one `convert.lossy` warning has `where` `rule`, and the conversion does not refuse without
  `allow_lossy`

#### Scenario: Every kind
- **GIVEN** for each kind of `KINDS` a report with one lost, one changed and one kept item of that kind
- **WHEN** its issues are built
- **THEN** the kinds of `convert.lossy`, `convert.changed` and `convert.kept` are each exactly that kind
