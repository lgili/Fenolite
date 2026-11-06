# c0465: check honours an allowed short and an antenna tolerance

## Why

Change c0462 reads every Altium rule record that governs copper. Two kinds are checked by `fenolite check`
itself rather than mapped: Short-Circuit and Net Antennae. When such a record relaxes its check, c0462 reports
the warning `altium.rules.check-relaxed` and nothing more:

- a Short-Circuit with `ALLOWED=TRUE` (S-2216): Altium accepts a short between the nets its two scopes
  select (the page's example is two ground systems joined in one design);
- a Net Antennae with a tolerance above zero (S-2217): Altium accepts an open-ended track or arc whose stub
  is no longer than the tolerance.

`check` cannot honour either today, because it takes no input for them:

- `copper.short` and KiCad's `shorting_items` are reported whatever the rules say.
- A waiver (`model.findings.Waiver`) names the items of one finding by their locators. It cannot say "any
  short between `AGND` and `DGND`", and it goes stale when the copper moves.
- A net tie (`FootprintInstance.net_ties`) joins pads of one footprint, not two nets of the board.
- KiCad's dangling check (`track_dangling`) takes no length.

So an imported board whose source allows a short fails `check` with errors that Altium's own DRC does not
report, and an agent must waive each one by hand.

## What Changes

- **Two rule kinds** in `model.rules.RuleKind`, a minor model version approved by `tools/model_review.py`:
  - `short`: a binary rule over the two touching items. Its `severity` is the severity of a short between
    the items it selects. `ignore` allows the short, `warning` reports it as a warning, and `error` is
    today's default. It takes no limit.
  - `antenna`: a unary rule whose `max` is the longest stub that passes. A stub is an open-ended run of
    tracks and arcs, measured along its centre line from the open end to the first point where it meets
    other copper.
  Both follow the precedence of every rule (`checks.clearance.rule_precedence`), so a narrow rule governs a
  broad one as in Altium.
- **`check` honours them.**
  - The copper stage gives an allowed short severity `info`, with ` (allowed by rule <name>)` at the end;
    a `warning` rule gives severity `warning`.
  - The DRC stage judges KiCad's `shorting_items` entries the same way, and its `track_dangling` and
    `via_dangling` entries by the stub Fenolite measures on the design.
  - No finding is removed. The summary of each stage counts the findings an allowance accepted.
  - Allowances are not waivers: they live in the rules, match by nets and the other selector leaves, and
    never go stale.
- **The Altium import fills them.** c0462's Short-Circuit and Net Antennae records map:
  - every enabled Short-Circuit becomes a `short` rule, `ignore` when `ALLOWED=TRUE` and `error` otherwise,
    so the source's order of priority holds;
  - every enabled Net Antennae becomes an `antenna` rule with `max` = `NETANTENNAETOLERANCE`.
  - `altium.rules.check-relaxed` goes away: the records it named are now honoured.
  - The Altium writer writes the two kinds back as Short-Circuit and Net Antennae records.
- **KiCad.** KiCad has no constraint for a short between two nets, and no length for a dangling track
  (S-2242):
  - A `short` rule of `ignore` whose two sides are `all` becomes the project severity
    `shorting_items: ignore`, which is exact.
  - A narrower one is lowered only if the probe of task 4.2 shows that a negative `clearance` minimum on
    10.0 silences `shorting_items` for the selected nets. Otherwise it is a reported loss (`rules.kind-unchecked`,
    dropped with `allow_lossy`).
  - `error` rules lower to nothing: they are KiCad's default.
  - An `antenna` rule is a reported loss, except `max` 0, which is KiCad's default.
- **DSL.** `design.rules.rule()` takes the two kinds: `short` with `between` and no limit, and `antenna`
  with `max`.

## Capabilities

- `rules-model`: the kinds `short` and `antenna`, their limits and their KiCad lowering.
- `copper-check`: an allowed short.
- `verification-loop`: allowances in the DRC stage and their summary counts.
- `altium-project-reader`: Short-Circuit and Net Antennae records map; `check-relaxed` is withdrawn.
- `design-dsl`: `rule()` takes the two kinds.

## Impact

- `src/fenolite/model/rules.py`, `schemas/fenolite.model.v0/rules.json` and `docs/design-model.md`.
- `src/fenolite/checks/allowances.py` (new): the governing `short` rule of a pair, and the stub of a
  dangling item. It reuses `checks.padpath.CopperGraph`.
- `src/fenolite/checks/copper.py`, `src/fenolite/checks/drc.py` and `src/fenolite/checks/codes.py`.
- `src/fenolite/backends/altium/read/rules.py`, the Altium rule writer, and
  `docs/formats/altium/rule-file.md`.
- `src/fenolite/backends/kicad/rulemap.py`, `dru.py` and `pro.py`, and `docs/formats/kicad/rules.md`.
- `src/fenolite/dsl/design.py` and the agent guide.
- Depends on c0462, whose `check-relaxed` records this change maps. Tests use authored boards and records
  only.

## Non-goals

- A dangling check without KiCad. Fenolite's copper stage still finds no antenna by itself, so a design
  checked without KiCad judges no `antenna` rule.
- Net ties by net pair in KiCad. A KiCad net tie stays a footprint's pad group.
