---
topic: route-proposals
title: Route proposals and atomic bundles
summary: Negotiated alternatives, facts, whole bundles and reviewed decisions.
---

# Route proposals and atomic bundles

Start with `fenolite capabilities --brief --json`. Work on a copy and inspect the unconnected nets.
`--propose` writes nothing. Existing manual, script and locked copper is fixed input; a proposal does
not remove it. Use `board-routing` for physical routing practice and `routing` for scripted copper.

Bounded search (`search=fallback`, `search=only`) and its refusals are on the page `route-search`.

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

`fenolite.route-decisions.v0` bytes stay unchanged for independent decisions. Bundle-bearing
records add the optional `bundles` key; never strip unknown fields to make an older reader accept
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


## Local external alternatives

Add repeatable `--propose-with ROUTER` to octilinear proposals. Supported names are `freerouting`
(local jar) and `kicadroutingtools` (local checkout/interpreter). Check each router's
`external_candidates` in `capabilities --brief --json`: `supported`, `available`, `projection`,
`scope`, `arcs`, `pairs`, `groups`, `local_only` and `automatic_acceptance`. Unsupported routers
have null metadata; availability is null when tools were not queried. Containers and cloud routers
are refused in candidate mode. This command never fetches a tool or uploads the board.

```fenolite-cmd
fenolite route board --router octilinear --propose --propose-with kicadroutingtools --nets SIGNAL --timeout 120 --json
fenolite route board --router octilinear --accept CANDIDATE --propose-with kicadroutingtools --nets SIGNAL --dry-run --json
```

Use the existing `FENOLITE_KRT`, `FENOLITE_KRT_PYTHON`, `FENOLITE_FREEROUTING_JAR` and
`FENOLITE_JAVA` configuration. With exactly one adapter, `--router-path` selects its checkout/jar;
`--router-python` selects KiCadRoutingTools' interpreter. Multiple requested adapters use their
individual environment configuration. Router options still configure the primary octilinear router.
Missing requested tools return `FEN-6001` (exit 6), with no silent fallback or write.

Only ordinary pad-to-pad connections are supported. The selected two original pad-containing
components must merge; all other components must remain separate. Anonymous/unsupported islands,
track/zone endpoints, arcs, pair legs and critical groups are refused. A whole-board result is compared
to the board actually sent: moved pads/footprints, changed outline/stackup/rules, edited/removed old
copper or unselected additions reject the entire output. External IDs cannot prove preservation.
A session is a copper-only projection; its placements, unknown state and every decoded net are
checked before filtering. New tracks, allowed layers, full through-via barrels and both copper/role
judges must pass. The external result never replaces the original board.

`--candidates N` bounds internal shapes; each requested external adapter can add one alternative
per subject. Repeat an explicit limit during external-decision regeneration; `result.next` preserves it.

Candidate `source` is `external:<router>`. Its `tool` reports `router`, `version`, `inputs` (tool-byte
fingerprint), `job` (input fingerprint) and `deterministic=false`; acceptance rows retain that tool
metadata. External tools may regenerate different geometry despite the same Fenolite seed. Reuse
`result.next`, which repeats actual controls/selection; if an ID disappears, propose and review again.
Confirmation consumes staged bytes without executing the tool. Changed declared tool files or board,
rules, role/profile/requirements and sidecars invalidate the reviewed plan with `FEN-4002`.

`result.external.requested` lists deduplicated adapters; `refusals` lists `subject`, `router`, `reason`
and diagnostic `details`; `not_attempted` identifies work left by the shared deadline. Refusal reasons:
`external-unsupported`, `external-judge-missing`, `external-net-missing`, `external-incomplete`,
`external-tool-failed`, `external-unsupported-output`, `external-unselected-copper`, `external-via-scope`,
`external-geometry-missing`, `external-geometry`, `external-scope-unsupported`, `external-scope` and
`external-merge`. Final role refusal can report `search-role-refused`. Tool details may identify
`external-board-missing`, `external-topology-changed`, `external-copper-changed` or
`external-duplicate-copper`. Fix the stated scope/geometry/input problem and review new proposals.

One `--timeout` covers preparation, internal work, tool/version processes and facts (900 seconds
when omitted with external candidates). Killed, malformed, failed or incomplete output gives no
candidate. Cancellation kills the owned process tree; Windows uses bounded `taskkill /T /F` and
reports cleanup failure explicitly. Native Windows tree behavior is still unconfirmed. Elapsed time
is not an identity or score. Clock truncation reports only the attempted subset; it is not exhaustive.
Real pinned-router/KiCad CI evidence is required before native compatibility can be claimed.



## Inspect proposals in the viewer

`view BOARD --proposals FILE --serve --allow-actions` shows dashed alternatives, layer-filtered
vias, subject ends, locked/rejected choices, relaxations and tool facts. Toggle and Focus / cross-probe
without selecting acceptance. Missing facts stay unknown; static exports are read-only.
Scene `sha256`, `controls`, `notes`, `stale`, `ends`, `drill`, `unknown_geometry`, `tool` and `bundle`
are additive. `result.controls` uses `fenolite.proposal_controls.v0`: router_options, external_routers,
nets, kinds, groups, candidate_limit, requirements, timeout, gate, portable. The server allowlists
controls; requirements stay inside the project root. It never executes command text.
Review accept/reject plan, then explicitly confirm. Stale or nonportable controls require regeneration.
Atomic choices use only the whole b-ID, including hidden members; malformed bundles are inspection-only.

Read next: `route-search`, `board-completion`, `board-routing`.
