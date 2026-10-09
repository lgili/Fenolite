## MODIFIED Requirements

### Requirement: Rule kinds and limits
The thirteen model kinds SHALL lower one to one, with these constraints and limits:

| kind | written constraint | limits |
|---|---|---|
| `clearance` | `clearance` | `min` |
| `edge_clearance` | `edge_clearance` | `min` |
| `track_width` | `track_width` | `min`, `opt`, `max` |
| `via_diameter` | `via_diameter` | `min`, `opt`, `max` |
| `hole_size` | `hole_size` | `min`, `max` |
| `via_drill` | `hole_size`, with `A.Type == 'Via'` as the first conjunct of the condition | `min`, `max` |
| `hole_to_hole` | `hole_to_hole` | `min` |
| `hole_clearance` | `hole_clearance` | `min` |
| `annular_width` | `annular_width` | `min` |
| `courtyard_clearance` | `courtyard_clearance` | `min` |
| `silk_clearance` | `silk_clearance` | `min` |
| `creepage` | `creepage` | `min` |
| `no_tracks` | `disallow track`, one rule per layer ("Track layer rules") | none |

- Values MUST be written as the shortest exact millimetre decimal of the nanometre value, with the unit `mm` (`core.units.format_length`). They MUST never be rounded.
- Limits MUST be written in the order `min`, `opt`, `max`.
- A limit outside the table MUST give the error `rules.unsupported-limit`, and so MUST a rule with no limit of any kind but `no_tracks`, whose normal form holds none.
- `severity` MUST map one to one to `(severity error|warning|ignore)`, and a lowered rule MUST always carry its severity clause.
- Each of the first six kinds MUST be enforced by `kicad-cli` 9.0.9 and 10.0.6 on the items its condition selects (`H-K-DRU-KIND`). Each of the six kinds from `hole_to_hole` to `creepage` MUST be written only for the majors of its `KIND_SUPPORT` entry ("Kind support by major", `H-K-DRU-KIND-2`), and its DRC types MUST be listed in `docs/formats/kicad/rules.md`; `no_tracks` follows the same two rules with its own probe (`H-K-DRU-NOTRACKS`). A `min` of 0 MUST be accepted for those six kinds.
- `model.rules.RuleKind` MUST list the kinds in the order of the first twelve as before this change, with `no_tracks` last.

#### Scenario: Exact millimetres
- **GIVEN** a `track_width` rule with `min=250_000`, `opt=300_000` and `max=1_000_000`
- **WHEN** it is lowered
- **THEN** its constraint is `(constraint track_width (min 0.25mm) (opt 0.3mm) (max 1mm))`

#### Scenario: Via drill becomes a hole size for vias
- **GIVEN** a `via_drill` rule on `net PWR` with `min=300_000`
- **WHEN** it is lowered
- **THEN** its constraint is `(constraint hole_size (min 0.3mm))` and its condition is `"A.Type == 'Via' && A.NetName == 'PWR'"`

#### Scenario: Clearance with a maximum
- **GIVEN** a `clearance` rule with `min=200_000` and `max=500_000`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised and its issues hold one `rules.unsupported-limit` naming the rule

#### Scenario: Each kind is enforced
- **GIVEN** a bench with one probed item and one control item per kind, each 4 mm from other copper, and the canary
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_kinds.py` runs on 9.0.9 and on 10.0.6
- **THEN** for each kind the report holds one violation naming the probed item's uuid, none naming the control item, and the canary violation

#### Scenario: Hole-to-hole rule
- **GIVEN** a `hole_to_hole` rule on `net PWR` with `min=300_000`
- **WHEN** it is lowered for target 10
- **THEN** its constraint is `(constraint hole_to_hole (min 0.3mm))` and its condition is `"A.NetName == 'PWR'"`

#### Scenario: Limit outside a new kind
- **GIVEN** an `annular_width` rule with `min=100_000` and `max=300_000`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised with one `rules.unsupported-limit` naming the rule

#### Scenario: Thirteen kinds, one without a limit
- **WHEN** `uv run pytest tests/unit/dsl/test_minimums.py tests/unit/backends/kicad/test_lowering.py -k "kinds or no_tracks"` counts the kinds of `RuleKind` and lowers a `no_tracks` rule without a limit and a `clearance` rule without a limit
- **THEN** `RuleKind` holds thirteen kinds with `no_tracks` last, the first rule is written, and the second raises `RulesLossError` with one `rules.unsupported-limit`

## ADDED Requirements

### Requirement: Track layer rules
A rule of the kind `no_tracks` ("Rule kinds and limits") SHALL mean: tracks and arcs of the items that `selector_a` selects are not allowed on the copper layers of `layers`. This requirement states, for this one kind, what "Closed selector grammar", "Rule layers and lowered names" and "Kind support by major" state for the others (`H-K-DRU-NOTRACKS`). It is the rule kind, and not the `no_tracks` flag of a keep-out (`model.board.Keepout.no_tracks`), which forbids tracks inside an outline whatever their net.
- **Limits.** A `no_tracks` rule takes no limit: a `min`, `opt` or `max` MUST give `rules.unsupported-limit`.
- **Selectors.** `selector_a` MUST be `all`, or `net` and `netclass` leaves combined with `and`, `or` and `not`; `selector_b` MUST be absent. Anything else MUST give `rules.unsupported-selector`. `rulemap.KIND_SELECTORS["no_tracks"]` MUST hold that grammar.
- **Layers.** `layers` MUST hold at least one layer; an empty tuple MUST give `rules.unsupported-layer`. Each layer follows "Rule layers and lowered names".
- **Lowering.** `lower_rules` MUST write one rule per layer, named as "Rule layers and lowered names" states, with `(layer "<name>")`, the condition of `selector_a` (none for `all`), `(constraint disallow track)` and the severity clause.
- **Targets.** `rulemap.KIND_SUPPORT["no_tracks"]` MUST hold the majors whose probe `dru-kind-no_tracks` recorded `present`; a target outside it gives `rules.kind-unchecked` ("Kind support by major").
- The model schema `schemas/fenolite.model.v0/rules.json` MUST be regenerated with the new kind. A document that holds a `no_tracks` rule cannot be read by Fenolite 0.2.x or 0.3.x, whose `RuleKind` lacks the value; a document without one is unchanged, byte for byte.

#### Scenario: A class kept off the inner layers
- **GIVEN** a rule `sig-outer` of kind `no_tracks`, priority 0, `selector_a` `netclass SIG`, `layers == ("In1.Cu", "In2.Cu")`, severity `error`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lowering.py -k no_tracks` lowers it for target 10
- **THEN** two rules are written, `"fenolite_0_sig_outer_in1_cu"` with `(layer "In1.Cu")` and `"fenolite_0_sig_outer_in2_cu"` with `(layer "In2.Cu")`, each with `(condition "A.NetClass == 'SIG'")`, `(constraint disallow track)` and `(severity error)`

#### Scenario: Refusals
- **GIVEN** three `no_tracks` rules: one with `min=100_000`, one with `selector_b` set, one with no layer
- **WHEN** they are lowered
- **THEN** `RulesLossError` is raised with one `rules.unsupported-limit`, one `rules.unsupported-selector` and one `rules.unsupported-layer`

#### Scenario: Support follows the probes
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_rulemap.py -k kind_support` compares `KIND_SUPPORT["no_tracks"]` with the probe files of both majors
- **THEN** it equals the set of majors where `dru-kind-no_tracks` is `present`
