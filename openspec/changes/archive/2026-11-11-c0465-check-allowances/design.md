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
- The neutral `max` is inclusive. Altium DRC uses different measurements (D7).

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

ShortCircuit is mapped as follows. Native NetAntennae is carried:

| Altium | neutral |
|---|---|
| ShortCircuit, `ALLOWED=TRUE` | `short`, severity `ignore`, scopes → selectors |
| ShortCircuit, `ALLOWED=FALSE` | `short`, severity `error` |
| NetAntennae | native carrier; the tolerance cannot govern the portable centre-line check |

- **Only where it relaxes something** (coordinator's adjustment, 2026-11-06). When no enabled ShortCircuit
  record of the document has `ALLOWED=TRUE`, none maps: a rule that forbids a short is Fenolite's built-in
  check, and an `error` rule on every import would churn every census. When one does, every enabled
  ShortCircuit record maps, so the source's order of priority holds. A ShortCircuit
  record in a document where none relaxes a short is reported `checked`, as in c0462.
- Every record, mapped or not, is still carried (c0434), so the Altium writer writes it back unchanged.
- `altium.rules.check-relaxed` remains withdrawn. The ordinary unmapped and conversion coverage reports
  explain that native NetAntennae must be checked in Altium.
- The Altium writer lowers both kinds of an authored design to their records. The keys are those the public
  records hold (S-2243, a corpus census).

## D6: KiCad

KiCad's custom rules name no constraint for a short between nets, and none for the length of a dangling
track (S-2242). `via_dangling` (10.0 only) takes no length. A net tie is a footprint's pad group.

| neutral | KiCad 9 | KiCad 10 |
|---|---|---|
| `short` `error` | nothing (the default) | nothing |
| `short` `ignore` or `warning`, both sides `all`, and no other `short` rule | `rule_severities.shorting_items` = the severity | the same |
| any other `short` `ignore` or `warning` | loss | a `clearance` rule with a negative `min` between the sides, if probes `dru-short-allow` and `dru-short-allow-clearance` (task 4.2) both record `present`; otherwise a loss |
| `antenna` with `max` 0 | nothing (the default) | nothing |
| any other `antenna` | loss | loss |

- Task 4.2 measured both majors (2026-11-06): the negative `min` silences the short (`dru-short-allow`
  `present`), and the clearance check of the two nets with it (`dru-short-allow-clearance` `absent`). Such a
  rule would allow any gap between the nets, which the neutral `short` rule does not say, so the row stays a
  loss on both majors.
- A loss is `rules.kind-unchecked` (error, droppable). With `allow_lossy` it becomes
  `rules.dropped-for-target`, as for every kind outside its `KIND_SUPPORT` entry.
- A KiCad board read back holds no `short` and no `antenna` rule. Reading
  `rule_severities.shorting_items` is c0114's severity, and stays one.

## D7: evidence

- S-2240: Altium's Net Antennae constraint, the maximum permissible stub length (manufacturing page).
- S-2241: Altium's Short-Circuit, whose two scopes select the target nets (electrical page).
- S-2242: KiCad's constraint table, 9.0 and 10.0.
- S-2243: the census of the public Short-Circuit and Net Antennae records.
- S-2244: the probes `dru-short-allow` and `dru-short-allow-clearance`.
- S-2245: the kit run.

The labels:

- The Altium semantics are INFERRED until the kit (task 6.1) shows Altium's DRC on authored stubs and
  shorts.
- The KiCad lowering is KICAD-VERIFIED by the probe and the tests.

### Native observations (S-2245, 2026-11-10)

The scoped short control agrees with D2: one forbidden pair is reported with the allowance, and both
pairs are reported with that allowance disabled. The antenna measurements do not establish D3 as an
Altium oracle. At 50 mil tolerance the observed bare-track boundary depends on the width, and a 40 mil
via-ended branch is reported. The 0 mil control proves the three bare-track branches were measurable.
Do not replace the neutral centre-line definition with an inferred width correction: the tested lengths
only bracket its effect, and via, arc and bend handling still need separation. No broad evidence label
is raised by these partial native measurements.

### Portability decision (S-2298)

At 50 mil, width, geometry and the existence of a via affected Altium's verdict. At 1000 mil the
same 11 via endpoints still generated findings. Lowering a native tolerance to a neutral allowance
would therefore suppress some findings that Altium reports. Native records stay in the board
carrier and return unchanged, and the conversion describes the coverage limit. A legacy model rule
with an Altium record identity cannot lower the severity of a KiCad dangling finding. An authored
portable antenna rule still uses the centre-line check; exporting it writes the requested native
tolerance field, with no claim of DRC equivalence.
