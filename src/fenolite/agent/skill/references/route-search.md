---
topic: route-search
title: Bounded and role-aware route search
summary: Opt-in bounded and role-aware search.
---

# Bounded and role-aware route search

Search proposes ordinary connections that fixed shapes cannot finish. It is opt-in, writes nothing
with `--propose`, and keeps the reviewed accept/reject protocol of `route-proposals`.

## Bounded search

For an ordinary connection that fixed shapes cannot finish, add `--router-option search=fallback`.
`search=only` skips the fixed shapes; `search=off` is the unchanged default. Opt-in needs all three
bounds: `search-grid=LENGTH`, `search-max-states=N` (positive), and `search-max-vias=N` (zero allowed).
These are search limits, not fabrication or electrical requirements. The core uses no external router.

```fenolite-cmd
fenolite route board.kicad_pcb --router octilinear --propose --nets SIG --router-option search=fallback --router-option search-grid=0.5mm --router-option search-max-states=50000 --router-option search-max-vias=1 --json
fenolite route board.kicad_pcb --router octilinear --accept c-0123456789abcdef --router-option search=fallback --router-option search-grid=0.5mm --router-option search-max-states=50000 --router-option search-max-vias=1 --dry-run --json
```

Inspect the geometry/facts, then repeat acceptance with `--confirm --plan PLAN_ID`. The example ID
is a placeholder: use the actual candidate ID. Acceptance/rejection regenerate proposals, so repeat
the same search, candidate-count and max-length options. Confirmation writes the reviewed bytes.
New candidates have `source=search`, no score or recommendation. Search never moves existing copper.
It handles ordinary connections, not independent pair legs or critical groups (`search-unsupported`).
A via checks every copper layer it crosses. Missing outline or invalid endpoints give `search-geometry`;
`state-limit`, `budget` and `cancelled` mean incomplete exploration, never a partial route or proof of
impossibility. Raise an algorithmic bound only after inspecting the constraints. A fixed bound is
repeatable; wall-clock truncation is not an exhaustive or byte-identical search guarantee.
The direct routing API supports a `RoutingJob.extra["cancelled"]` predicate and returns search work
counters in `RoutingResult.log`; these diagnostics are not candidate scores.

The sparse grid can miss a legal off-grid route. Read a candidate's measured facts and unknowns,
not a score or rank, and inspect its `region` with `render --region` before preparing a decision.

## Role-aware search

Search uses declared/confirmed roles; inferred roles stay unknown. Add `--requirements FILE`
for user pair distances (same TOML as `analyze`); repeat it for `--accept`/`--reject`. Hard limits bind. Missing HV distances give `search-role-limit`; stale field packets give
`search-role-stale`; final copper/role rejection gives `search-role-refused`.

```fenolite-cmd
fenolite route board --router octilinear --propose --requirements limits.toml --router-option search=only --router-option search-grid=0.5mm --router-option search-max-states=50000 --router-option search-max-vias=0 --json
```

`result.role_fields` lists `fingerprint`, `provenance`, `limits`, `preferences`, `unknowns`,
`missing_limits`. Candidate `facts.role_fields` adds `input_fingerprint`, `input_provenance`,
`confirmed_reference_length_lower_bound_nm`, `unconfirmed_reference_length_nm` and
`switching_exposure_upper_bound_nm`. Only validated saved fill counts; unconfirmed length is not
proven uncovered. Conservative bounds give no electrical certification or score. Changed
requirements, roles, profile or project rules invalidate the reviewed plan.

## Route or measure on an existing board

`fenolite path` searches one connection on an existing `.kicad_pcb` or `.PcbDoc` with that board's own
rules, keep-outs and copper. Ends are `REF-PIN` or `X,Y@LAYER` in mm. `--width W` plans the found copper
through the mutation protocol; a `.PcbDoc` needs `--gate clone` (edit-session clones, warning
`route.altium-edit-unconfirmed`: run Altium's DRC). `--widest` measures the widest track that fits and
never writes: `result.channel` gives `low`/`high` (nm) and the `pinch` gap.

```fenolite-cmd
fenolite path board.kicad_pcb --net GND --from D1-1 --to 30,15@F.Cu --widest --grid 0.5mm --json
fenolite path board.PcbDoc --net SIG --from U1-3 --to R2-1 --width 0.3mm --gate clone --dry-run --json
```

A refusal exits 5 with `result.refusal`: `route.no-path` (the `wall` items and `widest_gap`; `proven`
only when every neighbour gap is narrower than the track) or `route.path-limit` (bounds stopped the
search, nothing proven). `route.via-template` means the `.PcbDoc` has no via of that size to clone;
`route.repour-needed` means `--pours refilled` ignored pours a `.PcbDoc` keeps until Altium repours.

Read next: `route-proposals`, `board-routing`, `board-completion`.
