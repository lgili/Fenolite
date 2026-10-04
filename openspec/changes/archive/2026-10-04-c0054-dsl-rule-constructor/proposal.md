# c0054 — Design-rule minimums in the design script

## Why

A design script can declare net classes, but no design rule. `dsl.to_model` writes an empty `RuleSet`
(c0011, design Decision "Custom rules in the DSL": "a rule constructor … in v0.2a (or c0025 if the agent
loop needs it)"), and no later change took it. So a script cannot state the fab minimums that c0026
lowers to the board setup, and the 40-part example of c0025 has to pass KiCad's DRC against the
template's values. The maintainer decided on 2026-10-04 that the constructor belongs to v0.1.

Everything below the DSL exists: the rule model (c0004), `lower_rules` (c0018), the board-setup
minimums (c0026) and the rules merge of a rebuild (c0019).

## What changes

- **DSL.** `design.rules.minimum(*, clearance, track_width, via_diameter, via_drill, hole_size,
  edge_clearance, netclass=None)` declares one minimum per given length, for the whole board, or for
  the nets of a declared class. It follows `design.rules.netclass(...)`: keyword lengths with units,
  `DslError` at the call.
- **Model.** `dsl.to_model` writes one model `Rule` per minimum into `Design.rules`, with an id keyed by
  the kind and the class (`dsl.KEYS["rule"]`). No model or schema change: `rules.json` already holds
  rules.
- **KiCad build.** No new writer: `write_triad` already lowers `Design.rules` to `<name>.kicad_dru` and
  to the board-setup minimums of `<name>.kicad_pro`.
- **Oracle.** A new test builds the routed blink with minimums and shows that `kicad-cli pcb drc`
  reports the violation on the build that breaks a minimum and none on the build that respects it, for
  board and class minimums of clearance, track width and via size.
- **Altium build.** The minimums are not carried; the build reports them with one
  `altium.not-lowered` info (`where` = `design-rules`) naming them.
- **Docs.** `docs/dsl.md` ("Design rules", API list, key table), `docs/design-model.md`,
  `docs/altium.md`, `docs/hypotheses.md` (`H-K-DSL-MINIMUM`), `CHANGELOG.md`.

## Capabilities

- `design-dsl`: ADDED "Rule minimums in the DSL"; MODIFIED "Net classes in the DSL" and "DSL to model".
- `design-model`: MODIFIED "Identifier derivation" (one key row).
- `kicad-oracle`: ADDED "Script rule minimums are enforced by kicad-cli".
- `altium-build`: ADDED "Rule minimums in an Altium build".

## Non-goals

Deferred to v0.2a unless stated:

- Rule severities other than `error`, and `rule_severities` of the project (v0.2b).
- `opt` and `max` limits, layers, and selectors other than "the board" and "one net class" (nets,
  references, item kinds, compound selectors, a second selector).
- Custom rule expressions, differential pairs, length matching.
- Resolving a class clearance against a board clearance minimum: c0026's `kicad.project.class-shadowed`
  and `kicad.project.below-floor` warnings stay the report; no value is changed for the user.
- Writing the minimums into the Altium PCB document. Its rules come from the net classes and from
  Fenolite's `All` defaults (c0038); feeding minimums into them changes the rule writer and needs an
  Altium acceptance run, which is more than an adapter.
- Changing `examples/` (c0025 writes `board_40parts`).

## Ordering

- Independent of c0016 and c0023. c0025 comes after and may use `minimum()` in `board_40parts`.
- The sibling c0053 (script copper into the Altium build) edits `lens/altium.py` and possibly the DSL.
  This change adds one block to `lens.altium._not_lowered` and one method to `dsl.design.Rules`; either
  order merges.

## Evidence level required

- DSL, conversion and ids: unit tests (no label; model behaviour).
- KiCad enforcement of built minimums: `KICAD-VERIFIED (10.0.x)` from the local `kicad-cli` 10.0.6
  before merge; 9.0.x from the `kicad-9` job. Until both ran, `H-K-DSL-MINIMUM` is `INFERRED`. It rests
  on `H-K-DRU-KIND`, `H-K-DRU-COND`, `H-K-DRU-ORDER` and `H-K-PRO-MIN-KEYS`, which are
  `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- Altium: no file changes, so no label changes.

## Sources

Public only: the KiCad PCB editor manuals for custom rules (S-0010, S-0038 in
`docs/evidence/sources.md`). No new source.
