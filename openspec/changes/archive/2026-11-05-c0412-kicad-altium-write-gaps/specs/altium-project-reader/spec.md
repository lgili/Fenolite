## MODIFIED Requirements

### Requirement: Closed scope grammar
`fenolite.backends.altium.read.scope.parse_scope(text)` SHALL return a neutral `Selector`, or a string that says why the expression is outside the grammar. It MUST accept only this grammar, with the spellings as written here:

| expression | selector |
|---|---|
| `All` | `all` |
| `InNet('v')` | `net v` |
| `InNetClass('v')` | `netclass v` |
| `InComponent('v')` | `ref v` |
| `IsTrack`, `IsVia`, `IsPad` | `item_kind track`, `via`, `pad` |
| `InPolygon`, `InPoly` | `item_kind zone` |
| `x And y And …`, `x && y && …` | `and(x, y, …)` |
| `x Or y Or …`, `x \|\| y \|\| …` | `or(x, y, …)` |
| `Not x` | `not(x)` |
| `(x)` | `x` |

- Spaces around tokens MUST be ignored. A value `v` MUST be non-empty and MUST NOT hold `'`, `*`, `?`, `[` or `]`, because a neutral leaf value is a glob.
- One parenthesis level MUST hold one kind of operator: an expression that mixes `And`, `Or` and `Not` without parentheses is refused, because no permitted source states the precedence. `Not` MUST be followed by a leaf or a parenthesised expression and MUST be the whole of its level.
- `InPolygon` (alias `InPoly`) is the attribute check that Altium names for the copper of a polygon pour in a clearance rule (S-1702, change c0412). It takes no argument; `InNamedPolygon('…')` and `InPolygonClass('…')` stay outside the grammar.
- `All` below the top level, `OnLayer` and every other layer function, every other function or field comparison, and any text left over MUST be refused. A scope MUST never be approximated.

#### Scenario: Class and item kind
- **GIVEN** `InNetClass('HV') And (Not IsVia)`
- **WHEN** `parse_scope` is called
- **THEN** it returns `and(netclass HV, not(item_kind via))`

#### Scenario: Pour copper
- **GIVEN** `InPolygon And (Not InNetClass('HV'))` and `InPoly`
- **WHEN** `parse_scope` is called on each
- **THEN** it returns `and(item_kind zone, not(netclass HV))` and `item_kind zone`

#### Scenario: Mixed operators without parentheses
- **GIVEN** `InNet('A') Or InNet('B') And IsTrack`
- **WHEN** `parse_scope` is called
- **THEN** it returns a string that names the mixed operators, and a rule with this scope is `Unmapped` with the reason `scope`

#### Scenario: Layer and wildcard refused
- **GIVEN** the expressions `OnLayer('Top Layer')` and `InNet('PWR*')`
- **WHEN** `parse_scope` is called on each
- **THEN** both return a string, the first naming `OnLayer` and the second the character `*`
