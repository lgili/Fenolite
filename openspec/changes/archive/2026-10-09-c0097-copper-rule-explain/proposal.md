# Explain the rule behind copper findings

## Why
A copper finding gives a numeric limit and source but hides matching selectors, candidates and
precedence. Users also need to distinguish a footprint's own pad spacing from placement findings.
The explanation must be hashable and describe the resolver call that actually judged the pair.

## What Changes
- Attach immutable clearance candidate rows, subjects, switches and the governing value.
- Explain the actual arc/fill judgment, normalizing nonpositive zone clearances to absence.
- Group intrinsic, inter-component and routed/free findings without changing or suppressing them.
- Preserve existing item-kind, layer and rule precedence semantics in the explanations.

## Capabilities
### New Capabilities
- `copper-rule-explanation`: diagnostic rule traces and lossless grouping.
### Modified Capabilities
None; existing copper checks keep their numeric behaviour.

## Non-goals
Electrical profiles/readiness (c0098), automatic exemptions, design advice, changing rule limits,
new verdicts, standards tables, areas, differential pairs, waivers, impedance and power analysis.
The earlier proposed diagnostic for track sizes is removed because no checker produces its input.

## Evidence level required
INFERRED on authored trace tests; existing KiCad parity and public corpus checks retain verdicts.
Sources: S-0010, S-0020 and S-0038 in docs/evidence/sources.md. No new source or change id.

## Impact
Milestone v0.4. One signed local commit on current origin/dev, with coordinator integration only.
No CLI, schema, version, milestone table or backend writer changes.
