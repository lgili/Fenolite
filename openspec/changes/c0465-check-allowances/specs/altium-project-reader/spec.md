## ADDED Requirements

### Requirement: Short-Circuit records map and native antenna records travel

When an enabled ShortCircuit record holds `ALLOWED=TRUE`, `read.rules.map_rules` SHALL map every enabled
ShortCircuit record in the document. Each gives one `short` rule over its two scopes at the record's
priority, with severity `ignore` for `ALLOWED=TRUE` or `error` for `ALLOWED=FALSE`. When no enabled record
allows a short, the records SHALL remain unmapped with reason `checked`. Extra keys and other values of
`ALLOWED` SHALL remain unmapped.

A NetAntennae record SHALL travel as a native record and remain unmapped as a portable rule. The import
and KiCad conversion SHALL report the coverage limit. The Altium round trip SHALL restore the record's
tolerance, scope, enabled state and priority. Altium Designer 24.5.2.23's DRC measures antennae differently
from the portable centre-line check (S-2245, S-2298).

The Altium writer SHALL keep writing explicit authored `short` and `antenna` rules with the public record
keys. This writes the declared tolerance field; it does not establish equal DRC verdicts. The legacy
warning `altium.rules.check-relaxed` SHALL remain withdrawn.

#### Scenario: An allowed short and a native antenna rule
- **GIVEN** an allowing ShortCircuit for AGND and DGND, a default ShortCircuit that forbids shorts and
  a native NetAntennae rule of tolerance 50 mil
- **WHEN** Fenolite imports the records
- **THEN** both ShortCircuit records become neutral rules and the antenna record is carried with its
  original tolerance, without installing a portable allowance

#### Scenario: Preserve a native rule through KiCad
- **WHEN** Fenolite converts an authored Altium project with a native NetAntennae rule to KiCad and back
- **THEN** the first conversion reports that Altium checks the carried native rule, and the return
  writes its native fields unchanged
