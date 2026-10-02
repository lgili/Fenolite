# KiCad custom rules (`.kicad_dru`)

A project's custom design rules live in `<project>.kicad_dru`, next to the board and the project file.
`fenolite.backends.kicad.dru` reads and writes these files in the full dialect, and
`fenolite.backends.kicad.lowering.lower_rules` lowers the model's `RuleSet` to one. The closed grammar
that both directions share is in `fenolite.backends.kicad.rulemap`. This page describes the format in
Fenolite's own words; sources are listed in `docs/evidence/sources.md`.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| A rules file has no root list: it is a sequence of top-level lists, `(version 1)` first, then `(rule NAME …)` lists | S-0010, S-0038 | INFERRED | H-K-TOK-CONSTANTS |
| A rule holds an optional `layer` clause, an optional `condition` string, one or more `constraint` lists and an optional `severity`; the syntax summary lists them as `(rule <name> [(severity)] [(layer)] [(condition)] (constraint …))` | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-DIALECT |
| The header stays `(version 1)` in 9.0 and 10.0; no KiCad command writes a rules file | S-0010, S-0038 | INFERRED | H-K-TOK-CONSTANTS |
| A line whose first non-blank character is `#` is a comment, between rules and inside a rule | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-DIALECT |
| Values may carry the units `mm`, `mil` (or `th`), `in` (or `"`); angles take `deg` or `rad`; `mm`, `mil` and `in` are exercised | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-DIALECT |
| A condition is an expression over the two items `A` and `B` of a check: properties such as `NetName`, `NetClass` and `Type`, functions such as `memberOfFootprint`, the operators `==`, `!=`, `&&`, `\|\|` and `!`, and `'…'` string literals inside the double-quoted condition; every form of the closed selector table selects the model's items | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-COND |
| String comparisons in conditions accept the wildcard `*` (`'PWR_*'` matches `PWR_A` and not `SIG_A`) | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-GLOB |
| String comparisons in conditions also accept `?` (not exercised; Fenolite refuses it) | S-0010, S-0038 | INFERRED | H-K-DRU-GLOB |
| Name comparisons ignore letter case: `A.NetName == 'lc1'` matches net `LC1` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-COND |
| A condition on side `A` alone matches an item pair in either item order | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-COND |
| When several rules match an item pair, the rule later in the file takes precedence | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-ORDER |
| A rule's severity is `error`, `warning`, `ignore` or `exclusion`; ignored rules are still matched and can override earlier rules | S-0010, S-0038 | INFERRED | H-K-DRU-ORDER |
| Constraint limits are `min`, `opt` and `max`; `clearance` and `edge_clearance` take `min`, `hole_size` takes `min` and `max`, `track_width` and `via_diameter` take all three; the `min` limit of each lowered kind is enforced | S-0010, S-0038, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-KIND |
| Board-setup minimums are absolute floors: a custom rule cannot lower them | S-0038 | INFERRED | H-K-DRU-KIND |
| Rules are read only with a project file next to the board, and any error disables every custom rule with exit 0 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-RULES-SILENT |
| 9.0.9 drops the whole file when one rule uses one of seven 10.0-only constructs (`bridged_mask`, `solder_mask_expansion`, `solder_paste_abs_margin`, `solder_paste_rel_margin`, `via_dangling`, the disallow kinds `through_via` and `blind_via`) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-RULES-DRIFT |
| Every constraint type and clause of the 9.0 manual loads on 9.0.9 and 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-RULES-FLOOR |
| A rule with a single-quoted name makes 9.0.9 and 10.0.6 drop the whole file, with exit 0 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-QUOTE |
| `assign_component_class` is a rules keyword at tag 10.0.6 and not at 9.0.0; no public page documents its shape | S-0034 | INFERRED | H-K-TOK-CONSTANTS |

## The dialect front end

`parse_rules(text, *, file="")` returns a `RulesDocument` of items in file order: `VersionItem`,
`RuleItem` and `CommentItem`.

- A line whose first non-blank character is `#` becomes a `CommentItem` with its exact text and line
  number, and is replaced by spaces of the same length before parsing, so offsets and line numbers do
  not move. A comment line inside a rule stays in that rule's text; the rule is marked `has_comment`
  and can only stay opaque.
- Only whole-line comments exist. A `#` after other content on a line is not a comment.
- A symbol atom containing `'` outside a double-quoted string (a single-quoted rule name) raises
  `FormatError` with `locator == "line N"`, because KiCad drops the whole file. A `'…'` literal inside
  a double-quoted condition is accepted.
- The rest is parsed with `versions.wrap_rules`. A missing `version` list is a `FormatError` (Fenolite
  policy). A version below 1 is too old, above 1 is future and read-only. A second `version` list, or
  an atom at top level, is a `FormatError`.
- `print_rules(items)` writes each item's text followed by a newline. Blank lines between items are not
  kept.

## The closed grammar

Fenolite lifts a rule into the model, and lowers a model rule, only through these tables. Anything else
stays an opaque slot with its exact text (`rules.kept-opaque`). These are Fenolite choices; KiCad's
semantics of each row are the hypotheses above.

### Kinds and limits

| kind | written constraint | limits |
|---|---|---|
| `clearance` | `clearance` | `min` |
| `edge_clearance` | `edge_clearance` | `min` |
| `track_width` | `track_width` | `min`, `opt`, `max` |
| `via_diameter` | `via_diameter` | `min`, `opt`, `max` |
| `hole_size` | `hole_size` | `min`, `max` |
| `via_drill` | `hole_size`, with `A.Type == 'Via'` as the first conjunct of the condition | `min`, `max` |

- Values are written as the shortest exact millimetre decimal of the nanometre value (`0.25mm`,
  `0.2032mm`), never rounded. Limits are written in the order `min`, `opt`, `max`.
- Values are read with `rulemap.parse_value`, which accepts `mm`, `mil` and `in` exactly. Other units
  and unitless values keep the rule opaque.
- Severity maps one to one for `error`, `warning` and `ignore`; `exclusion` keeps the rule opaque. A
  missing severity lifts as `error`.
- Via drill normal form: a lifted `hole_size` whose condition starts with `A.Type == 'Via'` stays
  `hole_size` with an `item_kind via` selector. `rulemap.normal_form` maps `via_drill` to that form.

### Selectors

Side `S` is `A` for `selector_a` and `B` for `selector_b`.

| model selector | condition text | `SELECTOR_SUPPORT` key |
|---|---|---|
| `all` (top level only) | no term | none |
| `net v` | `S.NetName == 'v'` | `net` |
| `netclass v` | `S.NetClass == 'v'` | `netclass` |
| `ref v` | `S.memberOfFootprint('v')` | `ref` |
| `item_kind v`, v in `track`, `via`, `pad`, `zone` | `S.Type == 'Track'`, `'Via'`, `'Pad'`, `'Zone'` | `item_kind` |
| `and(x, y, …)` | `(x && y && …)` | `and` |
| `or(x, y, …)` | `(x \|\| y \|\| …)` | `or` |
| `not(x)` | `!(x)` | `not` |
| `*` inside a leaf value | the value as written | `glob` |
| a `selector_b` other than `all` | the `B.` side | `selector_b` |
| a non-empty `Rule.layers` | `(layer "<name>")` | `layer_clause` |

- The two sides combine as `<A> && <B>`, each a leaf or a parenthesised compound; an `all` side adds no
  term. `selector_b` is allowed only for `clearance`.
- `rulemap.SELECTOR_SUPPORT` maps each key to the KiCad majors on which its `dru-cond-<key>` probe
  passed. A key is written for a target only when the target is in its entry.
- Refused with `rules.unsupported-selector`: the `layer` op (use `Rule.layers`), `all` below the top
  level, an `item_kind` value outside the table, a value containing `'`, `"`, `?`, `[` or `]`, and any
  key outside its entry for the target. A selector is never approximated.
- A net with several classes compares a composite class name in KiCad; lowered designs assign one class
  per net (c0010), so `netclass` compares one name.

### Layers and names

- An empty `Rule.layers` writes no layer clause; one layer writes `(layer "<name>")`; several layers
  write one KiCad rule per layer, in tuple order. A layer name must pass `layers.is_canonical`; other
  names give `rules.unsupported-layer`. The `outer` and `inner` forms keep a rule opaque on read.
- `lower_rules` names rules `fenolite_<priority>_<slug>`, where the slug is the rule name in lower case
  with each run of characters outside `[a-z0-9]` replaced by `_`, trimmed of `_`, or `rule` when empty.
  A rule written once per layer gets `_<layer slug>` appended; a repeated name gets `_2`, `_3`, … in
  emission order. Names are double-quoted.

## Priority order

- `lower_rules` writes rules with priority 0 ("unset") first, then in descending priority, so priority
  1 (the highest in the model) comes last and governs under the later-wins rule (`H-K-DRU-ORDER`).
- Ties are broken by rule name, then by id. This tie rule is a Fenolite choice: the model gives such
  rules equal weight.
- `read_rules` gives each lifted rule the priority "number of rule items after it, plus 1", so the
  last rule has priority 1.

## Writing and target gating

- `write_rules` writes `(version 1)` first, then follows the file slots of the rule set: comments and
  opaque rules verbatim in place, the k-th modelled slot as the k-th rule, extra rules after the last
  modelled slot. A rule keeps its clause order; a clause the model now needs is inserted in the order
  `layer`, `condition`, `constraint`, `severity` (Fenolite choice). A rule without clause slots always
  carries `(severity …)`, so a project severity override cannot change it.
- Every opaque rule is checked with `check_emittable` on a node holding `(version 1)` and that rule.
  For target 9, a `kicad.token.too-new` or `kicad.token.uninventoried` issue refuses the rule
  (`RulesLossError`, FEN-7001), because 9.0.9 would drop the whole file; `allow_lossy` drops the rule
  instead, with `rules.dropped-for-target`. For target 10, an uninventoried rule is kept with its
  warning; `assign_component_class` is such a rule.
- Before text is returned, the writer self-checks it: the text parses, `check_emittable` reports no
  error, every modelled rule lifts back to its normal form, and every comment and opaque rule comes
  back in order. A failure raises `RulesSelfCheckError` (FEN-1001).
- Fenolite ships no requirement values: `lower_rules` writes only the user's rules, and an empty rule
  set lowers to `(version 1)` alone. Diagnostic rules such as the canary appear only in temporary
  oracle copies.

## Issue codes

| code | severity | when |
|---|---|---|
| `rules.unsupported-selector` | error | a selector outside the closed grammar for the target |
| `rules.unsupported-limit` | error | a limit the kind does not take, or no limit |
| `rules.unsupported-layer` | error | a layer name that `layers.is_canonical` refuses, or a layer clause for a target outside the `layer_clause` entry |
| `rules.dropped-for-target` | warning | `allow_lossy` dropped a rule the target cannot load |
| `rules.kept-opaque` | info | `read_rules` kept a rule opaque, naming the reason |

The writers also pass on `kicad.token.uninventoried` warnings for target 10.

## Oracle outcomes

The rules oracle (`tests/kicad/rules/`) runs every proof on a bench that carries the canary rule of
`tests/data/kicad/tokens/canary/canary.kicad_dru`; a report without the canary violation fails the test.
Outcomes per `kicad-cli` version are pinned in `docs/evidence/kicad/probes/<version>.json` under the
`dru-*` probe ids.

| kind | violation type observed (9.0.9 and 10.0.6) |
|---|---|
| `clearance` | `clearance` |
| `edge_clearance` | `copper_edge_clearance` |
| `track_width` | `track_width` |
| `via_diameter` | `via_diameter` |
| `hole_size` | `drill_out_of_range` |
| `via_drill` | `drill_out_of_range` |

Per-major outcome of each row, from the oracle on 2026-10-02 (local `kicad-cli` 10.0.6 and the pinned
9.0.9 image):

| hypothesis | 9.0.9 | 10.0.6 |
|---|---|---|
| `H-K-DRU-ORDER` (later rule governs) | holds | holds |
| `H-K-DRU-DIALECT` (comments, units, literals) | holds | holds |
| `H-K-DRU-COND` (every selector key) | holds | holds |
| `H-K-DRU-GLOB` (`*`) | holds | holds |
| `H-K-DRU-QUOTE` (single-quoted name drops the file) | holds | holds |
| `H-K-DRU-KIND` (each kind) | holds | holds |

**Letter case.** KiCad compares names without regard to case, while the model's selectors are
case-sensitive. Lowering writes names as given, so two nets or classes whose names differ only in case
would both be selected by a rule written for one of them; the build (c0011), which knows the nets,
refuses such designs.
