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
| The manuals call the board-setup minimums absolute floors that no rule may override, but on 9.0.9 and 10.0.6 a board-wide custom rule governs below them | S-0038, S-0010, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-RULE-2 |
| A board-wide custom clearance rule governs the items of a net class with a larger clearance | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-CLASS |
| Any error disables every custom rule with exit 0; a `.kicad_dru` next to the board is read with or without a project file (the net classes need one) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-RULES-SILENT |
| 9.0.9 drops the whole file when one rule uses one of seven 10.0-only constructs (`bridged_mask`, `solder_mask_expansion`, `solder_paste_abs_margin`, `solder_paste_rel_margin`, `via_dangling`, the disallow kinds `through_via` and `blind_via`) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-RULES-DRIFT |
| Every constraint type and clause of the 9.0 manual loads on 9.0.9 and 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-TOK-RULES-FLOOR |
| A rule with a single-quoted name makes 9.0.9 and 10.0.6 drop the whole file, with exit 0 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-QUOTE |
| `assign_component_class` is a rules keyword at tag 10.0.6 and not at 9.0.0; no public page documents its shape | S-0034 | INFERRED | H-K-TOK-CONSTANTS |
| `hole_to_hole`, `hole_clearance` and `annular_width` rules with a `min` and a net condition are enforced, under violation types of the same names; 9.0.9 prints a 1 mm hole-to-hole limit as `0.9995 mm` | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-KIND-2 |
| A `courtyard_clearance` rule is reported as `courtyards_overlap` ("Courtyards overlap (rule … clearance 1.0000 mm; actual 0.5100 mm)"); it selects a footprint with `A.Reference == '<ref>'`, and `A.memberOfFootprint('<ref>')` selects nothing for it | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-COURTYARD |
| A `silk_clearance` rule is reported as `silk_overlap`, between the silkscreen of two footprints and between a footprint's silkscreen and another footprint's courtyard rectangle; `silk_over_copper` is its type against pads | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-KIND-2 |
| A `creepage` rule on two nets (`A.NetName == … && B.NetName == …`) is reported as `creepage` on 10.0.6, 50 µm above the surface distance and not 50 µm below it; 9.0.9 loads the same rule and reports nothing for it | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-KIND-2 |
| KiCad reports one violation per item pair in the copper clearance test: a pair whose copper clearance fails gets a `clearance` entry and no `hole_clearance` entry, so a clearance rule that matches every pair hides the hole clearance of the pairs it flags | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-KIND-2 |
| A board-wide `hole_clearance`, `hole_to_hole` or `annular_width` rule governs below the template's board-setup minimum of its kind (0.25 mm, 0.25 mm and 0.1 mm): an item between the two is reported without the rule and not with it | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-MIN-RULE-3 |
| The later of two `hole_to_hole` rules that match one via pair governs, as for clearance | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRU-KIND-2 |
| `A.inDiffPair('<base>')` matches the two nets named `<base>` plus a last character `P` and `N`, or `+` and `-` (`X_P`/`X_N` with the base `X` or `X_`, `X+`/`X-`, `X_DP`/`X_DN`, `XP`/`XN`); letter case counts, and `X_DP`/`X_DM`, `X_p`/`X_n` and `X_P`/`X-` are not a pair | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DIFFPAIR-NAMES |
| `(constraint disallow track)` with `(layer "<name>")` and a condition on `A.NetName` gives one `items_not_allowed` violation per track of the selected net on that layer, none for its tracks on another layer and none for another net's tracks on the layer (10.0.6; a condition on `A.NetClass` selects as in every other rule, `H-K-DRU-COND`) | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRU-NOTRACKS |
| 9.0.9 reports the same for `disallow track` (measured on 2026-10-05; its probe is not yet recorded in `9.0.9.json`, so the kind is written for target 10 only) | S-0029 | INFERRED | H-K-DRU-NOTRACKS |

## Board-wide rules and board-setup minimums

A board-wide rule (selector `all`, no second selector, no layers) is written here as a custom rule, as
every modelled rule is, and also sets the matching board-setup minimum of the project file. The
mapping, the value rule and the conflict reports are in `project.md`, "Board-setup minimums".

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
| `hole_to_hole` | `hole_to_hole` | `min` |
| `hole_clearance` | `hole_clearance` | `min` |
| `annular_width` | `annular_width` | `min` |
| `courtyard_clearance` | `courtyard_clearance` | `min` |
| `silk_clearance` | `silk_clearance` | `min` |
| `creepage` | `creepage` | `min` |
| `no_tracks` | `disallow track`, one rule per layer | none |

- The last six kinds (change c0071) take `min` only, which is what the oracle measured, and a `min` of 0
  is allowed for them.
- `rulemap.KIND_SUPPORT` maps each kind to the KiCad majors on which `kicad-cli` enforces it as written:
  both majors for every kind but `creepage` and `no_tracks`, which hold 10 only (`no_tracks` until its probe
  is recorded on 9.0.9). A modelled rule of a kind outside its
  entry gives `rules.kind-unchecked`; `allow_lossy` drops it with `rules.dropped-for-target`.
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

### Selectors per kind

`rulemap.KIND_SELECTORS` narrows the grammar for the kinds of change c0071. The six kinds of v0.1 take
the whole table above.

| kind | side A | side B | layer clause |
|---|---|---|---|
| `hole_to_hole`, `hole_clearance`, `annular_width` | the whole table | no | no |
| `courtyard_clearance` | `all`, or `ref` leaves without `*`, combined with `and`, `or` and `not` | no | no |
| `silk_clearance` | `all` only | no | no |
| `creepage` | `all`, or `net` and `netclass` leaves, combined with `and`, `or` and `not` | the same | no |
| `no_tracks` | `all`, or `net` and `netclass` leaves, combined with `and`, `or` and `not` | no | required: at least one layer |

- A courtyard rule checks footprints, so its `ref v` is written `A.Reference == 'v'`. A courtyard rule
  read with `memberOfFootprint` stays opaque: writing it back with `Reference` would change what KiCad
  checks.
- A silkscreen rule is board-wide because KiCad also applies it between a footprint's silkscreen and the
  courtyard of its neighbours; a narrower selector would promise a precision the check does not have.
- Anything outside a kind's row gives `rules.unsupported-selector` on write and keeps the rule opaque on
  read.

### Track layer rules (c0107)

A rule of the kind `no_tracks` keeps the tracks and arcs of the items it selects off its layers. It is the
rule kind, not the `no_tracks` flag of a keep-out (`model.board.Keepout.no_tracks`), which forbids tracks
inside an outline whatever their net.

- It takes no limit (a `min`, `opt` or `max` gives `rules.unsupported-limit`), no B side
  (`rules.unsupported-selector`) and at least one layer (`rules.unsupported-layer` without one).
- `lower_rules` writes one KiCad rule per layer: `(layer "<name>")`, the condition of side A (none for
  `all`), `(constraint disallow track)` and the severity. Names follow "Layers and names".
- `read_rules` lifts a rule whose constraint is `disallow track` alone, with a layer clause that names one
  KiCad layer and a condition in the kind's grammar, into a `no_tracks` rule with that layer. Every other
  `disallow` rule (another item type, several item types, `(layer inner)` or `(layer outer)`, no layer
  clause) stays opaque with `rules.kept-opaque`.
- KiCad reports a violation of the rule as `items_not_allowed`.
- `fenolite route` reads these rules to choose the layers a net may use (`docs/routing.md`).

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
| `rules.kind-unchecked` | error | a modelled rule of a kind whose `KIND_SUPPORT` entry lacks the target |
| `rules.dropped-for-target` | warning | `allow_lossy` dropped a rule the target cannot load or does not check |
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
| `hole_to_hole` | `hole_to_hole` |
| `hole_clearance` | `hole_clearance` |
| `annular_width` | `annular_width` |
| `courtyard_clearance` | `courtyards_overlap` |
| `silk_clearance` | `silk_overlap` (and `silk_over_copper` against pads) |
| `creepage` | `creepage` on 10.0.6; nothing on 9.0.9 |
| `no_tracks` | `items_not_allowed` on 10.0.6; 9.0.9 not yet recorded |

The benches of the last six kinds carry the canary scoped to its own net (`A.NetName == 'CANARY_A'`): the
plain canary matches every pair and would take the one violation KiCad reports for a pair.

**Letter case.** KiCad compares names without regard to case, while the model's selectors are
case-sensitive. Lowering writes names as given, so two nets or classes whose names differ only in case
would both be selected by a rule written for one of them; the build (c0011), which knows the nets,
refuses such designs.
