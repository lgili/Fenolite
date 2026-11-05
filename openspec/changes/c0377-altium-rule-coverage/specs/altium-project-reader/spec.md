## ADDED Requirements

### Requirement: Operators in any letter case
`parse_scope` SHALL read a query operator written in any letter case (`and`, `AND`, `or`, `OR`, `not`,
`NOT`) as `And`, `Or` or `Not`. The reading is `INFERRED` (`H-A-RD-PRJ-SCOPE-CASE`): no public source
states Altium's letter-case rule.

#### Scenario: A lower-case Or
- **WHEN** the scope is `IsVia or IsTrack`
- **THEN** the selector is `or(item_kind via, item_kind track)`

### Requirement: Net scope of a rule on one object
A Width, Routing Via Style, Hole Size or Minimum Annular Ring record SHALL map with `NETSCOPE` `AnyNet` or
`DifferentNets` (`H-A-RD-PRJ-NETSCOPE-ONE`, `INFERRED`); any other value, and a Clearance whose
`NETSCOPE` is not `DifferentNets`, SHALL stay unmapped with the reason `net-scope`.

#### Scenario: A Width rule of DifferentNets
- **WHEN** a Width record holds `NETSCOPE=DifferentNets`
- **THEN** it maps to a `track_width` rule

#### Scenario: A Clearance of AnyNet
- **WHEN** a Clearance record holds `NETSCOPE=AnyNet`
- **THEN** it is unmapped with the reason `net-scope`
