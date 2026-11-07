# Router completion review evidence (c0370)

## Scope

c0370 adds no routing algorithm. It proves that the reviewed stages of c0222-c0369 compose on authored
boards, that the reply of `route --propose` states completion truthfully (`result.completion`,
`docs/routing.md`, "Proposals"), and that accepted, manual and locked copper survive later passes, scoped
tidy, interruption and conversion. Every board here is authored for Fenolite: `examples/routing/acceptance.py`
(CC0, its own SplitMix64 mixer), `tests/_completion_project.py` and `tests/_families_project.py`. No
third-party board, router code or measurement enters these proofs.

## Local proofs — 2026-11-04

- Acceptance generator: `tests/unit/routing/test_completion_fixtures.py`, 15 passed. Script SHA-256 of
  seeds (1, 2, 40) and (1, 4, 150) pinned and equal on Python 3.11 and 3.13.
- Completion facts: `tests/unit/routing/test_completion_report.py`, unit and authored-bench cases for
  `proposed`, `unknown` (a timeout, cancellation or explicit search/round bound before any candidate, or
  unmeasured facts), `no-candidate`, `rejected` and `not-attempted`; `complete` is never true.
- Reviewed stages (`tests/kicad/routing/test_completion_workflow.py`): 5 passed on the local `kicad-cli`
  10.0.6 and 5 passed in the pinned `kicad/kicad:9.0.9` image run locally. Accept, a tidy scoped to the
  approved net and a second pass are separate reviewed transactions on two and four layers. Hand-drawn
  copper (no copper marker) and locked copper keep every item although an unscoped chamfer plans to cut the
  bend; KiCad DRC opens fall 2 -> 1 -> 0 with no violation type growing; a signal during an accept or tidy
  write leaves every file's bytes and the same reviewed plan writes afterwards; `search-max-states=1`
  writes nothing and reports `unknown`.
- Families together (`tests/kicad/routing/test_completion_families.py`): role-aware search over a saved
  ground reference negotiates a crossing pair into one bundle, a missing external tool refuses the run
  (exit 6, `FEN-6001`, nothing written), the viewer refuses a lone bundle member and writes the whole unit,
  and an ordinary search pass closes the last connection; KiCad DRC opens fall 3 -> 1 -> 0. The pinned
  external tools themselves are judged only by `test_external_candidates.py` in the router CI job.
- KiCad-to-Altium readback (`tests/unit/altium/test_router_completion_readback.py`): 2 passed. Every
  KiCad track of the routed completion board returns from Fenolite's reading of the converted PcbDoc with
  its net, layer, width and lock, each end within one Altium unit after one translation.

## CI scale record — run 41947475460 (head 515ddc6a, 2026-11-04)

`tests/kicad/routing/test_completion_scale.py` passed all eight cases on KiCad 10 (artifact
`router-scale-kicad-10-1`) and on KiCad 9 (the job passed; its record was lost because the kicad-9 step had no
`FENOLITE_SCALE_RECORD`, now restored). KiCad's unconnected count as built equals `completion.open` (58 for
40 parts, 223 for 150). KiCad 10 counts, search bound 50 000 states per call:

| layers | parts | mode | proposed | no-candidate | unknown | largest A* call | wall s (telemetry) |
|---|---|---|---|---|---|---|---|
| 2 | 40 | shapes | 33 | 25 | 0 | – | 20.1 |
| 4 | 40 | shapes | 17 | 41 | 0 | – | 18.7 |
| 2 | 40 | search | 20 | 38 | 0 | 4 319 | 27.2 |
| 4 | 40 | search | 20 | 38 | 0 | 27 485 | 63.2 |
| 2 | 150 | shapes | 121 | 102 | 0 | – | 295.7 |
| 4 | 150 | shapes | 64 | 159 | 0 | – | 211.0 |
| 2 | 150 | search | 42 | 150 | 31 | 9 443 | 301.6 (budget) |
| 4 | 150 | search | 0 | 148 | 75 | 50 000 | 302.7 (budget) |

Thresholds (`FLOORS`, KiCad 10 only): the six passes that finished inside their budget must keep at least
these proposed counts with no subject `unknown`. A local KiCad 10.0.6 run of the four 40-part cases gave the
same counts. The two 150-part search passes were cut by their 300 s budget, so their counts depend on runner
speed and carry no floor; their subjects are reported `unknown`, never `no-candidate`. KiCad 9 gets floors
only after a recorded run. On KiCad 9 the 150-part shapes passes took 454–552 s (pytest call time) against
their 600 s budget. 148 subjects of the 150-part boards are `search-unsupported`.

## Limits and open gates

- Altium: the readback is Fenolite reading what Fenolite wrote, `INFERRED`. Opening the converted
  document in Altium Designer and running its DRC is a separate maintainer gate, not performed.
- KiCad: local runs are not exact-head CI. `H-K-*` rows stay `UNKNOWN` until the required pinned jobs judge
  the exact head.
- Scale: measurements up to about 150 parts are recorded by `tests/kicad/routing/test_completion_scale.py`
  in CI; thresholds come only from those recorded measurements. Wall-clock time is telemetry, never a
  pass criterion, and a run cut by its budget is never called exhaustive.
- No global completion, optimality, electrical certification or manufacturing approval is claimed.

## Exact-head CI — 2026-11-05

CI run 41968083051 (head 5f46b8d7) concluded success: the workflow, families and scale tests passed on both pinned KiCad majors. Earlier statements that this row stays `UNKNOWN` until CI are superseded by this run. Native Altium and maintainer checks named above stay open.
