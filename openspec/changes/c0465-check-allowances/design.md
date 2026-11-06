# Design: c0465

## D1: allowances are rules, not waivers

A waiver accepts one finding, named by the locators of its items. An Altium Short-Circuit allows every short
between two sets of nets, and Net Antennae every stub up to a length. Both are design rules: they have
scopes and priorities, and a narrow rule governs a broad one.

They become two `RuleKind`s, so that they get, unchanged, the things every rule already has:

- the selector grammar: `net`, `netclass`, `layer`, `item_kind`, `area` and the c0462 leaves;
- precedence (`rule_precedence`, the later rule governs) and specificity reports;
- the canonical JSON;
- the DSL's `rule()`;
- each backend's lowering table.

`RuleSet.severities` is not used: it names a tool's check by code, and holds no scope.

The model review approves the widened `RuleKind` (coordinator, 2026-11-06). The change rides c0462's model
version 1.1 and does not bump `SCHEMA_VERSION` itself.

| kind | sides | limits | meaning |
|---|---|---|---|
| `short` | `selector_a`, `selector_b` | none | the severity of a short between an item of side A and an item of side B, in either order |
| `antenna` | `selector_a` | `max` (≥ 0) | an open-ended stub of the selected nets passes when its length is at most `max` |

- `short` uses `Rule.severity` as its value:
  - `ignore` allows the short;
  - `warning` reports it as a warning;
  - `error` reports it as an error.
  With no governing `short` rule, a short is an error, as today.
- `antenna` keeps its `severity` for a stub longer than `max`. A stub within `max` is accepted.
- Altium's page does not say whether a stub of exactly the tolerance passes. `max` is inclusive like every
  `max` of the model. The kit of task 6.1 settles it (`H-A-RULE-ANTENNA`).

## D2: which rule governs

- **Shorts.** The subjects are the two touching items' `RuleSubject`s, the same ones `copper.clearance`
  uses. The governing rule is the last rule of kind `short` in `rule_precedence` order that matches the
  pair in either order (`selector_matches`). This is how a clearance rule governs, so a higher-priority Altium
  record that forbids a short overrides a lower one that allows it.
- **Antennae.** The subject is the stub's open-end item: a track or an arc. The governing rule is the last
  rule of kind `antenna` that matches it.

## D3: the stub

`checks.allowances.stub(design, item)` measures the stub of a dangling item on the design's own copper,
without a tool. It walks the open-ended run on `checks.padpath.CopperGraph`, which splits tracks at their
junctions:

- it starts at the open end and follows the run of tracks and arcs;
- it stops at the first node where the run meets other copper: a pad, a via that joins other copper, a
  zone of the net that holds the node, or a junction of three or more pieces;
- the length is the sum of the centre-line lengths (`CopperGraph`'s exact arc lengths).

A track whose two ends are both open is one stub of its whole length. A via that ends a run and joins
nothing else is an open end, as Altium counts it (S-2217).

An entry whose item cannot be resolved on the design, because a uuid names no item or several, is left
unchanged. The stage then gives the info `check.allowance-unresolved`.

## D4: what check does

There is one helper, `checks.allowances`, and no code is shared with `checks.waivers`.

- **Where the rules come from.** A KiCad file holds no `short` or `antenna` rule (D6), so `check` takes them
  from the `.fenolite/` model of a built project, as it takes its waivers (`run_checks(allowances=)`), with
  those of the board read. The copper guards of `build` take the design's own, as they take its waivers: a
  short the design allows does not refuse the build.

- **Copper stage.** A `copper.short` governed by an `ignore` rule takes severity `info`, and its message
  ends with ` (allowed by rule <name>)`. A `warning` rule gives severity `warning`.
- **DRC stage.**
  - `kicad.drc.shorting-items`: the entry's two items are resolved by uuid, through the native ids that
    `item_locations` already reads, to their design items and subjects, and judged as in the copper stage.
  - `kicad.drc.track-dangling` and `kicad.drc.via-dangling`: the item's stub (D3) is judged against the
    governing `antenna` rule. Within `max`, the entry takes severity `info` and ends with
    ` (stub <length> within <max> of rule <name>)`.
- **Order.** Allowances are applied before waivers, and a waiver may still match an allowed finding. A
  stage whose every error was allowed or waived has status `ok`.
- **Summary.** `summary["allowed"]` gives, per code, the findings an allowance accepted. It is left out
  when empty, so the reports of a design without these rules stay byte for byte the same.
- No finding is removed, and evidence is unchanged.

## D5: the Altium import

c0462 lists ShortCircuit and NetAntennae as `checked`. Here they move to `RULE_KIND_MAP`:

| Altium | neutral |
|---|---|
| ShortCircuit, `ALLOWED=TRUE` | `short`, severity `ignore`, scopes → selectors |
| ShortCircuit, `ALLOWED=FALSE` | `short`, severity `error` |
| NetAntennae, `NETANTENNAETOLERANCE` = t | `antenna`, `max` = t, scope → `selector_a` |

- **Only where it relaxes something** (coordinator's adjustment, 2026-11-06). When no enabled ShortCircuit
  record of the document has `ALLOWED=TRUE`, none maps: a rule that forbids a short is Fenolite's built-in
  check, and an `error` rule on every import would churn every census. When one does, every enabled
  ShortCircuit record maps, so the source's order of priority holds. NetAntennae likewise maps only when one
  enabled record has a tolerance above 0. A record not mapped is reported `checked` as in c0462.
- Every record, mapped or not, is still carried (c0434), so the Altium writer writes it back unchanged.
- `altium.rules.check-relaxed` is withdrawn: its records are now honoured.
- The Altium writer lowers both kinds of an authored design to their records. The keys are those the public
  records hold (S-2243, a corpus census).

## D6: KiCad

KiCad's custom rules name no constraint for a short between nets, and none for the length of a dangling
track (S-2242). `via_dangling` (10.0 only) takes no length. A net tie is a footprint's pad group.

| neutral | KiCad 9 | KiCad 10 |
|---|---|---|
| `short` `error` | nothing (the default) | nothing |
| `short` `ignore` or `warning`, both sides `all`, and no other `short` rule | `rule_severities.shorting_items` = the severity | the same |
| any other `short` `ignore` or `warning` | loss | a `clearance` rule with a negative `min` between the sides, if probe `dru-short-allow` (task 4.2) records `present`; otherwise a loss |
| `antenna` with `max` 0 | nothing (the default) | nothing |
| any other `antenna` | loss | loss |

- A loss is `rules.kind-unchecked` (error, droppable). With `allow_lossy` it becomes
  `rules.dropped-for-target`, as for every kind outside its `KIND_SUPPORT` entry.
- A KiCad board read back holds no `short` and no `antenna` rule. Reading
  `rule_severities.shorting_items` is c0114's severity, and stays one.

## D7: evidence

- S-2240: Altium's Net Antennae constraint, the maximum permissible stub length (manufacturing page).
- S-2241: Altium's Short-Circuit, whose two scopes select the target nets (electrical page).
- S-2242: KiCad's constraint table, 9.0 and 10.0.
- S-2243: the census of the public Short-Circuit and Net Antennae records.
- S-2244: the probe `dru-short-allow`.
- S-2245: the kit run.

The labels:

- The Altium semantics are INFERRED until the kit (task 6.1) shows Altium's DRC on authored stubs and
  shorts.
- The KiCad lowering is KICAD-VERIFIED by the probe and the tests.
