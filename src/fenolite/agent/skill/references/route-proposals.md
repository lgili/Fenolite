---
topic: route-proposals
title: Route proposals and atomic bundles
summary: Bounded search, negotiated alternatives, measured facts, whole-bundle decisions and reviewed plans.
---

# Route proposals and atomic bundles

Start with `fenolite capabilities --brief --json`. Work on a copy and inspect the unconnected nets.
`--propose` writes nothing. Existing manual, script and locked copper is fixed input; a proposal does
not remove it. Use `board-routing` for physical routing practice and `routing` for scripted copper.

## Bounded search

Use `--router octilinear --propose`. `--router-option search=off` keeps fixed patterns (default).
`search=fallback` searches when patterns fail; `search=only` skips patterns. Both require explicit
`search-grid=LENGTH`, `search-max-states=N` and `search-max-vias=N`. Bounds are software inputs,
not fabrication limits. The sparse grid can miss a legal off-grid route. Pair legs and critical
groups without a supported atomic algorithm are refused; do not force them into separate tracks.

```fenolite-cmd
fenolite route board --router octilinear --propose --router-option search=only --router-option search-grid=0.5mm --router-option search-max-states=50000 --router-option search-max-vias=0 --json
```

A candidate's `source=search` identifies complete geometry. Read its measured facts and unknowns,
not a score or rank. `state-limit`, `budget` or `cancelled` means unfinished exploration, not a proof
that routing is impossible. Inspect its `region` with `render --region` before preparing a decision.

## Negotiate ordinary connections

Add `--router-option negotiate=on --router-option negotiate-max-rounds=N`. Default `negotiate=off`
keeps independent proposals. Negotiation needs at least two selected ordinary connections and the
explicit search bounds. It reroutes only job-owned provisional paths, increasing nonnegative costs
near provisional conflicts. The discovered-state bound is shared across all subjects and rounds;
`--timeout` and cancellation also cover the whole job. No provisional overlap is emitted.

```fenolite-cmd
fenolite route board --router octilinear --propose --nets SIG --nets SECOND --router-option search=only --router-option search-grid=0.5mm --router-option search-max-states=50000 --router-option search-max-vias=0 --router-option negotiate=on --router-option negotiate-max-rounds=5 --json
```

`result.bundles` lists each atomic alternative's `id`, `fingerprint`, `members` (candidate IDs) and
`subjects` (connection keys). Each candidate's `bundle` names its unit. `result.next` gives commands
that repeat the actual controls and selection. There is one complete joint alternative; candidate
count does not produce multiple bundles. Pair/group relaxation and global optimality are not promised.

Only a set passing swept geometry, connection checks and both copper/confirmed-role judgments is
emitted. Read refusal reasons:

- `negotiate-subjects`: select at least two distinct ordinary connections.
- `negotiate-unsupported`: a selected pair/group needs a supported atomic router.
- `negotiate-round-limit`: rounds ended with conflicts; inspect placement or review a higher bound.
- `negotiate-judge-missing`: the direct routing adapter omitted the complete-set validation callback.
- `negotiate-refused`: whole-set final validation failed; inspect the existing checks and limits.

No candidate or bundle from failed/interrupted negotiation can be accepted. Existing accepted
copper stays fixed. A seed and deterministic bounds give stable geometry; clock truncation can stop
at another point. Temporary overlap never means permission to export a short circuit.

## Whole-unit decisions

Use the `b-…` bundle ID for `--accept` or `--reject`, never a member ID. Reuse the search/negotiation
options and the `--nets`, `--kind` or `--group` selection used to propose the subset. Prepare the plan
with `--dry-run`, inspect it, then `--confirm --plan ID`. Confirmation writes reviewed bytes without
searching again. `--gate drc` groups all bundle copper into one KiCad gate unit.

```fenolite-cmd
fenolite route board --router octilinear --accept BUNDLE --router-option search=only --router-option search-grid=0.5mm --router-option search-max-states=50000 --router-option search-max-vias=0 --router-option negotiate=on --router-option negotiate-max-rounds=5 --dry-run --json
fenolite route board --router octilinear --replay BUNDLE --dry-run --json
fenolite route board --router octilinear --forget BUNDLE --dry-run --json
```

`--reject BUNDLE --reason TEXT` records the whole alternative without writing board copper;
`--show-rejected` displays its rejected members. `--replay [BUNDLE]` restores the missing locked
members as one unit after rechecking endpoints and current hard fields; bare `--replay` still
replays all decisions. If one member is stale, none of its missing siblings is restored.
`--forget BUNDLE` removes the complete decision and its matching locked copper; unrelated manual
copper stays. Individual-member accept/reject/replay/forget fails with `FEN-2001` naming the bundle.

Legacy `fenolite.route-decisions.v0` bytes stay unchanged for independent decisions. Bundle-bearing
records use `fenolite.route-decisions.v1`; never strip unknown fields to make an older reader accept
them. Board and record changes share one transaction. Failed writes roll back; preserve recovery
files if rollback itself fails (`FEN-1004`). A partial native-gate result cannot become half a decision. If a new alternative reuses members of
a stored unit, explicitly review `--forget` of that old unit before replacing it; history is not erased.

## Electrical limits and stale plans

`--requirements FILE` uses the same user TOML as `analyze`. Repeat it when preparing a decision;
it is also accepted with bundle replay, without search options, to supply current HV distances.
Missing HV distances are refused, never filled from a switching default. Confirmed hard exclusions
cannot be traded for length. Inferred roles stay unknown. See `board-routing` for the conservative
`role_fields` bounds: saved ground only, no invented coverage or electrical certification.

Changed board, role, profile, requirements, project rules, built sidecars or decision input refuses
the reviewed write with `FEN-4002`. Review a new plan. Direct jobs with negotiation options must hold proposal subjects; ordinary routing refuses them.
The internal `RoutingResult.bundles` and
candidate membership mirror the CLI; direct adapters must provide `extra["bundle_check"]` for
whole-set connectivity and dynamic role validation, along with the existing copper/role callbacks.

Read next: `board-routing`, `checks`, `recovery`.
